# Changelog

## [0.1.2] - 2026-09-03
- feat: `qc calibrate` — probability-calibration companion gate (Brier / baseline Brier / Brier skill / log loss / ECE), fail-closed (refuse on too few samples or degenerate outcomes). Dogfood backfill of the production gate (dual-track ledger).
- fix: CLI JSON loads are BOM-safe (`utf-8-sig`).

## [0.1.1] / [0.1.0] - 2026-08-18
- Initial public release: fail-closed backtest gate (DSR/PBO/haircut/MinTRL), P0/P1/P2 grading, reference-value tests.
