# B35/A36 Pre-Outcome Conditional Evidence Contract

Status: **FROZEN DESIGN ONLY — NO STRATEGY OUTCOMES OPENED**

Contract: `atlas-b35-a36-conditional-evidence-v1-pre-outcome`

This package freezes how ATLAS will answer the research question **which frozen strategy works, for which kinds of stocks, under which market conditions, at what cost and risk, and when should ATLAS abstain?** It does not answer that question yet. The contract must be accepted before a separate finite DEVELOPMENT replay is authorized.

## 1. Bound strategy pack

The evaluation is bound to B34 pack fingerprint:

`6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf`

and exactly these RESEARCH-only strategy IDs:

1. `b34_gap_continuation_v1`
2. `b34_opening_range_breakout_15m_v1`
3. `b34_premarket_relvol_consolidation_v1`
4. `b34_highest_volume_day_style_v1`

No signal threshold may be silently changed after outcomes. A materially changed formulation is a new challenger with a new fingerprint and a new trial.

## 2. Evidence windows and blindness

Primary DEVELOPMENT scoring and selector fitting end **2026-04-30**. This avoids the May monthly partition that overlaps the already-consumed master holdout.

The old master interval **2026-05-12 through 2026-08-11** may never contribute selector-fitting labels or scored strategy outcomes for these B34 strategies. It cannot be reused as a rescue holdout.

Rows after DEVELOPMENT and before the new blind may be used only as fixed-feature warm-up for a later future signal. Warm-up rows must be counted separately and may not fit the selector, change a strategy threshold, or contribute a return label. This distinction is necessary because a genuinely future decision may legitimately require prior 20-session or 252-session lookbacks even though those prior dates are not reusable performance evidence.

A new future blind begins on the first actual XNYS regular session on or after **2026-09-08**. The blind cannot be unsealed until at least **63 complete XNYS sessions** have accrued, all bound fingerprints still match, and no prior blind-consumption receipt exists. Blind outcomes cannot be displayed, used to refit the selector, or converted into DEVELOPMENT after an unfavorable result.

## 3. Walk-forward design

The DEVELOPMENT selector uses rolling time-ordered folds:

- training window: **504 XNYS sessions**;
- test window: **63 XNYS sessions**;
- step: **63 sessions**;
- embargo: **1 session**;
- strategy signal parameters: never refit;
- condition profiles and selector scores: fit from the training fold only;
- test-fold realized outcomes: never available to same-fold selection.

A strategy becomes eligible only when its own required historical lookbacks are available. Missing history remains missing; no synthetic bars or guessed factors are introduced.

## 4. Entry, exit, and risk geometry

Every fired setup remains in the opportunity ledger even when no simulated entry can be completed.

After the frozen signal becomes information-safe, a simulated order is submitted for the next eligible regular-session minute. Entry uses the first observed regular bar open within five minutes. If no such bar exists, the opportunity remains recorded as a no-entry liquidity/data outcome rather than disappearing from the denominator. Entry must preserve valid stop/target geometry. Only the first entry attempt per strategy/instrument/session is eligible.

Frozen stops:

- gap continuation: prior regular-session close;
- 15-minute ORB: opposite opening-range boundary;
- premarket relative-volume consolidation: premarket consolidation low;
- HVD-style breakout: premarket consolidation low.

The primary target is **2.0R** from the actual simulated entry. Stop/target collisions inside the same minute are resolved **adverse-stop-first**. If a bar opens through a stop, exit occurs at that worse open. A target receives no better than the target price.

All primary trades are same-session. At 15:55 ET ATLAS submits the fixed time exit; the first observed regular bar stamped 15:55 through 15:59 supplies the simulated open fill. If no such bar exists and neither stop nor target resolved the trade, the outcome is explicitly unresolved and cannot be silently included in completed-return claims.

## 5. Cost model

Because B34 accepted aggregate bars rather than historical quotes/fills, B35 uses a frozen **all-in adverse execution-cost proxy**, not a claim of quote-level fill precision.

Round-trip grid: **0, 10, 25, 50, 100 bps**.

- selector training/scoring: **50 bps round trip**;
- execution stress: **100 bps round trip**;
- cost is split equally across entry and exit and applied adversely by direction;
- every report must show the full cost grid rather than only the most flattering case.

A later accepted quote-aware source may create a new execution-cost contract, but it may not retroactively rewrite this trial.

## 6. Point-in-time condition profiles

Primary condition dimensions are frozen before outcomes:

- prior-session accepted market regime;
- prior close price;
- 20-session median regular dollar volume;
- 20-session annualized realized volatility;
- prior-close 20/50 trend state;
- absolute opening gap;
- premarket relative volume;
- premarket dollar volume;
- 15-minute opening-range width;
- signal-time bucket;
- HVD volume ratio.

The market regime for a morning intraday decision is the latest accepted regime finalized **by the prior regular-session close**, never the current day’s eventual closing regime. Price, liquidity, realized volatility, and trend use prior-close data only. Premarket features become usable at 09:30 ET. Opening-range width becomes usable at 09:45 ET. Any unavailable dimension stays `UNAVAILABLE` rather than being imputed from the future.

