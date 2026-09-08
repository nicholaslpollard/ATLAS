# B35/A36 Pre-Outcome Conditional Evidence Contract

Status: **V2 FROZEN PRE-OUTCOME; FINITE DEVELOPMENT REPLAY IMPLEMENTATION FROZEN — NO B35 HISTORICAL OUTCOMES OPENED**

Active contract: `atlas-b35-a36-conditional-evidence-v2-pre-outcome-clock-split-corrected`  
Active fingerprint: `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`

Superseded pre-outcome lineage: `atlas-b35-a36-conditional-evidence-v1-pre-outcome`, fingerprint `7bfd1cfdd65e946d45caa99dd2a35a90d8b424cb82cad5941ad26cac51816c4c`. **No B35 outcome was opened under v1.** It is preserved rather than rewritten.

## 1. Why v2 exists

Before any B35 outcome access, implementation review found two preregistration inconsistencies. First, unchanged B34 allows a breakout bar stamped through 11:30 ET and defines a one-minute bar stamped `T` as usable only at `T+1`; therefore a valid 11:30 bar has an information-safe B35 decision at 11:31. V1 had ended the decision-time bucket at 11:30. V2 extends only that decision-time boundary: the last bucket is `1031_TO_1131`, and decisions after 11:31 fail closed.

Second, an overnight split makes the raw prior-close/current-open gap incomparable, but it does not cross a same-session opening-range or breakout comparison. V2 therefore records `absolute_gap_pct=UNAVAILABLE` for non-gap condition profiles when the prior-close comparison crosses a split, while preserving the otherwise-valid ORB/premarket/HVD snapshot. B34 gap continuation remains blocked across that split exactly as before.

These corrections were made before historical outcomes and do not modify B34 strategy thresholds or signals. The bound B34 fingerprint remains `6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf` for the four frozen RESEARCH strategies.

## 2. Evidence windows and blindness

Primary DEVELOPMENT scored outcomes and selector fitting end **2026-04-30**. The already-consumed master interval **2026-05-12 through 2026-08-11** may never contribute B35 fitting labels, scored outcomes, repair evidence, qualification, or selector fitting. It cannot be reused as a rescue holdout.

Rows after DEVELOPMENT and before a genuinely future signal may serve only as separately counted fixed-feature warm-up. They may not change strategy thresholds or contribute return labels. The new future blind begins on the first XNYS session on or after **2026-09-08**, requires at least **63 complete sessions** before one-time unblinding, cannot refit on blind outcomes, and cannot be recycled into DEVELOPMENT after a bad result.

## 3. Frozen walk-forward and selector design

The selector uses 504-session rolling training windows, 63-session tests, 63-session steps, and a one-session embargo. Strategy parameters never refit. Condition profiles and selector scores use training-fold outcomes only; same-fold and same-session realized outcomes are unavailable to selection.

A cell requires at least 60 opportunities, 30 unique sessions, and 20 unique instruments. The score is the fifth percentile of 1,000 deterministic session-cluster bootstrap means of net risk-multiple at the frozen 50-bps round-trip cost. The score must be strictly positive or the selector abstains/cash. The preregistered fallback hierarchy and stable tie-breaks remain unchanged. Learning may recommend but never self-promote.

## 4. Entry, exit, cost, and unresolved mechanics

Every fired setup remains in the opportunity denominator. After a frozen signal becomes information-safe, the first observed eligible regular-minute open within five minutes **measured from the decision time** is the simulated entry; otherwise the opportunity is a no-entry liquidity/data outcome. Only the first entry attempt per strategy/instrument/session is eligible.

Frozen stops remain: gap → prior close; ORB → opposite opening-range boundary; premarket relvol/HVD → premarket consolidation low. Target is 2R from actual entry. A target touched exactly at the bar open resolves at the target before later intrabar ambiguity; a stop gap exits at the worse open; a target gap receives no improvement; otherwise a same-bar stop/target collision is adverse-stop-first. At 15:55 ET the fixed time exit uses the first observed regular bar stamped 15:55..15:59 at its open. Entered trades that still cannot resolve retain signal, entry, stop, target, observed bars, and available MFE/MAE but remain excluded from completed-return claims.

All-in round-trip cost grid remains **0/10/25/50/100 bps**; selector scoring uses 50 bps and stress uses 100 bps. Half the proxy cost is applied adversely at entry and half at exit. Long and short gross/net returns and excursions are normalized to entry notional. This remains a bar-only spread/slippage/fee proxy, not quote-level fill precision.

## 5. Point-in-time conditions

