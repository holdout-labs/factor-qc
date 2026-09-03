"""Probability-calibration companion gate (Brier / log loss / ECE).

Companion to ``factor_qc.gate``: the gate judges *returns*; this module
judges *probability predictions* (predicted probability vs observed binary
outcome), the evidence behind probability-style factors.  Added 2026-09 as
the dogfood backfill flagged in the dual-track ledger (the production system
had a full Brier/calibration gate with execution history; the open library
had none).

Semantics mirror the production gate:

- ``brier`` = mean((clamp(p) - y)^2), y in {0, 1};
- ``baseline_brier`` = q(1-q) with q the base rate (always-predict-base-rate);
- ``brier_skill`` = 1 - brier / baseline_brier (strictly positive baseline);
- ``log_loss`` = mean binary cross-entropy (epsilon-clipped);
- ``ece`` = sample-weighted mean |mean(p) - observed_rate| over fixed-width
  probability buckets (5 by default).

Fail-closed, like everything else in this library: without a minimum number
of samples, or with a degenerate outcome set (base rate 0 or 1), it refuses
to judge and reports ``verdict: refuse`` with a blocker instead of guessing.

This module computes and decides the companion gate; it never touches the
main backtest gate.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np

MIN_SAMPLES_DEFAULT = 30
SKILL_MIN_DEFAULT = 0.01  # mirrors the production gate's brier_skill floor
ECE_MAX_DEFAULT = 0.05  # mirrors the production gate's calibration-error cap
BUCKET_COUNT_DEFAULT = 5
_EPSILON = 1e-9

SAFETY = {
    "production_effect": False,
    "changes_probability": False,
    "submits_to_mx_moni": False,
    "allow_real_trade": False,
    "active_live": False,
}


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def probability_bin_index(score: float, bin_count: int) -> int:
    """Fixed-width bin index over [0, 1]; 1.0 lands in the last bin."""
    return min(bin_count - 1, max(0, int(_clamp(score) * bin_count)))


def evaluate_calibration(
    predicted: Sequence[float],
    actual: Sequence[int | float],
    *,
    min_samples: int = MIN_SAMPLES_DEFAULT,
    skill_min: float = SKILL_MIN_DEFAULT,
    ece_max: float = ECE_MAX_DEFAULT,
    bucket_count: int = BUCKET_COUNT_DEFAULT,
) -> dict[str, Any]:
    """Return the calibration report with fail-closed verdict.

    ``predicted`` values are probabilities in [0, 1]; ``actual`` outcomes are
    positive = up/1, otherwise 0.  Verdict is ``PASS`` only when every
    numeric gate holds; otherwise ``FAIL``; ``refuse`` when the inputs do not
    permit an honest judgement (too few samples or degenerate outcomes).
    """
    if len(predicted) != len(actual) or len(predicted) == 0:
        return _refuse("samples_required", "predicted/actual must be non-empty and equal length")
    if bucket_count < 2 or min_samples < 2:
        return _refuse("invalid_configuration", "min_samples>=2 and bucket_count>=2 required")
    probs = np.asarray([_clamp(float(p)) for p in predicted], dtype=float)
    labels = np.asarray([1.0 if float(o) > 0 else 0.0 for o in actual], dtype=float)
    if not np.all(np.isfinite(probs)) or not np.all(np.isfinite(labels)):
        return _refuse("non_finite_input", "predicted/actual must be finite")
    n = len(probs)
    if n < min_samples:
        return _refuse(
            "min_samples_required",
            f"cannot judge probability calibration with {n} samples "
            f"(minimum {min_samples}) - fail-closed",
        )
    base_rate = float(np.mean(labels))
    if not (0.0 < base_rate < 1.0):
        return _refuse(
            "degenerate_outcomes",
            f"base rate {base_rate:.4f} is degenerate (all outcomes equal); "
            "skill against a random baseline is undefined - fail-closed",
        )

    brier = float(np.mean((probs - labels) ** 2))
    baseline_brier = base_rate * (1.0 - base_rate)
    brier_skill = 1.0 - brier / baseline_brier
    clipped = np.clip(probs, _EPSILON, 1.0 - _EPSILON)
    log_loss = float(np.mean(-(labels * np.log(clipped) + (1.0 - labels) * np.log(1.0 - clipped))))

    buckets: list[dict[str, Any]] = []
    weighted_error = 0.0
    for bucket in range(bucket_count):
        mask = np.asarray(
            [probability_bin_index(float(p), bucket_count) == bucket for p in probs],
            dtype=bool,
        )
        if not np.any(mask):
            continue
        mean_probability = float(np.mean(probs[mask]))
        observed_rate = float(np.mean(labels[mask]))
        count = int(np.count_nonzero(mask))
        weighted_error += count * abs(mean_probability - observed_rate)
        buckets.append(
            {
                "bucket": f"{bucket / bucket_count:.1f}-{(bucket + 1) / bucket_count:.1f}",
                "count": count,
                "mean_probability": round(mean_probability, 8),
                "observed_up_rate": round(observed_rate, 8),
            }
        )
    ece = weighted_error / n

    checks: list[dict[str, Any]] = []
    skill_ok = brier_skill >= skill_min
    checks.append(
        {
            "check_id": "brier_skill",
            "severity": "P1",
            "title": "Brier skill against always-base-rate baseline",
            "value": round(brier_skill, 6),
            "threshold": round(skill_min, 6),
            "passed": skill_ok,
        }
    )
    ece_ok = ece <= ece_max
    checks.append(
        {
            "check_id": "calibration_error",
            "severity": "P1",
            "title": "sample-weighted mean absolute calibration error (ECE)",
            "value": round(ece, 6),
            "threshold": round(ece_max, 6),
            "passed": ece_ok,
        }
    )
    passed = skill_ok and ece_ok
    return {
        "schema_version": "factor_qc_calibration_report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n": n,
        "min_samples": min_samples,
        "base_rate": round(base_rate, 6),
        "brier": round(brier, 6),
        "baseline_brier": round(baseline_brier, 6),
        "brier_skill": round(brier_skill, 6),
        "log_loss": round(log_loss, 6),
        "ece": round(ece, 6),
        "bucket_count": bucket_count,
        "buckets": buckets,
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "checks": checks,
        "note": (
            "probability calibration is judged fail-closed: too few samples or "
            "degenerate outcomes refuse a verdict; skill is measured against "
            "always predicting the base rate."
        ),
        "safety": SAFETY,
    }


def _refuse(reason: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "factor_qc_calibration_report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verdict": "refuse",
        "passed": False,
        "blockers": [reason],
        "note": message,
        "safety": SAFETY,
    }
