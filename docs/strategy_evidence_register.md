# ATLAS Strategy Evidence Register

**Current as of 2026-09-21 (UTC). This file is a living project document.**

**2026-09-20 reconciliation:** reviewed through the completed Historical News V1 workstation acquisition and the source-integrity-closeout implementation package. The September 20 deterministic-pipeline, news/options storage/source foundation, provider preflight, Historical News V1 acquisition and source-integrity work are data/product research infrastructure only; they do not open, reinterpret, calibrate, close or promote any strategy evidence. The source preflight completed under fingerprint `8fa4fe13856c3e93973867e4503765be4c240c64d73df08ab11ed654985bb134`. Historical News V1 then completed all 141 monthly partitions under acquisition run fingerprint `8076044e7f7c233f98b990dc5595bc4171d1788c143c8391bf173f827ed12c2f`, returning 2,211,606 raw provider records and 2,211,606 month-normalized records while using 1.931 GiB of news storage and leaving 116.81 GiB free. A separate source-integrity closeout contract, fingerprint `99b3b76cadbfff7a7975ce1c9c5b4f2103b2d9e8ec77acae46bba51f80fa8df0`, must PASS before news-derived predictor work begins. After the Hive-schema validator repair, the corrected workstation closeout passed 139/141 partitions and the read-only diagnostic isolated four provider chronology anomalies (three in `2015-07`, one in `2026-08`) where `updated_at < created_at` by 1, 16, 18 and 29 seconds; every normalized row hash-binds to immutable raw provider data, while corpus-wide counts, uniqueness and corpus fingerprint `a5a26ed8b0093db16060c03d5ecb883a03322e61d7fe7217549b678dc1b3a1b0` remain stable. Strict V1 closeout remains FAIL. The successor V2 source-integrity contract `2a2039ba8ca495f1ea04a7ffd0719ccb95021d48917098899c4d93e5599df632` is frozen before predictor access, binds exactly those four anomalies with no generic tolerance, preserves provider fields unchanged, and uses conservative downstream effective PIT `max(created_at, updated_at)`. The target-workstation V2 acceptance then PASSED under acceptance fingerprint `279c13b37eb0a793a3ba821172e8ee226315109a52bca55040bbb3e1dd0a1532`, formally closing Historical News V1 source integrity while preserving strict V1 as FAIL. The Historical Option Reference source-qualification contract is infrastructure only, fingerprint `17a3736f9317f7e403ea08c123aac35fabad0a8b2682bca7450373b797e9d260`. Its target-workstation evidence returned PASS_WITH_LIMITATIONS under evidence fingerprint `120f141089420dcfaf86e1d30203a1517f27815bf1e6b3587976ccb74f4025e3`: identity/cardinality, schema, entitlement, sampled pagination and repeatability passed while chronology/PIT/dynamic-deliverable authority remains explicitly limited. Historical Option Reference V1 acquisition contract `95eb5048336e411cb31c912e2cf8569915aedd42fc9e9f0fd0917f3fb3fe3f23` then failed closed on the target workstation in partition `expired-2014-08` when provider ticker `O:AAL140816C00020000` appeared more than once, invalidating V1's one-row-per-ticker source assumption. V1 remains failed evidence. Historical Option Reference V2 is frozen before retry at `6d0af0b58a66b77c445d7e561d759dfd947e348e994045a1f7cfc16aeb9ccb41`, preserving every provider version in raw storage and selecting normalized structural reference by highest provider correction number with same-highest conflicting payloads failing closed. This is still source infrastructure only: it opens no strategy outcomes and grants no historical option availability, dynamic-deliverable, market-price, predictor, PAPER or LIVE authority. The first V2 workstation retry rebuilt 63 verified V1 raw partitions locally, then failed closed in `expired-2014-06` on `O:AAL140621C00020000` because conflicting provider rows shared highest correction rank `-1` with no explicit correction. V2 remains incomplete and the conflict rule is not relaxed. A read-only targeted diagnostic, fingerprint `f544bb78cb6d61cbd69aa5fd266ee20349b3a977b39cb85e79a0a6a5ec0f9678`, is the next permitted source step and grants no acquisition, predictor, strategy, PAPER or LIVE authority. Its first target-workstation execution completed the repeated structural-list requests, then encountered provider HTTP 404 / `NOT_FOUND` / `Option Ticker not found.` on the first current Contract Overview request. No diagnostic evidence fingerprint was produced because the initial harness incorrectly treated that expected diagnostic outcome as fatal. The implementation is repaired without changing the frozen request contract: that exact 404 is now retained as explicit absence evidence, repeated responses must remain semantically stable, all other 404 forms fail closed, and absent rows cannot compare equal as canonical hashes. A clean rerun remains required before any successor source rule is frozen. No news-derived predictor evidence exists yet. Historical strategy support, dispositions, promotion, PAPER and LIVE authority therefore remain unchanged.

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

**Final robustness component: COMPLETE / NO PROMOTION.** PR #79 merged to `main` as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`; the workstation run completed 482/482 groups and 59,768/59,768 source units with 27 one-axis-at-a-time profiles, targeted fingerprint `078bdc84a18bd6e5ff401ca0a21d4feed61f7b21770a86610a42ee0fdd16374d`, run fingerprint `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69`, and `PASS_EXACT_CANONICAL_OUTCOME_REUSE_ALL_GROUPS`. Consumed-master/future-blind reads, provider calls and broker reads/writes remained zero; selector refit/canonical rewrite/promotion/PAPER/LIVE remained false. No neighboring parameter variant became economically viable. This closes B35 v1 robustness and simple parameter rescue.

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

**Current disposition:** `CONDITION-GATE / CALIBRATE`. Preserve v1 as a negative unrestricted baseline. Targeted perturbations confirm that +1/+2-minute delays and 0.9/1.0/1.1 gap-threshold multipliers improve or worsen only the degree of a still deeply negative result; none is a viable rescue. Admit one mechanism-level long-side quality/condition successor centered on preregistered liquidity, volatility, price and premarket participation, and explicitly investigate the high noncomparable rate in low-liquidity names.

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

**Current disposition:** `CONDITION-GATE / CALIBRATE + EXECUTION AUDIT`. Targeted 14/15/16-minute ranges and +0/+1/+2-minute entries are economically indistinguishable and negative, closing simple timing/range rescue. The bounded successors are Stocks-in-Play 5-minute ORB and an objective 15-minute close/retest confirmation policy. Continue to audit signal time, overnight-gap exhaustion, price/liquidity quality and opening-range geometry; do not hard-code the low-liquidity/unavailable-volatility cell as a permanent edge.

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

**Current disposition:** `KEEP FOR R&D / COST-EXECUTION CALIBRATION`. Targeted delay, rel-vol-threshold and consolidation-width perturbations retain only a thin gross signal; the best observed gross mean is about 4.92 bps and is already negative at 10 bps, while delayed entry worsens the profile. Admit one quality/liquidity/participation successor that attempts to increase gross edge and execution quality without weakening costs or simply choosing the best observed threshold.

### 4.4 `b34_highest_volume_day_style_v1`

**Status:** insufficient evidence, not a valid positive/negative conclusion for conditional qualification.

Full DEVELOPMENT evidence:

- opportunities/comparable: 58/58;
- unique sessions: 58; unique instruments: 58;
- mean return: -0.3367% at 0 bps and -0.8359% at 50 bps;
- mean net-R at 50 bps: -0.8815R;
- win rate at 50 bps: 24.14%.

The frozen minimum is 60 opportunities / 30 sessions / 20 instruments. HVD fails the opportunity-count threshold before any supported condition-cell claim can be made; all HVD condition cells therefore remain unsupported. Small positive cells with one or two observations are explicitly non-evidence.

**Current disposition:** `REDEFINE / INSUFFICIENT EVIDENCE`. Preserve v1 unchanged. Targeted consolidation-width neighbors produced only 55/58/59 signals and remained negative; entry delays also worsened or failed to help. No simple HVD challenger is admitted this cycle. A future successor must genuinely redefine the abnormal-volume mechanism under a new fingerprint rather than lower the evidence threshold or tune width after seeing the result.

