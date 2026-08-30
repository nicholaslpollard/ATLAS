# Phase32 Independent Negative Closeout

**Disposition:** `ACCEPTED_NEGATIVE`

**Accepted target-machine evidence date:** 2026-08-30

Phase32 tested the frozen SEC 8-K material corporate-event family under policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

The development study produced one frozen finalist, `solvency_distress_short`. The independent finalist blindness/lineage audit then reproduced the complete accepted development path and built the source-only protected plan without reading protected stock/SPY returns.

## Accepted finalist-audit evidence

Audit contract:

`phase32-finalist-blindness-lineage-audit-v1-independent-development-recompute-protected-unread`

Protected plan contract:

`phase32-protected-plan-v1-finalist-only-source-predictor-three-fold-no-returns`

Finalist audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Protected plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Protected plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

The audit independently reproduced:

- selection survivors: `equity_issuance_short`, `financial_integrity_adverse_short`, `listing_distress_short`, `share_repurchase_long`, `solvency_distress_short`;
- selection winners: `share_repurchase_long`, `solvency_distress_short`;
- frozen finalist: `solvency_distress_short`.

Audit status:

`AUDIT_PASS_PROTECTED_SAMPLE_GATE_IMPOSSIBLE`

## Protected source-only sample proof

The frozen protected finalist population contains:

- event rows: **46**;
- signal sessions: **33**;
- unique instruments: **40**.

The preregistered protected source-only minimums are:

- event rows: **50**;
- signal sessions: **20**;
- unique instruments: **20**.

Therefore:

- event-row gate: **FAIL** (`46 < 50`);
- signal-session gate: **PASS** (`33 >= 20`);
- unique-instrument gate: **PASS** (`40 >= 20`).

The 50-row minimum was frozen before performance. It may not be weakened after observing the result, and no alternate finalist or runner-up may be substituted. Because the source-only population cannot satisfy the mandatory sample gate, opening protected returns cannot produce an admissible Phase32 confirmation. The correct action is negative closeout without spending the holdout.

## Protected-boundary proof

Protected return rows read: **0**.

Protected holdout consumed: **false**.

Provider network activity during the finalist audit: **0**.

Broker/account reads or writes: **0**.

Order/PAPER/LIVE/automation activity: **0**.

No finalist-only protected performance evaluator is authorized or needed for Phase32 because the source-only gate is impossible.

## Scientific meaning

Phase32 found meaningful development evidence but did not earn historical support. `solvency_distress_short` passed the development selection/internal-validation path, yet its frozen protected population was too small to satisfy the preregistered protected sample requirement. That is a scientifically valid negative result, not a software failure.

Phase32 therefore closes `ACCEPTED_NEGATIVE` with:

- supported Phase32 candidates: **0**;
- Historical supported alpha remains **0**;
- Phase33 signal-to-trade entry condition: **not satisfied**;
- protected holdout: **unconsumed**;
- LIVE authority: **unchanged / disabled**.

The Phase32 8-K family may not be retuned after this result under a new label. Any next alpha phase must test a **materially different alpha mechanism** rather than weakening the 50/20/20 gate, redefining `solvency_distress_short`, substituting a runner-up, changing chronology/horizon/costs, or reopening this protected family.

## Closeout implementation

- `packages/backtesting/phase32_closeout.py`
- `scripts/run_phase32_closeout.py`
- `scripts/validate_phase32_closeout.py`
- `tests/unit/test_phase32_closeout.py`

The closeout runner validates the exact accepted audit/plan fingerprints and source counts from local immutable artifacts, verifies protected returns remain unread, verifies no protected-performance artifact exists, and writes:

`data/derived/strategy_evaluation/phase32/v1/phase32_closeout_report.json`
