"""Tests for the probability-calibration companion gate (Brier/log loss/ECE).

Semantics mirror the production gate that flagged 44/44 factors below a 1%
Brier-skill floor (2026-09 dogfood backfill; dual-track ledger).  All
expected values are hand-computed from the documented formulas.
"""

from __future__ import annotations

import pytest

from factor_qc.calibration import evaluate_calibration, probability_bin_index


def test_probability_bin_index_fixed_width() -> None:
    assert probability_bin_index(0.0, 5) == 0
    assert probability_bin_index(0.2, 5) == 1
    assert probability_bin_index(0.999, 5) == 4
    assert probability_bin_index(1.0, 5) == 4  # 1.0 lands in the last bin


def test_unskilled_coin_flip_fails_skill_gate() -> None:
    predicted = [0.5] * 40
    actual = [1, 0] * 20
    report = evaluate_calibration(predicted, actual)
    assert report["verdict"] == "FAIL"
    assert report["brier"] == pytest.approx(0.25)
    assert report["baseline_brier"] == pytest.approx(0.25)  # q=0.5
    assert report["brier_skill"] == pytest.approx(0.0)
    assert report["ece"] == pytest.approx(0.0)  # perfectly "calibrated" at 50%
    skill_check = next(c for c in report["checks"] if c["check_id"] == "brier_skill")
    assert skill_check["passed"] is False
    ece_check = next(c for c in report["checks"] if c["check_id"] == "calibration_error")
    assert ece_check["passed"] is True


def test_well_skilled_predictions_pass_with_loose_calibration() -> None:
    # alternating outcomes 1/0; predictions 0.9 on 1s, 0.1 on 0s
    actual = [1, 0] * 25
    predicted = [0.9 if a == 1 else 0.1 for a in actual]
    report = evaluate_calibration(predicted, actual, skill_min=0.0, ece_max=0.2)
    assert report["verdict"] == "PASS"
    assert report["brier"] == pytest.approx(0.01)
    assert report["base_rate"] == pytest.approx(0.5)
    assert report["brier_skill"] == pytest.approx(0.96)  # 1 - 0.01/0.25
    # 0.9 lands in bucket 0.8-1.0, observed 1.0 -> |0.9-1.0| = 0.1 (weighted)
    assert report["ece"] == pytest.approx(0.1)
    assert len(report["buckets"]) == 2


def test_fail_closed_on_too_few_samples() -> None:
    report = evaluate_calibration([0.5, 0.6, 0.4], [1, 0, 1])
    assert report["verdict"] == "refuse"
    assert "min_samples_required" in report["blockers"]


def test_fail_closed_on_degenerate_outcomes() -> None:
    report = evaluate_calibration([0.5] * 40, [1] * 40)
    assert report["verdict"] == "refuse"
    assert "degenerate_outcomes" in report["blockers"]


def test_mismatched_lengths_refuse() -> None:
    report = evaluate_calibration([0.5] * 10, [1] * 9)
    assert report["verdict"] == "refuse"