## 5. System-level interpretation from B35

B35 does **not** support a claim that any of the four unrestricted strategies is historically validated. It also does not support simply discarding all four. The principal research result is that strategy performance is conditional and temporally unstable: the frozen rolling selector found a tiny number of positive training cells in separated market periods, while most supported cells were conservatively nonpositive and therefore correctly abstained.

The long-term ATLAS design should therefore use a **dynamic specialist router**:

`independent strategy fires -> point-in-time condition vector -> trailing/walk-forward evidence for that strategy/condition -> eligible or abstain -> confluence/ranking -> portfolio/risk`

A strategy should become active only when its current observable condition cell has enough trailing evidence and clears the frozen confidence/cost/robustness gates. Conditions may stop qualifying later. ATLAS must never search live indicators until something agrees with a desired trade.

Candidate successor selector dimensions motivated by B35 diagnostics include **direction** and **signal time** in addition to the existing strategy/regime/realized-volatility/liquidity/setup-intensity hierarchy. Price band, overnight gap, premarket participation, and execution-quality variables also merit controlled testing. These are hypotheses for a successor fingerprint, not retroactive additions to B35.

## 6. B35 closeout and successor handoff

**B35 is CLOSED / NO PROMOTION as of 2026-09-13.** Canonical replay, condition/selector analysis, retained-artifact robustness and the final exact targeted minute perturbations are complete. No B35 v1 replay, selector refit, nearby parameter sweep or cost weakening is justified. The four final research dispositions are recorded above and B35 v1 remains immutable historical evidence.

The successor PRE-OUTCOME contract is now implemented in `packages/strategies/successor_practitioner_lab.py` with human-readable specification `docs/successor_practitioner_lab_preoutcome.md`. It freezes exactly 21 economic families (10 retained + 11 new), four bounded B35 mechanism-level challengers, shared PIT context, walk-forward/support/cost rules, and confluence/multiplicity semantics. Because the admitted B35 challengers were inspired by DEVELOPMENT evidence, they cannot validate themselves on the same DEVELOPMENT data; untouched/prospective evidence remains mandatory before promotion.

The successor family/challenger evaluator and shared PIT feature layer is implemented at the PRE-OUTCOME level without opening broad successor performance. It reuses the accepted daily feature stream once per instrument, adds confirmation-lagged deterministic pivots/pattern geometry, Wilder ADX/DMI14, SPY-relative-strength/market context, and fully closed-minute VWAP/failed-break/ORB/quality evaluators. Duplicate closed-minute timestamps fail closed. These are implementation facts, not performance evidence.

PR #83 merged the portable pre-outcome boundary as `5bcc80d72d1203394525c69ba21f07193b4d6272`: all 28 routes are bound to accepted V2 DEVELOPMENT daily/minute sources, profile-independent grouping and the `0/10/25/50/100` bps diagnostic contract are frozen, and standalone-before-conditioning/confluence artifact order is preregistered. The workstation hash-only preflight then completed **493/493 groups and 59,768 minute units** under runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`. It used 8 workers x 1 DuckDB thread and opened zero strategy outcomes, consumed-master rows, future-blind rows, provider calls, or broker access.

PR #84 is the separate DEVELOPMENT outcome-runner package. It binds outcome access to those exact accepted preflight artifacts; implements next-open 1/5/20-session daily diagnostics and conservative structural-stop/fixed-2R intraday diagnostics; evaluates exact retained daily signal masks plus frozen successor rules; applies a single executable-universe disposition across all 18 daily routes; and preserves the accepted B35 native-plan grouping for all 10 minute routes. Because `research_daily` intentionally excludes ETFs, SPY relative-strength/market context is reconstructed from the already accepted native minute acquisition universe by requiring the exact final regular SPY minute for every DEVELOPMENT session; the native acquisition universe was frozen before the later common-stock research projection, so this does not widen source authority.

The accepted source starts on `2016-01-04`; no earlier warm-up is available or invented. Derived daily groups, SPY benchmark, minute-unit bindings, prepared input manifest, per-group outputs and external standalone artifacts are hash-bound; drift/corruption fails closed. Conditioning/confluence is forbidden until all standalone receipts validate. Any DEVELOPMENT outcome access requires `--authorize-development-outcomes`; the full 493-group run additionally requires `--authorize-full-standalone`. After PR #84 merge, only the fixed 4x1/6x1/8x1 benchmark subset is permitted next. No broad successor DEVELOPMENT result exists yet.

## 7. Authority

As of this 2026-09-13 closeout, historical supported modern alpha remains **zero**. No B35 strategy, selector, condition cell, successor hypothesis, or confluence mechanism is `HISTORICALLY_VALIDATED`, `PAPER_VALIDATED`, or `LIVE_ELIGIBLE`. B35 research reads no consumed-master or future-blind outcomes and grants no provider, broker, PAPER, LIVE, strategy-promotion, or selector-promotion authority.

## 8. Successor research hypotheses accepted for testing

These entries are **approved research hypotheses only**. They are not strategy validation, authority promotion, or permission to reinterpret B35 v1. Exact strategy specifications and fingerprints are frozen only in the successor package after B35 targeted perturbation evidence closes.

### 8.1 `orb_stocks_in_play_5m_v1` — planned / high priority

- Family: Opening Range / opening momentum; it is not independent confluence from other ORB variants.
- Evidence source: `LITERATURE_ANCHORED` idea prior plus independent ATLAS motivation from weak unrestricted ORB and condition-sensitive B35 behavior.
- Mechanism: abnormal same-time opening participation / relative volume + sufficient executable liquidity/volatility -> first-five-minute directional range -> objective breakout -> intraday continuation.
- Must define before performance: universe/liquidity floor, same-time opening-volume baseline, finite activity-selection rule, 5-minute range, breakout confirmation, entry clock, stop/invalidation, exit/EOD flat rule, sizing and cost assumptions.
- Primary question: does activity selection transform broad negative ORB into a viable opening-momentum specialist after realistic costs?

### 8.2 15-minute ORB close + retest challenger — planned / high priority

- Family: Opening Range; versioned challenger to `b34_opening_range_breakout_15m_v1`, not a new economic family.
- Evidence source: `INTERNAL_CHALLENGER` / practitioner-motivated false-break hypothesis.
- Freeze objective close-outside-range, retest distance, retest window, hold/rejection confirmation, entry, stop, exit and no-retest handling before performance.
- Compare directly with v1 for trade-count reduction, MAE, MFE sacrificed by later entry, win rate, net expectancy/net-R, execution quality and condition stability.

### 8.3 Objective session-level failed-break/reclaim — planned / medium-high priority

- Family: Exhaustion reversal / structural failed break.
- Evidence source: `PRACTITIONER_BASELINE` with mechanism support; do not use hidden-liquidity/ICT/SMC claims.
- Initial PIT levels: previous-day high/low and premarket high/low. Opening-range levels may be a later version, not an open-ended target search.
- Freeze normalized breach depth, maximum reclaim time, confirmation, entry, sweep-extreme stop/invalidation and one coherent exit hierarchy before performance.
- Primary question: does breach-then-reclaim of universally observable session levels contain measurable reversal/continuation information after costs?

### 8.4 Shared successor context / routing evidence

Accepted for measurement in the next full historical run, not as automatic hard gates: broad-market directional alignment and volatility state; ticker relative strength/weakness versus SPY over a small preregistered horizon set; bounded higher-timeframe ticker trend; trend maturity/extension; opening/premarket/same-time volume participation and dollar-volume quality; overnight gap; price band; signal time; realized volatility; and execution/liquidity quality. Sector-relative strength waits for a PIT-valid sector map.

Confluence remains a separate layer. Standalone strategy outcomes are preserved first; then incremental evidence is measured across independent families (price structure, participation, market state, relative strength, higher-timeframe state, volatility/liquidity, and later event/fundamental context). RSI/MACD/EMA variants are not counted as independent votes merely because they are numerically different transforms of price.

