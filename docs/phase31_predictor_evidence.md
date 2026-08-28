# Phase 31 Predictor-Only Form-4 Evidence

**Evidence status:** `PASS` — first accepted outcome-blind predictor construction, target machine, 2026-08-28.

This record freezes the deterministic Form-4 predictor evidence that existed **before any Phase31 development market-performance read**. It grants no alpha support, no protected-return authority, and no trading authority.

## Accepted implementation

Runner:

`scripts/run_phase31_form4_predictors.py`

Accepted implementation head:

`dbde716b79ae882bcfec412e1a13e1bb3c274f6a`

Frozen scientific policy fingerprint:

`e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

Source: accepted 62-shard authoritative Form-4 history plus accepted Composite-FIGI-authoritative PIT ticker intervals.

## Target-machine result

- authoritative rows scanned: **2,992,608**
- qualified accessions before session/identity: **103,773**
- resolved noncontradictory events: **5,870**
- development predictor rows: **5,400**
- protected predictor rows: **343**
- target outcome rows read: **0**
- protected return rows read: **0**
- provider/broker/order/PAPER/LIVE/automation writes: **0**.

Candidate-membership rows:

- `open_market_purchase_long`: **2,482**
- `clustered_open_market_purchase_long`: **1,009**
- `open_market_sale_short`: **3,261**
- `clustered_open_market_sale_short`: **1,724**.

Broad and clustered hypotheses intentionally overlap, so membership counts do not sum to the event-row count.

## Frozen artifact lineage

- authoritative Form-4 lineage SHA256: `a9a385828b436fde7bf2297d1f8b987c4899eaff7500d79fd0b6c4abf6de7918`
- PIT identity interval SHA256: `beabae4416f8444a5a062d3c3d49cdab46dec7919a545850ac0808ed94cfe3de`
- development predictor SHA256: `a82ff3114febc0c6f7c13d5f045549b714edbf0fd66157ef93853be9ae90c49f`
- protected predictor SHA256: `d3bcd2696463ec1e384919007a36570475f8cb0bf1e393f109f0accd24224e27`.

The protected predictor artifact contains metadata only. Its hash may be bound before finalist selection; its rows and all protected stock/SPY returns remain unread by the development-performance stage.

## Exclusion evidence

- `ACQUIRED_DISPOSED_MISMATCH`: 473
- `AFF_10B5_ONE_TRUE`: 37,170
- `CONTRADICTORY_PURCHASE_SALE_TICKER_SESSION`: 1,014
- `EQUITY_SWAP_TRUE`: 27
- `NOT_SUBJECT_TO_SECTION16_TRUE`: 1,636
- `NO_DECISION_SESSION_IN_FROZEN_GRID`: 117
- `NO_SECTION16_ROLE`: 1,645
- `NO_T20_EXIT_IN_FROZEN_GRID`: 963
- `NO_TRANSACTION_ROWS`: 1,568
- `OWNER_CIK_INCONSISTENT`: 9,824
- `PIT_IDENTITY_INTERVAL_DOES_NOT_COVER_EXIT`: 50
- `PIT_IDENTITY_NOT_RESOLVED`: 71,144
- `PRICE_NOT_POSITIVE`: 1,014
- `SECURITY_TYPE_INELIGIBLE`: 2,642
- `SHARES_NOT_POSITIVE`: 270
- `TICKER_ASSOCIATION_NOT_EXACTLY_ONE`: 33,635
- `TRANSACTION_CODE_NOT_PURE_P_OR_S`: 707,504.

These counts are deterministic source/predictor exclusions, not performance filters. They may not be changed after development results merely to rescue a candidate.

## What the PASS authorizes

This PASS freezes predictor membership and authorizes the next **development-only** scientific step under the already-frozen Phase31 contract. That step may read development stock/SPY outcomes only after binding this evidence and enforcing corporate-action/path admissibility.

It does **not**:

- accept Phase31;
- imply a candidate has alpha;
- authorize protected candidate-row parsing during development;
- authorize protected stock/SPY returns;
- authorize a fifth hypothesis, alternate horizon, value/role tail, runner-up substitution, or post-result search;
- authorize provider writes, broker reads/writes, order writes, PAPER, LIVE, automation, or automatic broker failover.

If development produces no frozen finalists, protected returns remain unread and the master holdout remains unconsumed. If development produces one or more finalists, an independent blindness/lineage audit must pass before any finalist-only protected-return read.