Frozen dimensions remain prior market regime, prior close price, prior 20-session median dollar volume, prior 20-return annualized realized volatility, prior-close 20/50 trend, absolute gap, premarket relative volume, premarket dollar volume, opening-range width, signal time, and HVD volume ratio. Twenty close-to-close returns require **21 completed closes in one split epoch**. Raw trend/volatility comparisons fail closed across split epochs.

The latest valid decision-time bucket is `1031_TO_1131`. Cross-split raw gap is `UNAVAILABLE`. Market regime for a morning decision must be accepted and finalized by the prior regular close; where the finite minute replay lacks an exact accepted join, it remains `UNAVAILABLE` rather than guessed. Sector, ticker regime, PIT market cap, correlation, and borrow economics remain unavailable until separate accepted contracts exist.

## 6. Finite DEVELOPMENT replay implementation

The replay source is not a second data lake. It binds the exact expected 1-minute unit set to the immutable V2 native acquisition plan, including exact year/month/batch/unit identity, checkpoint body, policy/universe hashes, and canonical path/hash. May-2026-or-later minute partitions are rejected before open. Minute and split-evidence paths are confined to the isolated V2 tree without symlink/root escape. Canonical SHA-256 is verified immediately before use. Physical validation fails closed on provider/dataset/timeframe/source drift, adjusted data, non-finite or invalid OHLCV, duplicate minute keys, misplaced sessions, incorrect exchange-session labels, and non-Boolean adjustment schema. A source plan is itself content-fingerprint validated so an in-memory mutation cannot retain a stale trusted fingerprint.

Actual replay additionally requires the immutable self-hash DEVELOPMENT authorization. Concurrent replay publication is serialized. Immediately after authorization validation and before the first outcome read, ATLAS writes an immutable self-hash `outcome_read_start.json`; it remains if a later run fails, so outcome access cannot disappear merely because no completion receipt was produced. Symbol-batch outputs are compact JSONL plus self-hash completion receipts. An output without a receipt is untrusted derived state and is deterministically recomputed; a receipt without its exact hash-bound output fails closed. Restart reuses only fully validated receipts, and the final run fingerprint binds validated receipt IDs. No giant permanent minute-feature lake is created.

The production scan may prefilter candidate breakout bars for efficiency, but the unchanged B34 evaluators make the final fired/not-fired determination. Focused parity tests protect that equivalence.

## 7. Portfolio, multiplicity, and robustness

The accepted A34 portfolio envelope remains bound by fingerprint `c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa`: $100,000 start, 0.25% equity risk per position, 10% single-position notional cap, 100% gross cap, 10 open positions, three active family positions, one position per instrument, and no leverage. Short signals may be RESEARCH-profiled after explicit DEVELOPMENT authorization, but account admission remains long-only until borrow/locate/recall economics are accepted.

Primary claims retain session-clustered bootstrap uncertainty, Benjamini-Hochberg FDR q=0.05, Deflated Sharpe diagnostic, CSCV PBO when evaluable with 16 partitions, complete trial ledgering, diagnostic-only perturbations, and 10,000 session bootstrap/Monte Carlo resamples for drawdown/loss-streak/P&L-concentration behavior. A better perturbation becomes a new challenger; it cannot rewrite the primary strategy.

Methodology anchors remain White (2000), *A Reality Check for Data Snooping*, DOI `10.1111/1468-0262.00152`; Sullivan, Timmermann & White (1999), *Data-Snooping, Technical Trading Rule Performance, and the Bootstrap*, DOI `10.1111/0022-1082.00163`; Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, DOI `10.3905/jpm.2014.40.5.094`; and Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting*, DOI `10.21314/JCF.2016.322`.

## 8. Authority and next gate

Implementation acceptance itself opens **no B35 historical outcomes**. At this package: consumed-master rows read `0`; future-blind rows read `0`; provider calls `0`; broker reads `0`; broker writes `0`; PAPER orders `0`; LIVE operations `0`; strategy promotion `false`; selector promotion `false`; PAPER authority unchanged/absent; LIVE authority `false`.

After exact-head implementation acceptance and merge, the sequence is: (1) workstation `--source-only` preflight; (2) control-chat review of that source evidence; (3) only then explicit `--authorize-development-outcomes`; (4) materialize frozen DEVELOPMENT opportunity/outcome evidence; (5) analyze strategy × condition results; (6) construct the preregistered walk-forward selector/profile evidence; (7) later one-time future-blind evaluation after sufficient accrual; and (8) never reuse the consumed master interval.