### 8.5 Deferred/rejected near-term ideas

Fundamentals are deferred for intraday ORB; future swing-conditioning research may ask whether technical setups vary by PIT fundamental/event quality without reopening closed SEC alpha hypotheses. Portfolio daily-loss limits, simultaneous-position competition, concentration, strategy exposure and capital allocation belong to account/PAPER simulation. Anchored VWAP waits for objective anchor semantics. Level-2/order-book, options-flow and GEX require separate historical source authority. Fixed arbitrary stop percentages/R:R, human psychology rules, small discretionary watchlists, Fibonacci and subjective ICT/FVG/order-block terminology are not adopted from the reviewed practitioner material.

### 8.6 Successor laboratory target

The accepted successor PRE-OUTCOME laboratory targets **21 economic strategy families**: the ten retained families plus eleven distinct additions. Nearby policy variants, including the two ORB challengers, remain within their economic family for multiplicity and confluence accounting. B35 perturbation results determine which additional gap/premarket/HVD/ORB v2 challengers earn one of the bounded research slots before the successor contract is fingerprinted.

The successor objective is **economically viable condition coverage**, not maximum win rate. Qualification evidence must consider win rate, payoff ratio, net expectancy/net-R, cost decay, drawdown/tail loss, sample/support, fold/year stability, concentration, MFE/MAE, holding time and abstention. No favorable post-result slice validates itself; a frozen successor still requires untouched/prospective evidence before promotion.

### 8.7 Successor exact implementation and source state — BROAD PERFORMANCE UNOPENED

All eleven new-family rules and the four admitted B35 same-family challengers have deterministic implementations tied to explicit information clocks. Daily families share one PIT computation layer. Intraday rules consume only fully closed left-edge one-minute bars, require complete opening ranges where specified, preserve missing minutes as absence, and reject duplicate timestamps. Shared context covers SPY direction/volatility, 20/63-session ticker relative strength, higher-timeframe trend, ATR-normalized extension, overnight gap, price band, realized volatility and prior-dollar-volume liquidity; intraday participation remains session-derived rather than fabricated.

The source-only gate is accepted: **493/493 groups and 59,768 minute units**, runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c`, source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`. It opened zero historical outcomes. PR #84 adds the separately gated outcome engine, restart-safe parallel runner, exact input/artifact binding, standalone-before-conditioning/confluence boundary and workstation benchmark harness. Repository tests validate mechanics but are not performance evidence.

No broad successor opportunity count, return, win rate, expectancy, drawdown, Sharpe, selector result, confluence result or promotion claim exists yet. The SPY source-only audit is accepted and the next evidence gate is the separately authorized 546-work-group standalone DEVELOPMENT run (64 daily buckets + 482 minute groups); the earlier 493 figure refers only to source verification. The 4x1/6x1/8x1 benchmark remains available as an optional operational performance/equivalence diagnostic and is no longer a scientific prerequisite. Consumed master and future blind remain unavailable, provider/broker/PAPER/LIVE/promotion authority remains zero/false, and no favorable DEVELOPMENT result can self-qualify a DEVELOPMENT-inspired challenger.

## 8. Successor DEVELOPMENT benchmark preparation incident

**Status:** preparation-only source-coverage repair; no successor benchmark performance opened; no promotion.

On 2026-09-13 the first authorized 4x1/6x1/8x1 successor workstation benchmark stopped before profile execution because SPY had no exact scheduled final regular minute in the accepted minute source for session `2019-08-12`. This does not reopen B35 and does not authorize substituting external or later data.

The successor SPY aggregation contract is versioned to use the last observed regular SPY bar from the same session at or before the scheduled final minute with a hard maximum staleness of 5 minutes. The repair records all fallback sessions and staleness, forbids cross-session forward fill and provider calls, and fails closed when same-session coverage exceeds the bound. Because this aggregation fingerprint is bound into the successor run identity and benchmark Parquet hash, all downstream evidence remains attributable to the repaired rule.

Consumed-master rows read: 0. Future-blind rows read: 0. Provider calls: 0. Broker reads/writes: 0/0. PAPER/LIVE/promotion authority: false/false/false. This minute-only preparation path is historical; the accepted source-only audit below supersedes it. Broad 493-group DEVELOPMENT outcomes remain unopened.


### 8.1 Second SPY preparation finding — minute-only close reconstruction retired

A second authorized benchmark attempt on 2026-09-13 again stopped during input preparation, before any 4x1/6x1/8x1 profile executed. The accepted minute source shows `2019-08-12` ending at `19:31:00Z` / 15:31 ET for SPY, **28 minutes stale** versus the scheduled final regular minute. No successor performance was opened.

ATLAS did not widen the minute tolerance to disguise this source gap. The source-only audit retained minute data as primary; only a minute session that is missing, invalid, or >5 minutes stale may be repaired from the exact same-session raw canonical V2 daily SPY close, with daily repair hard-limited to years <=2025. The 2026 native-daily partition remains forbidden. The workstation audit is now **ACCEPTED** under contract fingerprint `912bf7b0ed12a0e4fd7c0382244138573564472e618586677e78c154f7e3cc33` and scientific fingerprint `c575d5df1b7f0d0a7734efc3833329f57f73c953b7b67ccb4ea54d33abb4555c`. It resolves all **2,596** DEVELOPMENT sessions: **2,595** minute-primary and one `NATIVE_RAW_DAILY` repair for `2019-08-12`, whose last accepted minute was `19:31:00Z` and 28.0 minutes stale. Benchmark SHA-256 is `29d7ea9d6a322b4b55af872f7d2e5097777738b209727a487cfd0dcf1306790d`; native-acceptance fingerprint is `6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664`. Consumed-master/future/provider/broker reads remained 0, PAPER/LIVE/promotion remained false, and strategy outcomes remained unopened. PR #87 merged the DuckDB-only Parquet portability repair without changing these scientific identities. Broad successor outcomes are still unopened; the next permitted evidence action is the explicitly authorized full 493-group standalone run, with the 4x1/6x1/8x1 benchmark retained only as an optional diagnostic.

### 8.2 First broad successor run attempt — implementation repair, no accepted result

The first explicitly authorized broad DEVELOPMENT standalone attempt used 8 workers x 1 DuckDB thread and run-contract fingerprint `22a2ace77c4c578c30964ba2a645b822738ef667617f0ef6bffb3192f75582ae`. It exposed the correct outcome-run denominator of **546 work groups = 64 daily + 482 minute**, distinct from the accepted 493-group source-verification accounting. The run did not reach a complete/validated standalone summary: a sparse prior regular session produced `high == low`, and the shared engine passed that non-range into the strict failed-break/reclaim evaluator, which correctly raised `prior regular high/low must be finite positive geometry`.

Disposition: **implementation readiness defect, not strategy evidence**. The economic rule remains unchanged. A repaired engine treats finite, positive, strictly ordered prior regular high/low as a prerequisite for that route. If the immediately prior session does not supply valid geometry, the route is unavailable for that session; no older-session substitution or synthetic range is permitted. The engine contract is bumped so partial artifacts from the failed identity are not reused as repaired evidence. No completed broad performance conclusion, conditioning/confluence result, or promotion claim is admitted from the failed attempt. Parent-process console telemetry is also added for transparent long-run progress without entering scientific hashes.


## 9. Successor standalone and conditioning v1 evidence — 2026-09-15

### 9.1 Accepted standalone identity

The successor practitioner laboratory completed its full DEVELOPMENT standalone run without opening conditioning or confluence during the run:

- 546/546 validated groups = 64 daily + 482 minute groups;
- 54,618,427 standalone opportunity/outcome records;
- scientific run-contract fingerprint `d962d72579996c26485a292469e6483132b413c484b90471aba74b209993cafb`;
- standalone run fingerprint `c22bcb45b1a13dde11854f7ad166ae0abe1810fc0d6ab7371dbdd1165c1006e6`;
- standalone artifact-set fingerprint `4e5d66b8db1b37ac70dcff9e92fc4602bb729f90f18852db59f7e827de5a55d6`;
- 122 validated groups reused and 424 fresh groups completed in 9:00:08 at 47.10 new groups/hour;
- corrupt-reuse invalidations: 0;
- consumed-master rows, future-blind rows, provider calls and broker reads/writes: 0;
- PAPER/LIVE/promotion authority: false/false/false.

