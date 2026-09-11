# ATLAS Strategy Evidence Register

**Current as of 2026-09-11 (UTC). This file is a living project document.**

This register is the durable scientific ledger for strategy-level evidence. It exists so a future ATLAS chat can determine, without reconstructing old conversations, what each strategy version was, what evidence it opened, where it worked or failed, what remains uncertain, and what research action is currently justified.

The root `README.md`, `docs/roadmap.md`, and this register are the three living project documents. Every continuation chat must read all three before changing research direction. Code/tests remain the authority for implemented behavior; immutable receipts, fingerprints, artifacts, and Git history remain the authority for what actually happened. This register summarizes those facts and current interpretation; it must never rewrite a prior observed result to make a later version look better.

## 1. Register rules

1. **Version, never overwrite.** A strategy rule change creates a new strategy version. The prior version and its evidence remain recorded.
2. **Global failure is not automatic retirement.** A weak all-market result may still justify a condition-specialist successor if the favorable condition is economically coherent, sufficiently supported, and survives untouched/walk-forward evidence.
3. **A favorable slice is not proof.** Post-result condition findings are diagnostic hypotheses. They may motivate a bounded successor version but cannot validate that successor on the same data that inspired it.
4. **Current eligibility must be evidence-driven.** Long-term ATLAS should treat strategies as specialists whose eligibility can turn on/off with trailing point-in-time condition evidence; do not hard-code a decade-wide claim from one historical episode.
5. **Abstention is valid.** Broad coverage is a goal; continuous trading is not. Cash is correct when no strategy/condition specialty clears its evidence, cost, risk, and authority gates.
6. **Confluence is separate from strategy firing.** Independent strategies retain standalone lineage. Correlated indicators are not counted as independent votes. Distinct evidence-family agreement and conflicts are measured by a separate confluence/ranking layer.
7. **Costs remain binding.** Do not lower an accepted cost hurdle merely to rescue a strategy. Cost-sensitive mechanisms may be researched for better execution/entry/exit design under a new version.
8. **Research budget is bounded.** By default, one structured diagnostic review and no more than three materially distinct successor candidates per family per research cycle. No dense parameter fishing.
9. **Promotion remains separate.** `KEEP`, `CONDITION-GATE`, `CALIBRATE`, `REDEFINE`, or `RETIRE` are research dispositions, not authority promotions. Historical/PAPER/LIVE authority remains governed by the roadmap.
10. **Every material strategy-evidence package updates this register.** Record tested scope, fingerprints, sample/support, costs, walk-forward behavior, robustness state, disposition, candidate successor hypotheses, and unresolved limitations.

## 2. Standard evidence fields

Every strategy/version entry should maintain, where available:

- strategy/version id and family;
- evidence source (`PRACTITIONER_BASELINE`, `LITERATURE_ANCHORED`, `INTERNAL_CHALLENGER`);
- exact replay/analysis contract and fingerprints;
- evaluation interval and data authority;
- opportunities, comparable outcomes, sessions, instruments, direction coverage;
- cost grid and primary/stress cost assumptions;
- standalone win rate, mean/median net return and net-R, profit factor, MFE/MAE, holding time, noncomparable/unresolved rates;
- walk-forward folds, training/test/embargo design, selection/abstention behavior;
- condition cells with adequate support;
- time/regime stability and evidence concentration;
- multiplicity/robustness status (BH FDR, Deflated Sharpe, PBO/CSCV where evaluable, bootstrap tail/drawdown, losing streak, concentration, perturbation diagnostics);
- portfolio/account comparison status;
- current research disposition;
- successor hypotheses and the exact evidence that motivated them;
- unresolved source/execution/model limitations;
- authority state.

## 3. B35 accepted evidence package

### 3.1 Canonical replay identity