Sector, ticker-regime, point-in-time market-cap, short-borrow, and correlation context remain unavailable until separately accepted contracts exist.

The numeric bucket boundaries live in `packages/strategies/b35_conditional_evidence_contract.py` and are fingerprinted with the rest of the design.

## 7. Frozen selector challenger

The selector is deliberately interpretable. It never receives current-fold or same-session realized outcomes.

Each routing cell must contain at least:

- **60 opportunities**;
- **30 unique sessions**;
- **20 unique instruments**.

The score is the **5th percentile of 1,000 deterministic session-cluster bootstrap means of net risk-multiple at 50 bps round-trip cost**, calculated from training-fold outcomes only. A routing score must be strictly positive; otherwise ATLAS abstains.

The fixed fallback hierarchy starts with strategy + prior market regime + realized-volatility bucket + liquidity bucket + strategy-specific setup-intensity bucket, then progressively drops dimensions until the global strategy level. Candidate ties use stable strategy and instrument identifiers, never realized returns.

The strategy-specific setup-intensity dimension is:

- gap continuation → absolute-gap bucket;
- ORB → opening-range-width bucket;
- premarket relative-volume consolidation → premarket-relvol bucket;
- HVD-style breakout → HVD volume-ratio bucket.

Learning may recommend; it may never self-promote a strategy authority level.

## 8. Portfolio/account replay

The selector challenger is compared on the same basic risk envelope as the accepted A34 account replay, bound to policy fingerprint:

`c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa`

Frozen account constraints:

- starting equity: **$100,000**;
- risk per position: **0.25% of current equity**;
- single-position notional cap: **10%**;
- gross exposure cap: **100%**;
- maximum open positions: **10**;
- maximum active positions from one family: **3**;
- one position per instrument;
- no leverage.

Signals on the short side may later be profiled as RESEARCH evidence under a separate DEVELOPMENT-outcome authorization, but short positions are **not admitted to the account replay** until borrow/locate/recall economics are accepted. This prevents a short-side research result from masquerading as executable portfolio evidence.

At the same timestamp, exits are processed before new admissions. Stable identifiers resolve remaining ties.

## 9. Multiplicity and data-snooping controls

Every primary strategy/condition/interaction trial is registered in the trials ledger. Unadjusted condition-level p-values can never promote a strategy.

The frozen analysis requires:

- session-clustered bootstrap uncertainty;
- Benjamini-Hochberg FDR control at **q = 0.05** for primary condition claims;
- Deflated Sharpe Ratio as a selection-bias/non-normality diagnostic;
- CSCV Probability of Backtest Overfitting when the fold matrix is sufficient, using **16 partitions**;
- full reporting of attempted primary cells and unavailable/underpowered cells.

These controls follow the core concern in White (2000), *A Reality Check for Data Snooping*, Econometrica 68(5), DOI `10.1111/1468-0262.00152`; Sullivan, Timmermann & White (1999), *Data-Snooping, Technical Trading Rule Performance, and the Bootstrap*, Journal of Finance 54, DOI `10.1111/0022-1082.00163`; Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, Journal of Portfolio Management 40(5), DOI `10.3905/jpm.2014.40.5.094`; and Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting*, DOI `10.21314/JCF.2016.322`.

## 10. Robustness and stress testing

Primary strategy definitions remain untouched. Prespecified perturbations are diagnostic only and cannot replace the frozen strategy after a favorable result.

Diagnostics include:

- entry delay: 0, +1, +2 minutes;
- all-in round-trip costs: 0/10/25/50/100 bps;
- ±10% threshold perturbations for gap threshold, premarket relative-volume threshold, and consolidation-width threshold;
- ORB length 14/15/16 minutes, with 15 minutes remaining the primary frozen definition;
- 10,000 session-level bootstrap/Monte Carlo resamples for drawdown, losing-streak, and P&L-concentration behavior.

A perturbation that looks better is evidence for a **new challenger**, not permission to rewrite the original strategy.

## 11. Required reporting

For every strategy and predeclared condition slice, retain counts and data-quality denominators along with:

- opportunities, unique sessions, unique instruments;
- win rate;
- mean/median net return and net R;
- session-level Sharpe and Deflated Sharpe;
- profit factor;
- MFE/MAE;
- holding time;
- cost drag;
- max drawdown;
- turnover/exposure;
- worst day and losing streak;
- P&L concentration;
- abstention rate;
- unresolved rate;
- fold-to-fold stability.

Selector/account reports additionally compare against independent-strategy profiles, the frozen A34 stable non-learned long-only portfolio baseline, and cash abstention.

## 12. Authority at this package

This package grants **none** of the following:

- DEVELOPMENT outcome access;
- future-blind outcome access;
- broad minute replay/read authority;
- broad minute materialization;
- strategy promotion;
- PAPER authority;
- LIVE authority;
- provider calls;
- broker reads or writes.

The next gate is exact-head acceptance of this frozen design, followed by a separate hash-bound finite DEVELOPMENT replay authorization. That later authorization must still exclude the consumed master interval and the future blind from scored DEVELOPMENT outcomes.