This is immutable DEVELOPMENT diagnostic evidence. It does not validate any strategy for PAPER or LIVE.

### 9.2 Frozen conditioning v1 result

PR #94 merged the immutable-artifact conditioning analyzer as `6485a82afd724299a3ffa1a7fde16ef2259d8b5b`. It normalized the exact 54,618,427 standalone records without rereading raw market data and applied the preregistered 504-session training / 1-session embargo / 63-session test / 63-session step design over 33 complete folds. Minimum cell support remained 60 opportunities / 30 sessions / 20 instruments, with deterministic XNYS-session-cluster bootstrap scoring and no supported-negative-cell fallback rescue.

Observed selector result:

- test-eligible opportunities: 45,516,323;
- research-selected: 36,259;
- selected comparable: 36,254;
- abstention among eligible: about 99.92%;
- selected mean primary net return: **-0.313660%**;
- selected mean stress net return: **-0.466303%**;
- positive folds: 11/33; negative folds: 22/33;
- about 75.8% of all selections came from fallback level 1, the most-specific frozen cell;
- daily strategies supplied 35,998/36,259 selections (99.28%);
- only 261 minute selections occurred, all from `orb_15m_close_retest_v2`, and both LONG/SHORT selected means were negative;
- confluence opened: false; selector/strategy promotion: false.

**Interpretation:** conditioning v1 failed as an aggregate research router. The evidence points primarily to lack of persistence/nonstationarity rather than an inability to form supported specific cells. This result does not authorize weakening costs, changing support thresholds after observation, refitting the same selector on the same test outcomes, or opening confluence as a rescue search.

### 9.3 Route-level post-result diagnostics

The following favorable route/direction slices are diagnostic hypotheses discovered after observing test outcomes; they cannot validate themselves on the same data:

- `pract_bollinger_mean_reversion_v1` LONG: 5,516 comparable selections; +0.4536% primary / +0.3032% stress; 21 active folds, 15 positive / 6 negative; largest fold about 21.9% of selections. **Disposition: strongest specialist-development candidate; stability and move-distribution/option-worthiness audit justified.**
- `donchian_breakout_20_volume_short_v1` SHORT: 379 selections; +0.6159% / +0.4664%; 15 active folds, 8 positive / 7 negative; largest-fold share about 29.6%. **Disposition: secondary bounded candidate.**
- `pract_adx_dmi_continuation_v1` LONG: 204 selections; +0.5269% / +0.3764%; 7 active folds, 3 positive / 4 negative; largest-fold share about 38.7%. **Disposition: exploratory candidate.**
- `pract_flag_pennant_v1` SHORT: 191 selections; +0.8811% / +0.7318%; 9 active folds, 7 positive / 2 negative; largest-fold share about 38.7%. **Disposition: exploratory candidate with encouraging sign consistency but limited sample.**
- `rsi_recovery_14_trend_long_v1` LONG: 189 selections; +0.3706% / +0.2203%; 12 active folds, 6 positive / 6 negative; largest-fold share about 31.7%. **Disposition: exploratory candidate.**
- `pract_triangle_breakout_v1` LONG: 57 selections; +0.3271% / +0.1768%; 5 active folds, 2 positive / 3 negative; about 80.7% of selections in one fold. **Disposition: insufficient/concentrated; no positive claim.**

Several high-volume selected routes were materially negative, including EMA pullback LONG, MACD LONG/SHORT, relative-strength momentum LONG/SHORT, ATR-expansion LONG/SHORT, Bollinger mean-reversion SHORT, and multiple breakout/pattern directions. Preserve these outcomes rather than discarding or rewriting the v1 mechanism.

The aggregate post-result set of six positive route/directions contains about 6,536 comparable selections (roughly 18% of all selected trades) and is diagnostically positive, but choosing those six after seeing outcomes is post-selection. It is not a valid historical portfolio or qualification result.

### 9.4 Strategy Development Cycle rule

ATLAS does **not** discard a strategy solely because v1 is weak. Preserve each version and use the result to determine what job, if any, that mechanism is suited for. The standard development cycle is:

`BASELINE -> DIAGNOSE -> TARGETED EXTERNAL RESEARCH -> BOUNDED REVISION -> RETEST -> SPECIALIZE OR PARK -> MOVE ON`

Diagnosis includes condition/regime behavior, direction, trend/relative strength, extension, volatility, liquidity, price band, gap, participation, signal time, setup geometry, entry/confirmation, exit/holding logic, MFE/MAE, stop/target path, costs, false signals, unresolved/no-entry rate, concentration, fold/year stability, and underlying move magnitude/speed. Targeted research should ask why the observed mechanism failed or succeeded and compare credible academic, original-source, broker/exchange/quant, book, practitioner, and community evidence. Popular configurations are candidate evidence, never proof.

“Better” can mean **higher edge** or **more quality opportunities**, provided costs, downside, stability and account contribution remain acceptable. By default admit no more than three materially distinct revision candidates per family per research cycle. Do not densely sweep parameters or tune tiny thresholds on the observed test set. Freeze the revision before performance; the data that inspired it is diagnostic/training evidence only and cannot independently validate it. Parked strategies remain in the library and may be revisited later.

### 9.5 Options-oriented research implication

ATLAS strategy evidence must increasingly report whether a signal is capable of generating moves that are useful for options, not merely whether mean underlying return is positive. Add an option-worthiness profile: probabilities/frequencies of 1/2/3/5% and 1-ATR/2-ATR favorable moves, MFE/MAE, speed/time-to-move, adverse excursion before the favorable move, realized volatility during the expected hold, and return/path distribution tails. A +0.45% mean can hide either many slow small moves or a convex distribution of occasional fast 2-5% moves; these have very different option value.

This is not historical option-P&L evidence. Actual option qualification requires separately accepted PIT historical option-chain/quote/IV data and contract-level replay. The future trade-expression layer should support `OPTIONS_ONLY`, `STOCKS_ONLY`, `OPTIONS_PREFERRED`, and `STOCKS_PREFERRED`, all behind a universal economic actionability gate. The underlying forecast supplies move magnitude/time/probability; option construction then evaluates delta/gamma/theta/vega, IV/skew/term structure, strike/DTE/moneyness, rates/dividends/early exercise, spread/liquidity/open interest, events, scenario P&L and probability of profit. If option economics fail but the underlying stock remains attractive, stock may remain eligible in modes that permit it. Black-Scholes-Merton is a reference/scenario model; “undervalued” means model-relative evidence only until confirmed against the observable option surface and executable market.

### 9.6 Authority and next evidence action

Historical supported modern alpha remains zero. No successor strategy, selector, post-result slice, option-worthiness metric, or future instrument preference is `HISTORICALLY_VALIDATED`, `PAPER_VALIDATED`, or `LIVE_ELIGIBLE`. The consumed master remains unavailable and the future blind remains unopened.

Next research actions: close conditioning v1 without promotion; derive move-magnitude/speed/option-worthiness diagnostics from retained immutable artifacts where the existing data supports them; inventory implemented versus partial/placeholder strategy families; broaden baseline coverage; perform targeted external failure-mode research; freeze only a bounded set of materially different revisions; and reserve confluence for a later preregistered test after underlying strategy/router evidence justifies it.


### 9.7 Selected daily five-session path closeout and minute-path preregistration — 2026-09-15