- Scope: `2016-01-04..2026-04-30` DEVELOPMENT only.
- Contract fingerprint: `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`.
- Source fingerprint: `af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd`.
- Split fingerprint: `3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6`.
- Authorization: `562d7104d56151e6203a1bf85457f9d1a90bbf19e60cd4d9359a3f96bc0a7be5`.
- Completed: 482/482 deterministic groups, 59,768/59,768 source units, 482 receipt ids.
- Fired opportunity/context/outcome records: 20,171,286.
- Run fingerprint: `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`.
- Consumed-master rows read: 0; future-blind rows read: 0; provider calls: 0; broker reads/writes: 0/0.
- PAPER/LIVE authority: false/false. Strategy/selector promotion: false/false.
- Canonical continuation performance: 400 new groups / 49,600 units in 11:40:46 at 4,246.7 units/hour, after safely reusing 82 validated groups.

### 3.2 B35 strategy × condition / selector analysis

- Analysis contract: `atlas-b35-development-evidence-selector-analysis-v1`.
- Analysis fingerprint: `8369790cc019e84091d9ff431e0ba82678e8b23ec09f65f010cdfaca35d3254f`.
- Normalized opportunities: 20,171,286.
- Walk-forward: 33 complete-XNYS folds; 504-session rolling training, 63-session test, 63-session step, 1-session embargo.
- Minimum selector-cell evidence: 60 opportunities / 30 sessions / 20 instruments.
- Selector score: 5th percentile of 1,000 deterministic XNYS-session-cluster bootstrap mean net-R outcomes at 50 bps; score must be strictly positive or ATLAS abstains.
- Fallback: broader cell only when the more-specific cell lacks minimum support. A supported nonpositive cell is not rescued by a broader positive average.
- Test opportunities: 17,030,985; selected: 3,747; selected comparable: 3,188; abstention: 99.978%.
- Selected aggregate mean return: +0.2984% at 0 bps; +0.1984% at 10 bps; +0.0485% at 25 bps; -0.2015% at 50 bps; -0.7014% at 100 bps.
- Selected aggregate mean net-R at 50 bps: +0.00715R, but median net-R is negative (-0.0877R), median return at 50 bps is negative, and win rate is about 46.3%.
- Approximate aggregate selected break-even is near 30 bps round-trip; this is diagnostic only and does not authorize weakening the frozen 50-bps selector hurdle.
- Positive selector cells were temporally concentrated: gap cells appeared in early folds (2018-2019); ORB cells appeared in 2024 through early 2025; long stretches selected nothing. This supports a rolling specialist-eligibility architecture rather than permanent static filters.
- Prior market regime was unavailable in this V2 B35 evidence. B35 therefore did not test a meaningful bull/bear regime router; successor work must not pretend it did.
- Retained-artifact robustness is now complete under fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`: 13 selected fold/cell hypotheses produced 0 BH-FDR q=.05 rejections; all five declared 50-bps profiles have negative mean session return and Deflated-Sharpe probability 0.0. Exact minute-path perturbations remain the final preregistered B35 robustness component and are implemented in PR #79 without selector refit or v1 rewrite.

### 3.3 Retained-artifact robustness result

- Robustness fingerprint: `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`.
- Scope: the same 2,079 complete XNYS walk-forward test sessions; session is the primary dependence cluster.
- Selected-cell multiplicity: 13 declared fold x strategy x fallback-level x condition-cell hypotheses; **0 BH-FDR q=.05 rejections**. The smallest raw one-sided p-values were not sufficient after multiplicity correction.
- Profile multiplicity: all five declared 50-bps profiles have negative mean session return; profile one-sided bootstrap p-values and BH-adjusted p-values are 1.0.
- Deflated Sharpe: probability `0.0` for all five declared profiles. Annualized 50-bps Sharpes are approximately gap `-25.08`, ORB `-27.25`, premarket-relvol `-16.84`, HVD `-0.57`, selector `-0.24`.
- Frozen selector cost curve: annualized Sharpe `+0.652` / `+0.475` / `+0.208` / `-0.238` / `-1.120` and mean session return `+0.0834%` / `+0.0607%` / `+0.0265%` / `-0.0303%` / `-0.1441%` at 0/10/25/50/100 bps. The low-cost structure is research evidence only; the frozen 50-bps hurdle remains binding.
- Selector 10,000-draw bootstrap at 50 bps: probability mean session return >0 = `24.21%`; median bootstrapped mean session return about `-0.0310%`; median terminal research-profile compound return about `-65.56%`; median max drawdown about `-79.75%`. The 95th-percentile bootstrap can be positive, which confirms uncertainty but not a qualifying edge.
- HVD remains extremely sparse: 46 active 50-bps sessions in the aligned profile; bootstrap probability of positive mean session return is only `4.75%`, and positive P&L is highly concentrated (top 10 positive sessions account for about 99.63% of positive-session contribution).
- PBO/CSCV: `7.77e-05` (~0.01%) across the five declared profiles. This indicates little evidence that the in-sample winner ranking is a classic overfit selection artifact, but it does **not** establish profitability; consistently weak candidates can also have low PBO.
- A34 stable long-only account replay remains context only, not same-unit statistical comparison.
- Authority unchanged: consumed-master/future-blind reads 0; provider/broker calls/writes 0; PAPER/LIVE false; strategy/selector promotion false.

**Interpretation:** B35 has not established promotable alpha. The selector materially improves the unrestricted strategies and retains a low-cost positive signal, but the 50-bps economics, FDR and Deflated-Sharpe gates remain negative. That supports continued bounded specialist/condition research, not promotion or retroactive weakening of costs.

**Final robustness component:** PR #79 merged to `main` as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`; the workstation run remains pending. It implements the five frozen minute-path perturbation families in one DEVELOPMENT-only pass. There are 27 strategy/variant profiles because entry delay is applied to all four strategies and consolidation-range perturbation applies independently to premarket-relvol and HVD. Each axis changes alone. All baseline values must reproduce the canonical v1 fired/comparable/noncomparable counts in every group before a perturbed group can complete. Better variants are diagnostic successor hypotheses only; selector refit and canonical-v1 rewrite are forbidden.