**Daily path state: COMPLETE / DESCRIPTIVE / NO PROMOTION.** Contract fingerprint `14d3598599e21a8603f95933368c9bdfaf6480577a51064d6110706a9682d1ca`; analysis fingerprint `e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20`. The run validated the accepted retained conditioning/option-worthiness lineage, then evaluated exactly **35,995 selected comparable daily DEVELOPMENT opportunities**. Source lineage was 11 accepted daily partitions / 2,706,154 manifest rows; the optimized implementation projected 1,015 selected instruments, 2,117,873 daily rows and 184,478 targeted rows, then produced all 35,995 five-session paths and 143,980 threshold rows without reading the consumed master or future blind.

Frozen semantics: entry is next regular-session open; horizon is five instrument trading sessions; thresholds are 1%, 2%, 3%, and 5% in favorable and adverse directions; first-touch resolution is session-level; a bar touching both sides is `SAME_SESSION_COLLISION_UNORDERED`. These results are post-result diagnostic evidence and cannot validate a strategy version that was selected or redesigned from them.

Selected positive specialist diagnostics:

- `pract_bollinger_mean_reversion_v1` LONG: n=5,516; mean five-session gross +0.55%; MFE5 5.19%; adverse excursion 4.93%; favorable hit 73.11% / favorable-before-adverse 43.49% at 2%; favorable hit 59.72% / favorable-before-adverse 43.65% at 3%. Broadest current specialist hypothesis; no validation.
- `pract_flag_pennant_v1` SHORT: n=191; +0.98%; MFE5 5.78%; adverse excursion 4.60%; 2% hit 74.35% / favorable-before-adverse 54.45%; 3% hit 61.26% / favorable-before-adverse 50.79%. Cleaner path signal but limited sample and prior fold concentration remain material.
- `donchian_breakout_20_volume_short_v1` SHORT: n=379; +0.72%; MFE5 4.98%; adverse excursion 4.40%; 2% favorable-before-adverse 42.22%; 3% 41.16%. Secondary bounded hypothesis.
- `pract_adx_dmi_continuation_v1` LONG: n=204; +0.63%; MFE5 5.78%; adverse excursion 4.92%; 2% favorable-before-adverse 43.14%; 3% 42.16%. Exploratory only.
- `rsi_recovery_14_trend_long_v1` LONG: n=189; +0.47%; MFE5 4.04%; adverse excursion 3.68%; 2% favorable-before-adverse 49.74%; 3% 48.68%. Smaller sample but relatively cleaner adverse path.
- `pract_triangle_breakout_v1` LONG: n=57; +0.43%; MFE5 6.33%; adverse excursion 6.26%; insufficient and highly concentrated despite positive endpoint mean.

The dominant cross-route finding is not merely move magnitude: many negative routes also reach 2-3% favorable excursion within five sessions. Favorable-before-adverse rates are commonly only ~30-50%, so **speed/order/adverse path and exit construction are binding research variables**. This supports the options-aware architecture in which ATLAS forecasts an underlying move distribution and timing, then separately tests whether a specific option contract can monetize that path after theta, IV/vega, delta/gamma, spread/liquidity, strike/DTE and event risks. Endpoint movement is not option P&L.

**Capture-ratio caution:** the arithmetic mean of per-opportunity `gross_return_5 / MFE5` is unstable when MFE5 is near zero and yielded extreme negative aggregates. It must not be used to rank routes or justify a revision. The retained median capture statistic is the operator-facing summary; raw return, MFE, adverse excursion, give-back and first-touch distributions remain the primary evidence.

**Minute-path state: PREREGISTERED BEFORE RESULTS.** Population is exactly the already-selected comparable minute opportunities: expected 259, all `orb_15m_close_retest_v2`. The frozen minute package measures retained actual entry through retained actual exit at 1/2/3/5% thresholds. Pre-exit minute bars may establish favorable/adverse touches; if both sides first touch in one minute, the class is `SAME_MINUTE_COLLISION_UNORDERED`. The actual exit minute does **not** use that bar's high/low because those extrema may occur after exit; only the retained realized gross return is applied on the terminal minute. Tick order is never inferred. Source access reuses the accepted serialized successor native-unit bindings, verifies exact checkpoint/path/SHA identity for only needed symbol/month units, and queries only selected symbol/session paths. Historical option P&L, Greeks/IV path, confluence, promotion and trading authority remain closed.

Authority after the daily closeout is unchanged: consumed-master rows 0; future-blind rows 0; provider calls 0; broker reads/writes 0/0; confluence false; strategy/selector promotion false; PAPER/LIVE false; option-trading authority false.

## 10. Successor option-worthiness diagnostic — PRE-RUN implementation

**Evidence state: IMPLEMENTED / EMPIRICAL AGGREGATES NOT YET OPENED BY THIS PACKAGE.** The successor option-worthiness contract binds the accepted standalone and conditioning-v1 artifacts and derives descriptive underlying-move evidence without a raw-market reread. Its frozen move thresholds are 1%, 2%, 3%, and 5%. It reports all-comparable, walk-forward-test, and conditioning-selected populations separately, with route/direction return distributions, MFE/MAE distributions, favorable/adverse threshold frequencies, daily 1/5/20-session diagnostics, intraday holding-time diagnostics, selected-fold stability/concentration, and the exact observed 28-route / 21-economic-family implementation inventory. Daily retained MFE/MAE is a 20-session excursion window and is labeled as such; intraday MFE/MAE is entry-to-actual-exit. No five-session MFE threshold frequency is claimed from the 20-session extrema.

This is post-result DEVELOPMENT diagnosis. It creates no composite option-worthiness score and no new selector. Exact time to a 1/2/3/5% favorable move is unavailable because retained MFE stores magnitude but not the threshold-crossing timestamp. Entry ATR magnitude is not retained in the conditioning artifacts, so 1ATR/2ATR move frequencies are also unavailable. Complete MFE-versus-MAE path ordering, hold-period realized-volatility paths, historical option P&L, Greeks, IV surface, skew, term structure, and executable contract economics require future source/path packages and may not be inferred here.

Authority remains unchanged: consumed-master/future/provider/broker reads are zero; PAPER/LIVE/strategy/selector/option-trading authority is false; confluence remains unopened. A favorable diagnostic may motivate a bounded versioned research candidate under the Strategy Development Cycle, but cannot validate itself on the DEVELOPMENT evidence that revealed it.

### 8.9 Retained option-worthiness closeout and selected daily path preregistration — 2026-09-15

The DEVELOPMENT-only retained-artifact option-worthiness run completed with contract fingerprint `caedb97b7031c70e0aeec1f7fbde6d949b2ab22cd39529876b82d1228fcf8b11` and analysis fingerprint `6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3`. Scope was 34,273,432 comparable DEVELOPMENT opportunities, 28,825,473 walk-forward-test comparable opportunities, and 36,254 walk-forward-selected comparable opportunities across the authoritative 28 routes / 21 economic families. No consumed-master/future/provider/broker/PAPER/LIVE/promotion/confluence/option authority was opened.

Interpretation is deliberately limited: daily MFE/MAE in the retained standalone evidence is `THROUGH_20_SESSIONS`, while the primary daily return is a separate five-session outcome. The resulting 1%/2%/3%/5% MFE rates are therefore **eventual-excursion diagnostics, not five-session hit rates or option-profit evidence**. Their high values even on negative-expectancy routes indicate that timing, adverse path, exit capture, and regime persistence require diagnosis before parameter changes. No route disposition is upgraded by these excursion rates.

Before opening any five-session path results, the next diagnostic is frozen as `atlas-successor-selected-daily-path-v1-five-session-first-touch-descriptive`. Population is exactly the already-selected comparable daily opportunities (expected 35,995). Entry remains next regular-session open. Horizon is five instrument trading sessions. Thresholds are frozen at 1%, 2%, 3%, and 5% in both favorable and adverse directions. Report first-touch session, favorable/adverse ordering at session resolution, MFE, adverse excursion magnitude, five-session close return, exit-capture ratio, and peak give-back. If both sides touch inside the same daily bar, classify `SAME_SESSION_COLLISION_UNORDERED`; do not infer intraday order. The 259 selected ORB minute opportunities are excluded and deferred to a separate minute-path diagnostic. These are post-result DEVELOPMENT diagnostics only and can form bounded successor hypotheses, never validation or promotion.