## 4. Current B35 strategy dispositions

### 4.1 `b34_gap_continuation_v1`

**Status:** observed negative standalone baseline; promising conditional specialist evidence; no promotion.

Full DEVELOPMENT evidence:

- opportunities: 2,875,318;
- comparable: 1,811,231; noncomparable: 1,064,087;
- unique sessions: 2,595; unique instruments: 20,396;
- mean return: -0.6389% at 0 bps and -1.1386% at 50 bps;
- mean net-R at 50 bps: -0.8950R; median -0.5392R;
- win rate at 50 bps: 34.76%; profit factor on net-R: 0.278;
- noncomparable rate: 37.0%.

Walk-forward selector evidence:

- test opportunities: 2,581,516; standalone comparable: 1,630,499;
- selected: 258; selected comparable: 253;
- selected mean return at 50 bps: about +0.0360%; selected mean net-R: +0.00549R.

Diagnostic specialty that repeatedly earned positive training-cell selection in 2018-2019:

- gap magnitude >=10%;
- 20-day median dollar volume $50M-$250M;
- realized volatility primarily 25-50%;
- signal near the open.

Post-result diagnostic subdivisions inside the selected set suggest potential successor hypotheses, not validated rules: LONG materially outperformed SHORT; prior-trend UP outperformed other trend states; prices $20-$100 / >=$100, stronger premarket dollar participation, and 25-50% realized volatility were materially better than several alternatives. These must be frozen as new hypotheses and evaluated on untouched/walk-forward evidence before use.

**Current disposition:** `CONDITION-GATE / CALIBRATE`. Preserve v1 as a negative unrestricted baseline. Candidate v2 work should prioritize economically coherent long-side/liquidity/volatility/premarket participation hypotheses and explicitly investigate the high noncomparable rate in low-liquidity names.

### 4.2 `b34_opening_range_breakout_15m_v1`

**Status:** observed negative standalone baseline; promising but unstable/time-localized condition evidence; no promotion.

Full DEVELOPMENT evidence:

- opportunities: 16,982,463;
- comparable: 12,626,529; noncomparable: 4,355,934;
- unique sessions: 2,595; unique instruments: 21,481;
- mean return: -0.0454% at 0 bps and -0.5454% at 50 bps;
- mean net-R at 50 bps: -1.7633R; median -0.8009R;
- win rate at 50 bps: 29.28%; profit factor on net-R: 0.121;
- noncomparable rate: 25.65%.

Walk-forward selector evidence:

- test opportunities: 14,168,992; standalone comparable: 10,509,185;
- selected: 3,489; selected comparable: 2,935;
- selected mean net-R at 50 bps: +0.00729R but selected mean percentage return at 50 bps remains negative at about -0.2220%.

The selector's later positive cells were concentrated in 2024 through early 2025 and centered on a large opening range, low reported 20-day median dollar volume, unavailable realized-volatility history, and the frozen setup intensity. Post-result diagnostics indicate much better outcomes for 09:45-10:00 signals than later signals and better behavior in selected price/gap buckets. The `<$1M ADV + volatility unavailable` signature may proxy for new/sparse/low-liquidity instruments and therefore requires an execution-quality audit rather than being accepted as a favorable trading rule.

**Current disposition:** `CONDITION-GATE / CALIBRATE + EXECUTION AUDIT`. Candidate successor research should test signal-time, overnight-gap exhaustion, price/liquidity quality, and opening-range geometry under realistic execution assumptions. Do not hard-code the low-liquidity/unavailable-volatility cell as a permanent edge.

### 4.3 `b34_premarket_relvol_consolidation_v1`

**Status:** weak positive gross signal, cost-sensitive and negative under the frozen conservative cost hurdle; no selector selections; no promotion.

Full DEVELOPMENT evidence:

- opportunities: 313,447;
- comparable: 309,304; noncomparable: 4,143;
- unique sessions: 2,576; unique instruments: 9,204;
- mean return: +0.0472% at 0 bps, -0.0528% at 10 bps, -0.2028% at 25 bps, -0.4529% at 50 bps;
- mean net-R at 50 bps: -0.9858R; median -1.1858R;
- win rate at 50 bps: 32.80%; profit factor on net-R: 0.290;
- noncomparable rate: only 1.32%.

Supported condition cells often showed positive gross return but did not survive the conservative cost hurdle. A notable diagnostic example is large gap + elevated premarket relative volume, where gross and low-cost outcomes improve materially but 50-bps performance remains negative. This is evidence of a possibly real but thin execution-sensitive signal, not evidence that the cost assumption should be weakened.

**Current disposition:** `KEEP FOR R&D / COST-EXECUTION CALIBRATION`. Candidate successors may investigate liquidity, entry timing, breakout confirmation, stop/exit efficiency, and whether higher-quality participation filters can increase gross edge enough to survive conservative executable costs.

### 4.4 `b34_highest_volume_day_style_v1`

**Status:** insufficient evidence, not a valid positive/negative conclusion for conditional qualification.

Full DEVELOPMENT evidence:

- opportunities/comparable: 58/58;
- unique sessions: 58; unique instruments: 58;
- mean return: -0.3367% at 0 bps and -0.8359% at 50 bps;
- mean net-R at 50 bps: -0.8815R;
- win rate at 50 bps: 24.14%.

The frozen minimum is 60 opportunities / 30 sessions / 20 instruments. HVD fails the opportunity-count threshold before any supported condition-cell claim can be made; all HVD condition cells therefore remain unsupported. Small positive cells with one or two observations are explicitly non-evidence.

**Current disposition:** `REDEFINE / INSUFFICIENT EVIDENCE`. Preserve v1 unchanged. A successor should reconsider the practitioner specification under a new fingerprint rather than lowering the evidence threshold after seeing only 58 signals.

## 5. System-level interpretation from B35

B35 does **not** support a claim that any of the four unrestricted strategies is historically validated. It also does not support simply discarding all four. The principal research result is that strategy performance is conditional and temporally unstable: the frozen rolling selector found a tiny number of positive training cells in separated market periods, while most supported cells were conservatively nonpositive and therefore correctly abstained.