## 10. Exact-minute ORB closeout and literature-fidelity v2 preregistration — 2026-09-15

### 10.1 Exact-minute selected-path result

The frozen selected-minute contract reopened exactly 259 already-selected/comparable `orb_15m_close_retest_v2` DEVELOPMENT opportunities spanning 208 symbols. It verified 218 serialized native minute-unit bindings by exact path and SHA-256 before reading 55,581 retained entry-to-exit minute bars. Analysis fingerprint: `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`.

First-touch resolution is minute-bar timestamp. If favorable and adverse thresholds are both touched in the same minute, their order remains unresolved. Exit-bar high/low extremes are excluded so post-exit movement cannot contaminate path evidence.

- LONG (`n=157`): gross -0.71%; primary -1.20%; stress -1.70%; median hold 336m; MFE 8.82%; MAE 7.78%. Favorable-threshold hit / favorable-first / median time: 1% = 89.17% / 48.41% / 1m; 2% = 78.34% / 46.50% / 6m; 3% = 72.61% / 42.04% / 12m; 5% = 54.78% / 40.76% / 16.5m.
- SHORT (`n=102`): gross -0.01%; primary -0.51%; stress -1.01%; median hold 359m; MFE 3.85%; MAE 3.88%. Favorable-threshold hit / favorable-first / median time: 1% = 74.51% / 42.16% / 7.5m; 2% = 59.80% / 41.18% / 20m; 3% = 50.98% / 36.27% / 26.5m; 5% = 31.37% / 29.41% / 31m.

**Diagnosis:** movement magnitude is not the binding failure. The selected retest route frequently experiences substantial movement, but adverse movement wins the race more often than favorable movement at every symmetric threshold. LONG is highly two-sided/noisy; SHORT is approximately gross-flat and negative after realistic costs. Directional leverage or option convexity does not repair an entry whose path ordering is wrong. No historical option P&L is claimed.

### 10.2 Targeted external research and preserved v1

Failure-specific research identified Zarattini, Barbon & Aziz, *A Profitable Day Trading Strategy For The U.S. Equity Market* (Swiss Finance Institute Research Paper 24-98; SSRN 4729284). Their U.S.-stock study focuses on a five-minute ORB and reports the main improvement from restricting trades to unusually active "Stocks in Play" using first-five-minute relative volume and a daily top-20 rank. The studied rule uses first-five-minute candle direction, a direction-specific stop entry at the range boundary, a 10% ATR14 stop, and EOD exit.

ATLAS already has `orb_stocks_in_play_5m_v1`, but that frozen challenger is materially different: it uses a 20-session median opening-volume proxy, a 2.0 relative-volume threshold, a prior-dollar-volume quality gate, and the first closing breakout in either direction. That prior version remains immutable. It is not renamed or retroactively treated as the published design.

### 10.3 `orb_stocks_in_play_5m_literature_v2` frozen hypothesis

A separate version is preregistered before any v2 outcome is opened. Contract fingerprint: `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`.

Frozen rules:
- opening range = regular-session 09:30 through 09:34 ET, known at 09:35;
- opening price > $5;
- prior 14-session average daily share volume >= 1,000,000 shares;
- prior ATR14 > $0.50;
- current first-five-minute volume / prior 14-session mean first-five-minute volume >= 1.0;
- daily cross-sectional relative-volume rank <= 20;
- first-five-minute candle positive -> LONG only; negative -> SHORT only; doji -> abstain;
- stop entry at the corresponding opening-range high/low after 09:35;
- a gap through the stop fills at the first post-09:35 minute open rather than receiving the stale stop price;
- stop loss = 0.10 x prior ATR14 from executed entry;
- if not stopped, exit at the last regular-session bar;
- same-minute entry-and-stop ordering is unresolved/noncomparable unless a later pre-outcome contract explicitly chooses a conservative information-safe convention;
- one trade maximum per symbol/session;
- ATLAS costs remain 0/10/25/50/100 bps, with 50/100 bps primary/stress for intraday research;
- 1/2/3/5% exact-minute path thresholds remain descriptive option-worthiness inputs only.

### 10.4 Scientific status and authority

This v2 is intentionally a bounded mechanistic revision, not a sweep of opening-range lengths, relative-volume cutoffs, ATR stops, or exits. The internal motivation is post-result DEVELOPMENT evidence, while the external paper itself studies 2016-2023 and therefore overlaps ATLAS DEVELOPMENT. A positive DEVELOPMENT result can support specialization/research continuation but **cannot independently validate or promote the strategy**. Untouched/prospective evidence is required later.

Consumed-master reads = 0; future-blind reads = 0; provider reads = 0; broker reads/writes = 0. Strategy/selector promotion, confluence, PAPER, LIVE, and option-trading authority all remain false.

## 10. ORB exact-minute diagnosis and literature-fidelity v2 preregistration — 2026-09-15

### 10.1 Retained 15-minute ORB path closeout

`orb_15m_close_retest_v2` selected-minute path analysis fingerprint: `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`.

- 259 selected/comparable opportunities; 208 symbols; 218 verified native units; 55,581 minute bars.
- LONG: n=157, gross -0.71%, primary 50-bps -1.20%, stress 100-bps -1.70%, mean MFE 8.82%, mean MAE 7.78%.
- SHORT: n=102, gross -0.01%, primary -0.51%, stress -1.01%, mean MFE 3.85%, mean MAE 3.88%.
- favorable-before-adverse frequency was below 50% at all 1/2/3/5% thresholds for both directions.
- historical option P&L was not claimed.

Disposition: this is evidence of a path-ordering/direction problem, not evidence that the underlying names fail to move. Do not rescue the retained route with leverage or an unrestricted parameter sweep.

### 10.2 Separate literature-fidelity v2 hypothesis

Policy: `orb_stocks_in_play_5m_literature_v2`.

Base strategy contract fingerprint: `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`.

Frozen mechanism: five-minute opening range; opening price > $5; prior-14-session average daily volume >= 1,000,000 shares; prior ATR14 > $0.50; exact first-five-minute relative volume >= 1.0 versus the prior 14 sessions; deterministic top-20 daily relative-volume rank; opening-candle direction with doji abstention; range-boundary stop entry; adverse gap-through fill; 0.10xATR14 stop; end-of-day exit; 0/10/25/50/100-bps cost grid with 50/100 bps primary/stress.

### 10.3 DEVELOPMENT runner preregistration

DEVELOPMENT analysis contract fingerprint: `87ee4ff703f8040d88c22147444aa992d196ab49be91dc749e3035e3c15e739b`.

A pre-outcome source-semantics review corrected the runner before any historical v2 result was observed. The accepted V2 daily generation preserves provider-native split-adjusted volume and does not authorize reconstructing raw volume from the inverse price factor. Accordingly, the frozen runner reconstructs raw daily OHLC only for ATR14 and uses provider-native daily volume exactly as supplied for the liquidity gate. Opening relative-volume history requires the exact previous 14 XNYS sessions to each provide a complete five-minute opening snapshot; older observations cannot bridge a missing session.

The implementation uses a broad-cheap/narrow-expensive funnel: only 09:30-09:34 ET data are read broadly, the cross-sectional filter/rank is applied, and full-session minute paths are opened only for selected directional candidates. Group artifacts and receipts are SHA-bound and restart-safe; runtime worker count is excluded from the scientific identity.

### 10.4 Current evidence status

**Historical v2 outcomes: UNOPENED.** No v2 performance number exists yet in the accepted evidence register. The next permitted action after code acceptance is the explicit gated DEVELOPMENT run. Because this hypothesis was motivated by post-result DEVELOPMENT evidence and external research overlapping the DEVELOPMENT period, the resulting DEVELOPMENT distribution cannot self-validate or promote the strategy. Consumed master/future/provider/broker/PAPER/LIVE/promotion/confluence/option-trading authority remain zero/false. Any encouraging result must advance to untouched/prospective evidence rather than reusing the consumed master.