The long-term ATLAS design should therefore use a **dynamic specialist router**:

`independent strategy fires -> point-in-time condition vector -> trailing/walk-forward evidence for that strategy/condition -> eligible or abstain -> confluence/ranking -> portfolio/risk`

A strategy should become active only when its current observable condition cell has enough trailing evidence and clears the frozen confidence/cost/robustness gates. Conditions may stop qualifying later. ATLAS must never search live indicators until something agrees with a desired trade.

Candidate successor selector dimensions motivated by B35 diagnostics include **direction** and **signal time** in addition to the existing strategy/regime/realized-volatility/liquidity/setup-intensity hierarchy. Price band, overnight gap, premarket participation, and execution-quality variables also merit controlled testing. These are hypotheses for a successor fingerprint, not retroactive additions to B35.

## 6. Next B35 scientific work

**Implementation status (2026-09-11): retained-artifact robustness COMPLETE; exact targeted perturbation implementation ACTIVE in PR #79.** PR #78 merged as `83d09c424a02883f7d3529a39c62294dcbaf6bc2`; the workstation run completed under robustness fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`. Its 50-bps multiplicity/Deflated-Sharpe result is negative and grants no promotion. The exact minute-path perturbations could not be reconstructed from compact outputs, so PR #79 implements them together in one bounded pass rather than approximating them or rerunning the canonical evidence separately per variant.

PR #79 binds the same 59,768-unit DEVELOPMENT source, split evidence and immutable DEVELOPMENT authorization plus the accepted robustness fingerprint. It requires a new explicit hash-bound targeted authorization, validates every canonical B35 group output/receipt before use, publishes only restartable diagnostic group summaries/receipts, and fails each group closed unless all baseline perturbation values reproduce canonical fired/comparable/noncomparable counts. The pass changes one axis at a time, does not refit the selector, does not rewrite canonical B35 v1, and grants no strategy/selector/PAPER/LIVE authority.

Before freezing any condition-gated v2 rule, complete the remaining preregistered robustness package over the accepted B35 analysis artifacts:

1. BH FDR q=.05 across the declared hypothesis family;
2. Deflated Sharpe diagnostics;
3. PBO/CSCV using 16 partitions where evaluable;
4. deterministic 10,000-draw XNYS-session bootstrap for tail/downside/drawdown uncertainty;
5. losing-streak and P&L-concentration diagnostics;
6. perturbation diagnostics under the frozen B35 perturbation policy where the retained compact artifacts permit exact evaluation; any perturbation that requires a new outcome replay must be separately authorized and labeled rather than approximated;
7. selector comparison versus same-fold standalone strategies, the A34 stable nonlearned long-only reference portfolio where comparable, and cash;
8. record a final B35 research disposition without promotion.

Only after that closeout should ATLAS freeze condition-gated/calibrated successor candidates and the eight-new-family strategy/confluence package under new fingerprints. The future blind remains untouched and may not be opened to rescue or choose these hypotheses.

## 7. Authority

As of this update, historical supported modern alpha remains **zero**. No B35 strategy, selector, condition cell, successor hypothesis, or confluence mechanism is `HISTORICALLY_VALIDATED`, `PAPER_VALIDATED`, or `LIVE_ELIGIBLE`. B35 research reads no consumed-master or future-blind outcomes and grants no provider, broker, PAPER, LIVE, strategy-promotion, or selector-promotion authority.

## 7. Successor research hypotheses accepted for testing

These entries are **approved research hypotheses only**. They are not strategy validation, authority promotion, or permission to reinterpret B35 v1. Exact strategy specifications and fingerprints are frozen only in the successor package after B35 targeted perturbation evidence closes.

### 7.1 `orb_stocks_in_play_5m_v1` — planned / high priority