## 11. Literature-fidelity 5-minute ORB v2 DEVELOPMENT closeout — 2026-09-16

Policy: `orb_stocks_in_play_5m_literature_v2`  
Strategy contract: `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`  
DEVELOPMENT contract: `87ee4ff703f8040d88c22147444aa992d196ab49be91dc749e3035e3c15e739b`  
Completed analysis fingerprint: `cc6c34b18479aa76558e3c73cbc17ae75d85dd2c7b45d3806a8ac00d17b3a035`  
Disposition: `COMPLETE_DEVELOPMENT_DIAGNOSTIC / NO_PROMOTION / PARKED_COST_SENSITIVE`

### 11.1 Population and economics

The frozen run completed 482/482 opening groups and 261/261 selected-path groups with 8 workers x 1 DuckDB thread. It produced 4,957,662 opening snapshots, 62,516 eligible rank-pool rows and 40,606 top-20 selections. After 261 doji abstentions there were 40,345 directional candidates; 33,773 entered, 23,412 were comparable, 6,572 never entered and 10,361 were same-minute entry/stop unordered.

Aggregate comparable mean: **+0.12% gross / -0.38% primary 50 bps / -0.88% stress 100 bps**. LONG: n=11,778 comparable, +0.13% gross / +0.03% at 10 bps / -0.12% at 25 bps / -0.37% at 50 bps / -0.87% at 100 bps. SHORT: n=11,634, +0.11% / +0.01% / -0.14% / -0.39% / -0.89%. Mean MFE/MAE was 1.27%/0.41%; median comparable holding time was 12 minutes in both directions.

### 11.2 Path and option-worthiness evidence

Favorable underlying threshold-hit rates were LONG 34.31% / 18.22% / 11.00% / 4.71% and SHORT 34.64% / 20.17% / 12.49% / 5.51% at 1% / 2% / 3% / 5%. Median favorable time was 6/17/29/48 minutes LONG and 6/17/32/70 minutes SHORT. These are underlying path diagnostics only. Historical option P&L remains unavailable and unclaimed.

### 11.3 Diagnosis

- The strategy contains a small gross directional edge in DEVELOPMENT but is too cost-sensitive to clear the frozen ATLAS conservative actionability assumptions. Both directions are already negative by 25 bps.
- LONG and SHORT are economically similar, so there is no evidence-supported post-result direction carve-out.
- 10,361 same-minute entry/stop collisions are ~30.68% of entered cases. The frozen 0.10xATR14 stop is tight relative to immediate minute noise, but changing it now would define a new version rather than repair v2.
- Selected names often make fast 1-3% moves, preserving option-worthiness research interest, but move magnitude alone does not establish executable stock or option expectancy.

### 11.4 Disposition and authority

Preserve v2 exactly and move on. Do not sweep opening-range length, relative-volume threshold, rank count, ATR stop, entry delay or exit on the same DEVELOPMENT evidence. A future materially distinct v3 requires targeted external research, preregistration and untouched/new/prospective evidence. Consumed-master reads = 0; future-blind reads = 0; provider reads = 0; broker reads/writes = 0. Promotion, confluence, PAPER, LIVE and option-trading authority remain false. The immutable detailed record is `docs/research/orb_stocks_in_play_literature_v2_development_closeout_20260916.md`.

## 12. Recurrent successor portfolio outcome replay — preregistered 2026-09-19

Contract: `atlas-recurrent-successor-outcome-replay-v1-walk-forward-selector-long-only`.

This package does **not** create or upgrade strategy evidence. It is a portfolio/account diagnostic that reuses the already accepted successor DEVELOPMENT standalone and conditioning artifacts. The accepted walk-forward router remains unchanged: 504 training sessions, one-session embargo, 63-session test windows, and `research_eligible` only when the frozen training-cell lower-confidence score is strictly positive.

For each selected comparable test opportunity, the recurrent decision adapter constructs its underlying return distribution only from the corresponding fold's prior training cell. The held-out opportunity's realized return is not available to its forecast, admission, sizing, reservation, or capital-competition decision. The accepted held-out outcome is revealed only at its chronological exit event and is used to settle the recurrent position on a normalized price basis.

V1 is intentionally LONG-stock only because the accepted recurrent funding model has no short borrow/locate/collateral semantics. Selected SHORT rows remain visible in counts and attribution but cannot be converted into simulated long trades. Daily outcomes retain the frozen five-session / 10-bps primary convention; intraday outcomes retain the accepted entry/exit path and 50-bps primary convention. Every completed recurrent trade must numerically reproduce its accepted primary net return after the split entry/exit costs or the replay fails closed.

This mode is **OUTCOME_REPLAY_DIAGNOSTIC**, not a new backtest of exit rules. It does not yet reopen historical bars and therefore cannot answer whether changing STOP/TARGET/TIME mechanics would improve a strategy. That stricter bar-level campaign is a later separately versioned research package.

**Evidence status:** implementation/preregistration only; no workstation portfolio result has been opened yet. Historical supported modern alpha remains zero. No strategy, selector, family, or condition cell receives historical validation, promotion, PAPER, LIVE, confluence, or option-trading authority from this package. Consumed-master/future-blind/provider/broker/order authority remains zero/false.

## 13. First recurrent successor portfolio outcome replay result — 2026-09-19

Contract fingerprint:
`99c3b32b1905db3204646bac302a5b6836e843cbfe73d7647da9a84b8b879452`.

Run fingerprint:
`2096fe4bc3babdd80c667a0548ab24a861a586bd08f880237744f11b23378166`.

Scope: `2025-01-01..2025-12-31` successor DEVELOPMENT signals, starting book
equity $100,000.

Observed portfolio diagnostic:

- selected comparable opportunities: 4,685;
- supported LONG: 3,650;
- reported-only SHORT: 1,035;
- admitted/completed LONG positions: 439 / 439;
- final book equity: $101,647.15;
- total return: +1.6472%;
- maximum realized/book-equity drawdown: -20.9896%;
- peak active/reserved slots: 10;
- rejected for max positions per family: 2,429;
- rejected for max total open positions: 458;
- rejected for insufficient capital: 262;
- rejected because ticker was already active/reserved: 62.

The 3,211 rejection count exactly reconciles the supported LONG selections not admitted.
Only about 12.0% of supported LONG selections entered the simulated account. The
three-position-per-family cap was the dominant constraint, rejecting about 66.5% of all
supported LONG selections and about 75.6% of rejected LONG selections.

**Interpretation:** the endpoint is positive, but the return is small relative to the
observed realized/book-equity drawdown, and the result is heavily shaped by finite
capital and family-level competition. It cannot be treated as evidence that the
underlying strategy set is production-ready. It also excludes SHORT selections and
uses accepted terminal outcomes rather than bar-driven recurrent STOP/TARGET/TIME exit
logic.

**Disposition:** `COMPLETE_DEVELOPMENT_PORTFOLIO_DIAGNOSTIC / NO_PROMOTION`.

No strategy, family, selector, sizing rule, family-cap rule, or exit policy is promoted
or retuned by this result. Historical supported modern alpha remains zero. The next
permitted simulator research package is a separately preregistered bar-level
DEVELOPMENT campaign using accepted historical bars and frozen decision-bound
STOP/TARGET/TIME mechanics. Consumed-master/future-blind/provider/broker/order/PAPER/
LIVE/promotion/confluence authority remain zero/false.

## 14. Recurrent daily exit-policy sweep preregistration — 2026-09-19

Contract: `atlas-recurrent-successor-daily-exit-policy-sweep-v1`.

Purpose: bounded post-result DEVELOPMENT tuning of daily LONG exit construction while
holding the accepted successor selector and recurrent portfolio constraints fixed.

Frozen grid: STOP and TARGET each take exactly one of 1%, 2%, 3%, or 5%, producing
16 policy combinations. TIME closes at the fifth entry-session regular close. Entry
is next regular-session open. Costs remain 10 bps round trip. Same-session STOP+TARGET
collision is resolved to STOP. Adverse stop gaps fill at the worse open; favorable
target gaps receive no positive slippage beyond target.

The current opportunity's outcome cannot inform its decision forecast. Return
distribution evidence remains the accepted fold-training cell; threshold probabilities
and favorable timing are sourced only from strictly earlier selected daily folds with
at least 30 prior cases. Actual execution and marks use only the accepted hash-bound
Alpaca SIP V2 DEVELOPMENT daily source for selected instruments.

The recurrent account remains the sole portfolio truth. Compounding remains enabled at
10% current book equity per position with max 10 active/reserved positions, max 3 per
economic family, and one active/reserved ticker. Daily historical closes are published
through the recurrent marked-account surface to produce marked-equity drawdown.

This sweep is hypothesis generation, not validation. The highest 2025 return is not
automatically selected or promoted. Any bounded candidate must be carried unchanged
into other DEVELOPMENT regimes and then untouched/prospective evidence. SHORT funding,
portfolio-cap tuning, confluence, PAPER and LIVE remain separate gates. Consumed-master,
future-blind, provider, broker and order authority remain zero/false.

## 15. 2025 recurrent daily exit sweep result and candidate freeze — 2026-09-19

Run fingerprint:
`2726c3a644ac22ed3238adf5b03e978152eaa50a5d0e91fc937716309f0db9f4`.

Scope: selected daily LONG DEVELOPMENT opportunities with signal sessions
`2025-01-01..2025-12-31`; 3,520 usable cases.

Observed frozen-grid results:

- 2% STOP / 5% TARGET: +1.45% endpoint return; -9.20% maximum marked-equity
  drawdown; -9.06% maximum book-equity drawdown; 649 completed positions;
  397 STOP / 160 TARGET / 92 TIME.
- 3% STOP / 5% TARGET: +0.46% endpoint return; -13.11% maximum marked-equity
  drawdown; -13.26% maximum book-equity drawdown; 575 completed positions;
  286 STOP / 169 TARGET / 120 TIME.
- all other 14 preregistered STOP/TARGET combinations finished negative in 2025.

Interpretation is limited to post-result DEVELOPMENT tuning. The two positive policies
are **candidates**, not validated strategies or promoted account rules. The earlier
outcome-replay result is not a direct comparator because its eligible population and
exit mechanics differ.

Candidate set frozen before forward confirmation:

1. 2% STOP / 5% TARGET;
2. 3% STOP / 5% TARGET.

Primary confirmation interval:
`2026-01-01..2026-04-30`, which is chronologically after the 2025 tuning interval
while remaining inside the accepted DEVELOPMENT boundary.

The confirmation contract binds the exact 2025 sweep run fingerprint and refuses to
change candidate membership based on the 2026 outcome. After forward confirmation,
earlier calendar/regime checks may assess robustness but are explicitly retrospective
for exit-policy selection.

**Disposition:** `COMPLETE_2025_EXIT_TUNING_DIAGNOSTIC / TWO_CANDIDATES_FROZEN /
NO_PROMOTION`.

Historical supported modern alpha remains zero. No selector, strategy, exit policy,
portfolio rule, PAPER or LIVE authority is promoted by this result.

## 16. 2026 daily exit forward confirmation — failed — 2026-09-19

Run fingerprint:
`bd8e1fd32d2c34e8699e6e243e851c936c475e0d5b16fc4f6047d5f02e40f210`.

Scope: selected daily LONG DEVELOPMENT opportunities with signal sessions
`2026-01-01..2026-04-30`; 1,831 usable cases.

Frozen-candidate results:

- 2% STOP / 5% TARGET: -6.38% endpoint return; -9.88% maximum marked-equity
  drawdown; -9.93% maximum book-equity drawdown; 282 completed positions;
  190 STOP / 66 TARGET / 26 TIME.
- 3% STOP / 5% TARGET: -6.97% endpoint return; -10.42% maximum marked-equity
  drawdown; -10.45% maximum book-equity drawdown; 236 completed positions;
  130 STOP / 62 TARGET / 44 TIME.

Both candidates failed the first chronologically later confirmation interval. This
invalidates promotion of either static geometry as a general exit policy. No parameter
is retuned from the 2026 outcome.

A retrospective regime-robustness contract now freezes annual 2018–2024 checks with
the two candidate geometries unchanged and equal starting equity per year. Those
checks are descriptive: they may identify regime dependence but cannot convert the
failed forward confirmation into validation.

The next research direction is Dynamic Exit V1: choose decision-bound STOP/TARGET/TIME
geometry using only information available at entry, with a bounded action set and
point-in-time regime/volatility/path evidence. Any adaptive in-trade logic requires a
separate version and finer intraday path evidence.

**Disposition:** `FAILED_FORWARD_STATIC_EXIT_CONFIRMATION /
RETROSPECTIVE_REGIME_MAP_NEXT / NO_PROMOTION`.

Historical supported modern alpha remains zero. No selector, strategy, exit policy,
portfolio rule, PAPER or LIVE authority is promoted by this result.

## 17. Static daily exit regime robustness closeout — 2026-09-20

Run fingerprint:
`60989a10985973bff48d3d2a82a633282b62e664f22f5c3fac4c35bfee380ede`.

Annual recurrent-account results with equal $100,000 starting equity per regime:

| Year | 2%/5% return | 2%/5% marked DD | 3%/5% return | 3%/5% marked DD |
| --- | ---: | ---: | ---: | ---: |
| 2018 | -15.75% | -21.71% | -8.98% | -19.18% |
| 2019 | +6.60% | -5.54% | +6.64% | -5.25% |
| 2020 | -8.71% | -16.54% | -11.18% | -22.42% |
| 2021 | -21.19% | -24.45% | -18.76% | -25.41% |
| 2022 | -24.87% | -25.32% | -27.74% | -28.38% |
| 2023 | -9.79% | -12.61% | -9.24% | -13.53% |
| 2024 | -11.00% | -13.48% | -16.30% | -16.83% |

2%/5% was positive in 1/7 years, with median annual return -11.00% and worst annual
return -24.87%. 3%/5% was positive in 1/7 years, with median annual return -11.18%
and worst annual return -27.74%. Only 2019 was positive for both.

These results, combined with the failed 2026 forward confirmation, reject both fixed
geometries as robust universal exit policies. Retrospective regime evidence does not
rescue either candidate.

**Disposition:** `STATIC_EXIT_UNIVERSAL_RULE_REJECTED / DYNAMIC_EXIT_V1_NEXT /
NO_PROMOTION`.

### Dynamic Exit V1 preregistration

Dynamic Exit V1 is a DEVELOPMENT-only walk-forward selector diagnostic. Frozen actions:
1%/2%, 1%/3%, 1%/5%, 2%/3%, 2%/5%, 3%/5%, plus ABSTAIN. V1 keeps the five-session
time horizon fixed.

For each current case, training evidence is restricted to the previous eight completed
walk-forward folds. Current-fold outcomes and the current opportunity's future bars
are forbidden from selection. Supported context cells require >=60 prior cases,
>=30 unique sessions, and >=20 unique instruments.

The context fallback hierarchy is:

1. policy + market volatility + higher-timeframe trend + realized-volatility bucket +
   market-direction alignment;
2. policy + market volatility + higher-timeframe trend + realized-volatility bucket;
3. policy + market volatility + higher-timeframe trend;
4. policy + market volatility;
5. policy.

Every action is evaluated using prior realized net returns under the same conservative
daily bar semantics and frozen 10-bps round-trip execution cost. The robust score is
an equal-weight prior-session mean minus 1.645 standard errors. The highest positive
lower-confidence-bound action is selected only when its mean trade return is also
positive. Otherwise ATLAS abstains.

This first package does not calculate portfolio return, capital competition, or
compounding. Its purpose is to validate the dynamic decision mechanism and
anti-lookahead behavior before binding actions into the recurrent account engine.

Historical supported modern alpha remains zero. Dynamic Exit V1 grants no selector,
exit-policy, portfolio, PAPER, or LIVE promotion authority.