- Family: Opening Range / opening momentum; it is not independent confluence from other ORB variants.
- Evidence source: `LITERATURE_ANCHORED` idea prior plus independent ATLAS motivation from weak unrestricted ORB and condition-sensitive B35 behavior.
- Mechanism: abnormal same-time opening participation / relative volume + sufficient executable liquidity/volatility -> first-five-minute directional range -> objective breakout -> intraday continuation.
- Must define before performance: universe/liquidity floor, same-time opening-volume baseline, finite activity-selection rule, 5-minute range, breakout confirmation, entry clock, stop/invalidation, exit/EOD flat rule, sizing and cost assumptions.
- Primary question: does activity selection transform broad negative ORB into a viable opening-momentum specialist after realistic costs?

### 7.2 15-minute ORB close + retest challenger — planned / high priority

- Family: Opening Range; versioned challenger to `b34_opening_range_breakout_15m_v1`, not a new economic family.
- Evidence source: `INTERNAL_CHALLENGER` / practitioner-motivated false-break hypothesis.
- Freeze objective close-outside-range, retest distance, retest window, hold/rejection confirmation, entry, stop, exit and no-retest handling before performance.
- Compare directly with v1 for trade-count reduction, MAE, MFE sacrificed by later entry, win rate, net expectancy/net-R, execution quality and condition stability.

### 7.3 Objective session-level failed-break/reclaim — planned / medium-high priority

- Family: Exhaustion reversal / structural failed break.
- Evidence source: `PRACTITIONER_BASELINE` with mechanism support; do not use hidden-liquidity/ICT/SMC claims.
- Initial PIT levels: previous-day high/low and premarket high/low. Opening-range levels may be a later version, not an open-ended target search.
- Freeze normalized breach depth, maximum reclaim time, confirmation, entry, sweep-extreme stop/invalidation and one coherent exit hierarchy before performance.
- Primary question: does breach-then-reclaim of universally observable session levels contain measurable reversal/continuation information after costs?

### 7.4 Shared successor context / routing evidence

Accepted for measurement in the next full historical run, not as automatic hard gates: broad-market directional alignment and volatility state; ticker relative strength/weakness versus SPY over a small preregistered horizon set; bounded higher-timeframe ticker trend; trend maturity/extension; opening/premarket/same-time volume participation and dollar-volume quality; overnight gap; price band; signal time; realized volatility; and execution/liquidity quality. Sector-relative strength waits for a PIT-valid sector map.

Confluence remains a separate layer. Standalone strategy outcomes are preserved first; then incremental evidence is measured across independent families (price structure, participation, market state, relative strength, higher-timeframe state, volatility/liquidity, and later event/fundamental context). RSI/MACD/EMA variants are not counted as independent votes merely because they are numerically different transforms of price.

### 7.5 Deferred/rejected near-term ideas

Fundamentals are deferred for intraday ORB; future swing-conditioning research may ask whether technical setups vary by PIT fundamental/event quality without reopening closed SEC alpha hypotheses. Portfolio daily-loss limits, simultaneous-position competition, concentration, strategy exposure and capital allocation belong to account/PAPER simulation. Anchored VWAP waits for objective anchor semantics. Level-2/order-book, options-flow and GEX require separate historical source authority. Fixed arbitrary stop percentages/R:R, human psychology rules, small discretionary watchlists, Fibonacci and subjective ICT/FVG/order-block terminology are not adopted from the reviewed practitioner material.

### 7.6 Successor laboratory target

The next major Track-B experiment targets **21 economic strategy families**: the ten retained families plus eleven distinct additions. Nearby policy variants, including the two ORB challengers, remain within their economic family for multiplicity and confluence accounting. B35 perturbation results determine which additional gap/premarket/HVD/ORB v2 challengers earn one of the bounded research slots before the successor contract is fingerprinted.

The successor objective is **economically viable condition coverage**, not maximum win rate. Qualification evidence must consider win rate, payoff ratio, net expectancy/net-R, cost decay, drawdown/tail loss, sample/support, fold/year stability, concentration, MFE/MAE, holding time and abstention. No favorable post-result slice validates itself; a frozen successor still requires untouched/prospective evidence before promotion.
