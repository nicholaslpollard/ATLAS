# ATLAS

**Autonomous Trading, Learning, and Analysis System**

**Current as of 2026-09-17 (UTC). The root README, `docs/roadmap.md`, and
`docs/strategy_evidence_register.md` are the three living project documents. Every
continuation chat must read all three in full before making recommendations or changes.**

ATLAS is the greenfield successor to Chart Monitor. Its purpose is to become a
usable quantitative trading platform that can discover and compare opportunities,
run faithful historical replays, construct risk-controlled trades, operate end to
end with PAPER money, record outcomes, show the operator what is happening, and
improve its strategy library without hindsight or silent self-modification.

Profit is an objective, never a guarantee. Activity, alerts, attractive charts, and
profitable backtests are not substitutes for positive expected value after costs,
controlled risk, prospective evidence, and reliable operation.

## Read this first

1. Read this entire README for the current handoff.
2. Read [`docs/roadmap.md`](docs/roadmap.md) for the complete mission, testing
   design, gates, and ordered work.
3. Read [`docs/strategy_evidence_register.md`](docs/strategy_evidence_register.md)
   for strategy/version evidence, condition specialties, dispositions, robustness
   state, and successor hypotheses.
4. Inspect code, tests, immutable phase evidence, and Git history only as needed to
   perform the active roadmap package. Those materials support the three living
   documents; they do not compete with them as current plans.
5. If the three living documents conflict, stop and reconcile them in the same
   package before proceeding.
6. Every repository-changing implementation package must update this README and
   `docs/roadmap.md` before acceptance. Any package that opens, changes, interprets,
   closes, calibrates, or promotes strategy evidence must update the Strategy
   Evidence Register in the same package. A future chat must be able to reconstruct
   current product state, research direction, and strategy evidence without a prior
   conversation window.

All earlier README/roadmap versions were archived verbatim under
`docs/archive/2026-09-02-pre-product-rebaseline/`. The old `current_status`,
`phase_flow`, and plain-English files are frozen compatibility snapshots, not
living handoffs. Historical incident, closeout, policy, evidence, and research
documents are immutable records and must not be rewritten to make a later result
look like an original pass.

## Direction established by ATLAS Review Chat 3

The prior roadmap let unsuccessful alpha research block product construction. That
dependency is retired.

ATLAS now advances on two parallel tracks:

- **Track A — Product:** finish the end-to-end operating system using clearly
  labeled reference/baseline strategies in historical replay and operational
  PAPER. Product completion does not imply alpha validation or LIVE eligibility.
- **Track B — Strategy & Research Lab:** catalog practitioner setups, implement
  faithful finite strategy specifications, backtest them without parameter fishing,
  learn where each works or fails, and later add higher-prior academic mechanisms
  and advanced alpha research.

The immediate research priority is practitioner strategies built from observable
price, volume, volatility, trend, momentum, gap, opening, and premarket signals.
They are useful reference mechanisms and product test loads. A Reddit post, book,
charting site, or popular indicator is an **idea source**, not proof of edge.
Academic and replication evidence receives a higher prior evidence weight, but all
strategies must earn ATLAS historical and prospective evidence.

ATLAS is a strategy-selection system, not a single-strategy bot. It will eventually
rank eligible opportunities using frozen, walk-forward estimates of probability,
net expectancy, downside, execution cost, confidence, correlation, concentration,
and current conditions. It must not search indicators live until something agrees
with a desired trade.

## Current repository truth

- **B35 canonical DEVELOPMENT replay is CLOSED / ACCEPTED.** The frozen `2016-01-04..2026-04-30` trial completed exactly **482/482 groups, 59,768/59,768 source units, and 482 validated receipt ids**, producing **20,171,286** compact fired opportunity/context/outcome records. Run fingerprint = `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`; B35/source/split/authorization identities remained exactly frozen. Consumed-master rows read `0`; future-blind rows read `0`; provider calls `0`; broker reads/writes `0/0`; PAPER/LIVE authority `false/false`; strategy/selector promotion `false/false`; no permanent minute feature lake was created. The accepted continuation reused 82 validated groups and computed the remaining 400 groups / 49,600 units in **11:40:46 at 4,246.7 units/hour**, about **6.43x** the original serial restart and **44.3% faster** than the final isolated exact-equivalent benchmark.
- **B35 strategy x condition / frozen walk-forward selector analysis is COMPLETE / PROFILE-ONLY.** PR #76 merged as `cceccdc23569f6d48395a52322a83f59ba555b23`. Analysis fingerprint `8369790cc019e84091d9ff431e0ba82678e8b23ec09f65f010cdfaca35d3254f` normalized all 20,171,286 accepted compact opportunities and built 33 complete-XNYS 504/63/63/1 folds. The frozen selector evaluated 17,030,985 test opportunities, selected 3,747 (3,188 comparable), and abstained on 99.978%. Selected mean return was +0.2984% / +0.1984% / +0.0485% / -0.2015% / -0.7014% at 0/10/25/50/100 bps. No strategy or selector is promoted. The material research interpretation and per-strategy dispositions are maintained in `docs/strategy_evidence_register.md`.
- **B35 retained-artifact robustness is COMPLETE / NO PROMOTION.** PR #78 merged as `83d09c424a02883f7d3529a39c62294dcbaf6bc2`; workstation robustness fingerprint = `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` across 2,079 complete XNYS test sessions. At 50 bps every declared standalone/selector profile has negative mean session return and Deflated-Sharpe probability `0.0`; 13 selected fold/cell hypotheses produced **0 BH-FDR q=.05 rejections**. The frozen selector remains positive at 0/10/25 bps but is negative at 50/100 bps; its 10,000-draw bootstrap assigns 24.21% probability to positive mean 50-bps session return. PBO/CSCV is 0.01%, retained only as a narrow ranking-stability diagnostic and not profitability evidence. No strategy/selector promotion occurred; consumed-master/future/provider/broker reads remain zero and PAPER/LIVE authority remains false.
- **B35 exact targeted minute perturbations are COMPLETE / NO PROMOTION.** The frozen DEVELOPMENT-only pass completed **482/482 groups and 59,768/59,768 source units**, evaluated all **27 one-axis-at-a-time profiles**, and returned run fingerprint `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69`. Baseline equivalence is `PASS_EXACT_CANONICAL_OUTCOME_REUSE_ALL_GROUPS`; targeted fingerprint `078bdc84a18bd6e5ff401ca0a21d4feed61f7b21770a86610a42ee0fdd16374d`. Consumed-master/future-blind rows read `0/0`; provider calls `0`; broker reads/writes `0/0`; canonical replay rewrite and selector refit `false`; PAPER/LIVE/promotion authority `false/false/false`. No neighboring parameter variant rescued the four B34/B35 strategies after costs: gap delay/threshold variants remained deeply negative; ORB 14/15/16-minute and 0/1/2-minute delays were economically indistinguishable and negative; premarket rel-vol retained only a roughly 4.9-bps best gross mean that was already negative at 10 bps; HVD remained 55-59 signals and negative. B35 v1 is therefore scientifically closed; simple parameter rescue is closed as well.
- **Successor source verification is ACCEPTED; PR #84 implements the separately gated DEVELOPMENT outcome runner without opening broad successor performance during repository acceptance.** PR #82 merged as `26ddd08952454c9b1251df15fe5bfcc8ccdad16a`, implementing the frozen **21 economic families = 10 retained + 11 new**, four bounded B35 mechanism-level challengers, shared PIT context, and deterministic no-lookahead evaluators. PR #83 merged as `5bcc80d72d1203394525c69ba21f07193b4d6272` and froze all **28 concrete routes = 18 daily + 10 minute**, accepted V2 DEVELOPMENT source identities, profile-independent grouping, standalone-before-conditioning/confluence artifact order, and the `0/10/25/50/100` bps diagnostic contract. The workstation hash-only preflight then completed **493/493 groups and 59,768 minute units** under runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`, using 8 workers x 1 DuckDB thread while opening zero strategy outcomes, protected/future rows, provider calls, or broker access. PR #84 adds exact accepted-preflight validation, one shared daily feature pass, exact retained-reference signal masks, a common daily executable-universe disposition, exact B35-native grouping for all ten minute routes, SPY benchmark reconstruction from the already accepted native minute source, next-open 1/5/20-session daily diagnostics, conservative structural-stop/fixed-2R intraday diagnostics, atomic standalone artifacts, hash-validated restart/reuse, and an optional 4x1/6x1/8x1 exact-equivalence performance diagnostic. The accepted source begins on `2016-01-04`; earlier history is never invented. The full 493-group run still requires a second explicit CLI gate, but the workstation benchmark is now an optional performance diagnostic rather than a scientific prerequisite. The first benchmark attempt on 2026-09-13 stopped during input preparation before any benchmark profile ran because the accepted minute source lacks SPY's exact scheduled final regular minute on 2019-08-12. This is now treated as a source-coverage edge case rather than fabricated data: the repaired preregistered SPY benchmark uses the last observed regular SPY bar from the same session only when it is at most 5 minutes stale, records every fallback session/staleness value, forbids cross-session fill and provider fetches, and still fails closed beyond that bound. No successor benchmark performance was opened by that failed attempt. A second preparation attempt then proved the gap is material rather than a one-minute edge case: SPY's last accepted minute on 2019-08-12 is 15:31 ET, 28 minutes before the scheduled final minute. The minute-only repair is therefore retired. The next gate is a separate source-only SPY audit: accepted B35 minute data remains primary; an exact same-session raw canonical V2 daily close may repair an unusable minute session only through 2025; 2026 native-daily partitions are forbidden so the consumed May-August 2026 master cannot be opened indirectly. The source-only audit is now ACCEPTED under contract fingerprint `912bf7b0ed12a0e4fd7c0382244138573564472e618586677e78c154f7e3cc33` and scientific fingerprint `c575d5df1b7f0d0a7734efc3833329f57f73c953b7b67ccb4ea54d33abb4555c`. It resolves all **2,596** DEVELOPMENT XNYS sessions: **2,595** use the accepted minute-primary close and exactly **one** (`2019-08-12`) uses the preregistered `NATIVE_RAW_DAILY` same-session repair because the last accepted minute is `19:31:00Z`, 28.0 minutes stale. Benchmark artifact SHA-256 = `29d7ea9d6a322b4b55af872f7d2e5097777738b209727a487cfd0dcf1306790d`; native-acceptance fingerprint = `6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664`. PR #87 merged as `1e5c399752be690cc1b4a33e915f922e5503d956`, removing optional pandas Parquet-engine dependencies from both the source audit and successor DEVELOPMENT runner without changing scientific contracts. Consumed-master/future-blind/provider/broker reads remain `0`; PAPER/LIVE/promotion authority remains false. The next permitted evidence action is the separately authorized full 546-work-group standalone DEVELOPMENT run (64 daily buckets + 482 minute groups); the earlier 493 count is the source-verification grouping, not the outcome-run denominator; the 4x1/6x1/8x1 benchmark remains available only as an optional performance diagnostic. The first authorized full standalone attempt then opened the DEVELOPMENT-only runner at 8 workers under run fingerprint `22a2ace77c4c578c30964ba2a645b822738ef667617f0ef6bffb3192f75582ae` and stopped on a real sparse/flat prior-session geometry edge before a complete standalone result existed. The failed-break/reclaim route had passed a flat prior high/low into its strict evaluator and raised instead of treating that route as unavailable. The successor engine is now versioned so finite positive non-flat prior geometry is a readiness prerequisite; invalid/flat prior geometry fails closed for that route only. No geometry is fabricated. Console progress now reports completed/total groups, reused/new counts, active/queued work, elapsed time, new-group throughput and ETA at least every 30 seconds or five new completions.

- **B34 intraday source readiness and the opening/premarket pack are CLOSED / ACCEPTED.** The enhanced 2026-09-08 workstation audit returned `ACCEPTED` under contract `atlas-b34-intraday-source-readiness-v2-ohlcv-pack-frozen` with evidence SHA-256 `415c46c714b80f5cff4950320443088b8b89ed761c9f51d071fccf3e60baefd0`. It preserves the earlier semantic/source-readiness evidence SHA-256 `aad355e57c089a7aaea84a3f941091dec69d89ce87235972f13472a308550237`, accepted all five deterministic OHLCV samples, represented premarket/regular/after-hours bars, opened zero partitions overlapping the consumed `2026-05-12..2026-08-11` master interval, and made zero provider calls, broker reads, or broker writes. The frozen RESEARCH-only pack fingerprint is `6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf` for `b34_gap_continuation_v1`, `b34_opening_range_breakout_15m_v1`, `b34_premarket_relvol_consolidation_v1`, and `b34_highest_volume_day_style_v1`. B34 opened no outcomes and grants no promotion, PAPER, LIVE, broker-mutation, or broad/full minute-materialization authority.
- Accepted numbered foundation: **through Phase32**, merged on `main`.
- Phases26–32 are scientifically valid `ACCEPTED_NEGATIVE` results.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is
  `ACCEPTED_NEGATIVE` as well.
- Later XBRL, beneficial-ownership, FINRA short-interest, diluted-EPS, and Form 13F
  branches are also closed accepted-negative/source-limited results.
- Retained beneficial-ownership source-gate lineage: source-only feasibility
  mechanism `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`; frozen
  feasibility fingerprint
  `f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`.
  These are historical source-feasibility identifiers, distinct from the later
  frozen scientific mechanism and preserved for accepted-validator compatibility.
- Historical supported modern alpha remains **0**. No existing strategy is
  historically validated, paper validated, live eligible, or live authorized.
- The retained master protected outcome window `2026-05-12..2026-08-11` was
  **consumed exactly once on 2026-09-07** by the frozen A33/B33 V2 walk-forward.
  The completed receipt/accounting reports **93,380 master-protected return rows
  read**. The frozen version then continued unchanged through the accepted V2
  source cutoff `2026-09-03`; rows after `2026-08-11` are separately tracked as
  post-protected continuation, not a redefinition of the master holdout. This is
  historical out-of-sample evidence, not prospective PAPER.
- V2 split-reconciliation validator repair: provider-native split-adjusted volume
  is no longer required to equal the inverse OHLC split factor. That relationship
  is retained as deterministic audit evidence, while OHLC factor agreement,
  provider/source provenance, schema, finite/nonnegative volume, and other
  raw/adjusted integrity gates remain fail-closed. Focused regressions cover both
  accepted volume divergence and rejected price-factor corruption. At repair
  acceptance this changed no source bytes, strategy/portfolio policy, trading
  authority, or protected-return state; the later frozen replay described below
  subsequently consumed the master holdout exactly once.
- V2 split-price quantization repair: the real completed V2 source showed that the
  former absolute `1e-5` OHLC-factor equality was also too strict for provider-rounded
  split-adjusted prices. The retained quantization diagnostic covered 2,825,114 paired
  eligible rows: maximum adjusted-price residual was `$0.05841364` and maximum
  relative factor error was `0.000994532`. Reconciliation now fails closed unless each
  open/high/low value is within `$0.10` adjusted-price residual **and** `0.001` relative
  factor error of the close-derived split factor. A new regression accepts bounded
  provider rounding while the existing corruption regression still rejects a material
  price-factor mismatch. At repair acceptance it changed no source bytes,
  strategy/portfolio policy, holdout receipt, protected-return state, PAPER
  authority, or LIVE authority; the later frozen replay subsequently consumed the
  master holdout exactly once.
- LIVE trading and automatic broker failover remain disabled.
- The former operator pause is satisfied and superseded by the explicit Review
  direction encoded here. Product and practitioner-library work may resume; it
  grants no trading authority by itself.
- The unmerged Review research lineage remains preserved: LIT-01 Heston-Sadka
  calendar-seasonality work is source-inconclusive; LIT-02 terminal-repair work is
  deferred/incomplete. Neither grants alpha support or changes `main` authority.
- The former statement `Phase33 signal-to-trade remains blocked` is retained only
  as historical roadmap provenance. Product signal-to-trade work is now unblocked
  for historical replay and operational PAPER baselines. LIVE remains blocked.
- Product/strategy rebaseline: PR #44 merged to `main` as
  `6b972c4d26dfa350580e269d8010038fe526cf4f`, based on the accepted PR #43 Form
  13F closeout.
- A33/B33 phase-start contracts: PR #45 merged as
  `bc105be4958cce808dbbeb306f0ec58f23b13a6d`. Its six pre-outcome seed
  specifications, broader research taxonomy, authority transition rules, and
  shared opportunity-event contract remain preserved.
- A33/B33 foundation implementation is complete and protected by its exact-head
  acceptance workflow. Historical performance has now been opened only for the
  frozen V2 DEVELOPMENT and one-time walk-forward versions described below; strategy
  authority did not change and provider/broker/PAPER/LIVE mutations remain zero.
- A33/B33 compatibility validation now treats living-document protected state as a
  monotonic lifecycle: before outcome access it requires the original zero-read
  boundary; after an accepted one-time consumption it requires the current
  consumption statement and protected-row accounting instead. Frozen policy,
  authority, and feature fingerprints remain mandatory. This prevents current
  evidence from being rewritten backward merely to satisfy a historical handoff
  token.
- The trusted-lake adapters are implemented. The retained Massive path remains
  reproducibility-only; the isolated Alpaca SIP V2 adapter produced the completed
  frozen DEVELOPMENT and walk-forward evidence described below.
- The adapter package was accepted in PR #47 and merged as
  `646db6e6e44ccd2355c7c2263221f35cd01d5da8`; its post-merge Windows and Ubuntu
  full-suite jobs passed.
- The first A34 RESEARCH account-replay vertical slice is implemented: deterministic
  candidate admission, cash/position accounting, simulated orders, outcomes, equity
  curve, read-only API, and visible browser state. Empirical V2 DEVELOPMENT and
  frozen walk-forward account replays now exist and are negative at the aggregate
  account level; no strategy was promoted. The slice was accepted in PR #48 and
  merged as
  `147b95810936a0b10b24eb08e51cd4d83c16c85b`; its post-merge Windows and Ubuntu
  full-suite jobs passed.
- The accepted Phase19 operator-path correction is merged in PR #49 as
  `cc0ecc6995ad977ca6eeb5fc00983ba2926317a0`; its post-merge Windows and Ubuntu
  full-suite jobs passed. The current stacked dashboard, not the legacy Phase16
  shell, is the authoritative local GUI entry point.
- The hash-verified A34 operator drilldown was accepted in PR #50 and merged as
  `f0a45cbff2662e26f4f1f55e8a16c0c356c9266c`; its post-merge Windows and Ubuntu
  full-suite jobs passed. The dashboard now verifies and displays account metrics,
  decisions, rejection reasons, simulated orders, outcomes, and equity/exposure.
- Exact point-in-time market-regime context was accepted in PR #51 and merged as
  `e2dd741b4cdd3f5b729c4ec1cb510451887c748c`; its post-merge `main` test workflow
  passed. Daily close-derived signals now carry the exact XNYS-close availability
  clock and the replay consumes only the hash-bound same-close market regime that
  was knowable before next-open entry. Ticker/sector regime remain unavailable.
- Alpaca SIP V2 daily source/replay preparation and the finite B34 minute/intraday semantics audit are complete and accepted. Empirical sizing
  estimates 3.781B native minute rows, 64.51 GiB canonical minute Parquet, 62.55
  GiB compressed raw evidence, and a conservative 375.58 GiB peak-plus-reserve
  requirement. The operator chose precise local V1 historical-data decommissioning,
  not a local V1 archive. The first rebuild-safety package provides a generation-
  isolated `data/v2_build/alpaca_sip_v2` layout, atomic run state, a 30 GiB reserve
  guard, and an allowlisted content-hash-bound V1 decommission plan. It deliberately
  preserves live, model, unrelated research, repository, and accepted evidence
  state. The explicit `--decommission-v1-only` run completed successfully on the
  operator workstation on 2026-09-03 local time: **8 targets / 38,034 files /
  147,206,406,678 bytes (137.10 GiB)** were deleted after the exact generated token
  was confirmed. The retained receipt is
  `data/checkpoints/alpaca_v2_migration/v1_decommission_receipt.json`. ATLAS now has
  no accepted historical market database. The read-only post-decommission inventory
  then identified database-generation remnants that were outside the first eight
  targets: `raw/day_aggs_v1`, legacy `provider/alpaca`, old ML training data,
  discovery/universe/regime/quality/reference products, and their ingestion/manifests.
  Accepted strategy-evaluation evidence, SEC/regulatory source evidence, live state,
  models, source code, and Git history remain outside the expanded cleanup boundary.
- The fresh-source native V2 package was accepted in PR #57 and its first operator
  acquisition completed on 2026-09-07. `scripts/run_alpaca_v2_rebuild.py --build-v2`
  first
  inventories and asks for
  exact hash-bound confirmation of only the remaining database-derived targets; it
  writes a new plan-hash-specific receipt and never overwrites the original receipt.
  It then freezes the last completed XNYS session, captures fresh active and inactive
  Alpaca assets plus complete-quality corporate actions, builds an exact-literal
  acquisition universe, and runs native `1Day` units before native `1Min` units.
  The source contract is Alpaca SIP, raw adjustments, `asof=-`, 10,000 total bars per
  page, opaque pagination until the token is null, and New York local-midnight
  windows with the inclusive API end moved back one microsecond. Every page is an
  atomic restart boundary; exact response bytes, checksums, request metadata,
  normalized page shards, unit Parquet, quarantine records, and run/plan manifests
  live only beneath `data/v2_build/alpaca_sip_v2`. Provider-rejected or anomalous
  literals are quarantined without substitution. The runner reserves 30 GiB and
  pauses safely when capacity is insufficient. The estimated 3.781B minute rows mean
  one overnight run was not assumed; rerunning the identical command resumed rather
  than restarted. The final operator report is `COMPLETE`: **67,480 / 67,480 units**,
  including **5,302 / 5,302 daily** and **62,178 / 62,178 minute** units,
  **3,897,688,734 canonical rows**, and **1,757,288 quarantined rows**. This is a
  complete isolated native candidate base, not production promotion. The quarantine
  is retained evidence and was carried into the post-build gate rather than
  discarded or assumed harmless. Historical V2 RESEARCH results now exist only for
  the frozen versions described below; PAPER authority and LIVE authority remain
  absent.
- The V2 post-build package was accepted in PR #58 and merged as
  `8e5abf21fe1ca138cd90125005b8c305a598dd44`; its post-merge `main` workflow passed
  on Windows and Ubuntu. It has now run successfully against the completed operator
  V2 source: native validation passed **67,480 / 67,480 units**, the provider-native
  split source reused **5,302 / 5,302 complete units**, and the reconciled research
  view materialized **2,706,154 rows across 1,582 symbols**. Its single resume-safe
  post-build
  coordinator hash-verifies every native unit; fully scans native daily schema,
  provenance, dates, sessions, duplicates, and OHLCV; builds conservative direct-
  Alpaca-asset identity/lifecycle evidence; acquires a separate provider-native SIP
  `adjustment=split` daily source; reconciles raw and adjusted bars; and materializes
  a hash-bound V2 daily research view. Name changes, mergers, reorganizations,
  spin-offs/rights, stock distributions, termination/redemption events, ticker reuse,
  uncertain security type, source anomalies, and internally gapped streams are
  excluded rather than silently stitched until a separate segment and cash-flow
  policy exists. Native raw prices remain separate. The research view carries
  unadjusted same-session close for the PIT `$5` universe floor so a future split
  cannot rewrite historical eligibility. Although source capture continues through
  its frozen current cutoff, the strategy-input Parquet ends physically at the
  **2026-05-11 DEVELOPMENT boundary** and materializes zero protected-window return
  rows. It does not promote a production database or grant historical, PAPER, or
  LIVE authority. Compile-all and the complete local
  suite pass at **1,546 tests**; all ten PR #58 exact-head workflow groups and the
  post-merge `main` workflow passed.
- The frozen walk-forward package is implemented and tested in PR #61 after native
  completion and before any operator V2 performance read. The default DEVELOPMENT
  manifest and adapter still end
  physically at `2026-05-11` and reject every later row. A separate
  `walk_forward_daily.json` generation can be created only after an immutable,
  self-hash-bound authorization records the exact native/split source plus frozen
  strategy, feature, and portfolio fingerprints. Its signal interval begins exactly
  `2026-05-12`; earlier rows are indicator warm-up only, and its end must equal the
  latest validated V2 source session. The trials ledger, strategy replay, account
  replay, post-build manifest, and permanent consumption receipt all account for the
  protected rows. A failed attempt after opening remains consumed. No parameter
  revision, historical-to-PAPER relabeling, strategy promotion, or external write is
  permitted by this path. The restart repair preserves each superseded consumption
  receipt as a content-addressed snapshot, verifies the complete history before
  continuation, retains known protected-row counts across attempts, and reuses a
  completed replay only after its operator artifact verification passes. Missing or
  inconsistent current/history receipts fail closed; source-only reruns cannot erase
  prior consumption. The GUI shows the attempt and known/pending row accounting and
  never describes an incomplete run as unopened. The materialization-cutoff failure
  path also preserves an observed protected-row count in both the receipt and
  post-build summary. Three additional pytest cases cover that failure and successful
  retries after cutoff and replay failures. The complete implementation revision
  `0879bbed7f22c53108f58db0b790f58c61a04987` passed all **ten PR #61 workflow
  groups**, including the locked Windows and Ubuntu full suites at **1,581 tests
  plus 4 subtests per platform** and all three retained A33/A34 validators. Local
  checks also passed 10 isolated standard-library receipt tests, 13 isolated
  coordinator checks, Python compilation, JavaScript syntax, dependency-lock
  validation, and secret hygiene. Local isolation was necessary because application
  dependencies were absent; the full application evidence comes from locked CI.
  The implementation closeout changed only the two living documents after the code
  package. The authorized workstation run has now completed. DEVELOPMENT produced
  **161,347 opportunities**, account replay **-17.912608%** return and
  **-20.803073%** max drawdown. The frozen walk-forward evaluated signals
  `2026-05-12..2026-09-03`, produced **14,081 opportunities**, consumed the retained
  master holdout exactly once with **93,380 protected return rows read**, and ended
  with account replay **-8.372772%** return and **-8.372772%** max drawdown. Signal-
  level mean net return was positive for Bollinger-long, EMA-pullback-long,
  MACD-long, and RSI-recovery-long, but the aggregate account evidence is negative,
  the RSI sample is small, cash-distribution economics remain incomplete, and
  **authority promotion is none**. All nine policies remain RESEARCH; PAPER/LIVE
  authority remains absent.
- **A34.5 operator live observability is now implemented in PR #60.** Its
  accepted merge closes the observability prerequisite before A35; A35 itself remains
  a separate PAPER/broker-authority package and has not begun. No PAPER broker
  mutation is authorized by A34.5.
- The former Phase39 LIVE numbering is retained: **Phase39** remains Controlled
  LIVE Activation and is still protected by all preceding evidence and authority
  gates.

## What exists now

The accepted foundation already includes provider ingestion, PIT identity/history,
Parquet/DuckDB analytical storage, deterministic features, universe/discovery,
market/sector/ticker regime context, ML evidence, strategy routing, instrument and
trade geometry, portfolio risk planning, AI review boundaries, broker-neutral
SHADOW/PAPER primitives, Webull-primary and manual-Alpaca-secondary controls,
restart-safe orchestration, API/browser primitives, and historical production-path
reconstruction.

Important limitations:

- The accepted Phase11 strategy registry still contains eight simplified daily
  rule variants. A33/B33 adds a separate, versioned reference-strategy catalog so
  accepted behavior is not silently changed.
- The accepted PR #45 six-specification seed catalog remains an immutable
  pre-outcome compatibility layer. The nine direction-specific policies resolve
  its declared implementation blockers without rewriting that accepted lineage.
- The first six practitioner families now have nine direction-specific, complete
  research policies covering universe, signal, side, timing, stop, target, exit,
  sizing, costs, and authority.
- A separate daily reference-feature overlay supplies the exact indicator
  transitions needed by those policies without changing the accepted 33-feature
  core. B34 supplies accepted minute/session semantics and the initial
  opening/premarket evaluators. The successor pre-outcome implementation now adds the
  shared daily PIT overlay, objective confirmed-pivot/chart-pattern geometry, ADX/DMI
  and SPY-relative-strength context, closed-minute VWAP/failed-break evaluators, and
  exact implementations for all eleven new families plus the four bounded B35
  challengers. No successor historical performance is opened by that implementation.
- The existing router applies fixed regime compatibility; it does not yet learn
  conditional, walk-forward strategy performance or calibrated probability.
- A provider-free independent-strategy runner, condition-sliced opportunity/outcome
  records, append-only strategy-trials ledger, and read-only catalog API now exist.
  A read-only trusted-lake adapter now supplies its exact input contract. The first
  fixed, non-learned account replay and browser view now exist; learned selection,
  qualifying PAPER, strategy-management controls, and the complete operator product
  remain unfinished.
- A34.5 now supplies the accepted read-only near-live Operational PAPER dashboard
  contract over engine-owned evidence: no second GUI trading truth, no independent
  trade decisions, bounded automatic refresh, and visible fail-closed degraded/
  invalid state. A35 broker mutation remains a separate authority package.
- PostgreSQL and the root Docker deployment remain historical scaffolds, not an
  accepted operational database or deployment.

The decommissioned V1 daily lake used Alpaca SIP through `2021-08-13` and
Massive from `2021-08-16`. That boundary is retained historical provenance, not the
current data path. The fresh V2 candidate base is Alpaca SIP throughout its frozen
acquisition interval. No V1 row, derived indicator, regime, or identity product may
be silently reused as V2 input. Earlier source limitations do not authorize invented intraday history; V2 minute semantics are now accepted by B34, and missing minute history remains preserved as absence rather than synthesized.

## 2026-09-16 — Live market-data provider and transport policy

ATLAS now separates its durable analytical lake from its live market interface. The
canonical Parquet/DuckDB V2 lake remains the broad historical/research source used for
large-universe discovery and replay. **Alpaca is the primary live/current market-data
provider; Webull is the secondary live/current fallback where its API entitlement and
feed quality are sufficient.** Execution remains a separate concern: Webull is the
planned primary PAPER/LIVE execution broker and Alpaca remains the explicitly selected
manual execution fallback. Automatic broker failover remains prohibited.

Massive is no longer a required forward runtime dependency. Any retained Massive free
access is diagnostic/research-only and carries no trading authority; historical Massive
source provenance and reproducibility paths remain immutable evidence and are not
rewritten. Tradier and unofficial Yahoo/yfinance feeds are not part of the supported
operating-provider chain.

Live transport is intentionally selective rather than market-wide. Broad discovery
runs locally first; REST/API snapshots refresh the narrowed candidate set and obtain
option-chain/contract evidence; WebSocket subscriptions are then allocated where
seconds matter economically: final candidate validation before entry, pending orders,
open positions, and exits. REST remains the normal overflow and recovery path when a
candidate does not receive a streaming slot or a stream is degraded. One provider
connection may multiplex many symbol/contract subscriptions; subscription capacity,
not one-connection-per-candidate, is the managed resource.

Streaming priority is: **open positions and pending orders first; entry-ready finalists
second; strong near-finalists third; lower-ranked candidates by REST; broad discovery
from the local lake.** A central market-data coordinator must own the stream/REST budget,
share one underlying subscription across related option candidates, apply hysteresis or
minimum residency so nearly tied candidates do not thrash subscriptions, and dynamically
promote/demote candidates as ranking changes. A WebSocket failure degrades first to a
fresh same-provider REST snapshot, then to the accepted secondary provider when
available, and finally to `DATA_UNAVAILABLE`/abstention rather than invented market
state.

Every live observation must retain provider, feed, transport, market timestamp,
receive timestamp, freshness/age, and quality/provenance. Current Alpaca Basic limits
verified on 2026-09-16 are **30 equity WebSocket symbols** on the real-time IEX stock
feed and **200 option quote subscriptions** on the indicative option feed, with REST
rate capacity treated as a separate budget. These are operational entitlements, not
scientific constants: the coordinator must configure/discover current provider limits
rather than hard-code them permanently. The then-current paid Alpaca plan raises stock
streaming to unlimited symbols and option quote streaming to 1,000 with consolidated
U.S. equities/OPRA-quality access; ATLAS does not require that paid plan until the
system's economics justify supporting its own data subscription.

For options, the intended sequence is `underlying shortlist -> REST option-chain
snapshot/Greeks/liquidity -> small contract finalist set -> underlying + finalist
WebSockets -> entry -> held-contract/underlying streams through exit`. If finalists
exceed streaming capacity, the coordinator streams the highest-priority subset and
keeps the remainder current through rate-aware REST polling. Provider transport choice
must not alter strategy authority, economics, portfolio-risk gates, or execution truth.

## 2026-09-16 — Explicit simulation funding/collateral terms

Track A now freezes the funding boundary under contract `f76d77ebbf138924a22813773ad27276b0fa71691ddff1d21040171c7b6d3821`
(`atlas-simulation-funding-collateral-terms-v1`). It consumes only the exact accepted
simulation account-state v2 snapshot and exact broker-neutral entry-fill evidence. The
terms object is descriptive evidence only: it does not mutate the account, release a
reservation, create a position, borrow funds, create an order, mark to market, realize
P&L, read/write a broker/provider, or grant PAPER/LIVE/promotion/confluence authority.

V1 permits a **fully cash-funded bullish stock long only**. Required cash is exact
filled gross notional plus explicit entry fees. The existing stock reservation is
credited toward that requirement and any remaining amount must be proven available in
the account's currently unreserved cash pool. Insufficient supplemental cash fails
closed. Borrowing, margin, leverage, collateral and short-sale proceeds remain exactly
zero and are never inferred from the accepted economic-capital/gross-notional gap.
Bearish stock/short position conversion therefore remains unsupported until a separate
versioned short-collateral/proceeds model is accepted.

Long options reuse the already-resolved debit from accepted fill evidence. Required
cash equals the exact filled premium debit plus accepted entry fees, supplemental cash
is zero, and any unspent option reservation remains explicit for the later atomic
position transition. Option delta-equivalent exposure remains separate from stock
gross notional and is not reinterpreted as funding or collateral.

That funding boundary is now consumed by the deterministic open-position entry-book
account state described below. Mark-to-market, unrealized/realized P&L, exits/closeout,
broker mutation and PAPER/LIVE authority remain later gates. The Strategy Evidence
Register is intentionally unchanged because these packages change product simulation
architecture only.

## 2026-09-16 — Deterministic open-position entry-book account state

Track A now adds `atlas-simulation-open-position-account-state-v1` under contract
`c15c03400d61bf9e025f836118bf431178caadbdfc7c9a62826ec03796a0ee37`. It consumes one immutable accepted reservation-account snapshot plus
exact simulated entry-fill and funding/collateral evidence, then converts reservations
into deterministic **entry-book-value open positions**. The source reservation batch is
never rewritten: every fill and funding record remains bound to the exact account-state
fingerprint against which it was created, while the position layer tracks which source
reservations remain unconverted.

Each transition releases exactly one matching reservation and updates cash as
`current cash + released reservation - accepted required cash`. Cash is rechecked at
the moment of transition, so multiple fills that were individually affordable against
the same original unreserved-cash pool cannot spend those dollars twice. Same-fill
reapplication is idempotent; a different fill for an already-open decision fails
closed. Batch application is deterministic by `(filled_utc, fill_fingerprint)`, and
state/event/ledger fingerprints support exact replay verification and tamper detection.

Entry fees are expenses immediately: `entry book equity = initial equity - cumulative
entry fees`, while `cash + remaining reservations + open entry book value` must equal
that entry-book equity. Stock gross exposure transfers exactly from the reservation to
the cash-funded bullish stock position. Long-option premium paid becomes option entry
book value/premium at risk; the reservation's signed/absolute delta-equivalent exposure
is retained only as an **entry reference**, not a current Greek or mark. Stock shorts
remain unsupported because no accepted collateral/proceeds model exists.

The open-position package deliberately stops before market valuation. The source-bound
market-mark evidence layer described below now supplies exact valuation provenance, but
mark-to-market, unrealized/realized P&L, exits/closeout, broker mutation and PAPER/LIVE
authority remain separate gates. The Strategy Evidence Register remains unchanged
because these packages change product/account-simulation architecture only.

## 2026-09-16 — Source-bound market-mark evidence

Track A now freezes `atlas-simulation-market-mark-evidence-v1` under contract
`1219f600e447f90718213ce0f974314f6480e90e13f46487770785e45c87c154`. The package binds one immutable mark record to one exact accepted
open-position fingerprint and requires explicit source id/SHA-256, provider, feed,
transport, feed-quality, market timestamp, receive timestamp, and valuation timestamp.
It is evidence-only: the accounting layer still performs no provider or broker read.

For the currently supported long stock and long-option positions, v1 selects the
**executable bid** as the conservative valuation candidate. Midpoint and last may be
retained descriptively but are never treated as liquidation truth. Stock requires a
positive bid; a long option may legitimately carry a zero bid, preserving a possible
zero liquidation value rather than inventing one. Crossed quotes fail closed.

Freshness is frozen at a maximum **60 seconds** from market timestamp to valuation
time. `market_timestamp <= received_timestamp <= valuation_timestamp` is mandatory.
A stale observation is retained for audit but is explicitly
`valuation_eligible = false`; it cannot create or carry forward P&L. The 60-second
limit is a versioned simulation policy rather than a permanent provider constant.

The market-mark package itself remains evidence-only and grants no account mutation,
realized P&L, exit/closeout, provider/broker, order, PAPER, LIVE, promotion or
confluence authority. The deterministic marked-account layer described below now
consumes those fresh marks for simulation valuation and unrealized P&L. The Strategy
Evidence Register remains unchanged because these packages change
product/account-simulation architecture only.

## 2026-09-16 — Deterministic marked account and unrealized P&L

Track A now adds `atlas-simulation-marked-account-state-v1` under contract
`f09a1ead48e86ae82442785f281c0e57d242db3773537a3ba64a44bb2519c082`. It consumes the exact accepted open-position account snapshot plus
one exact fresh, valuation-eligible market-mark record for **every** active position at
one common valuation timestamp. Missing, stale, duplicate, mismatched, or extra marks
fail closed; ATLAS does not publish an authoritative account-level marked-equity value
for an incomplete valuation snapshot.

For each active position, marked value is `quantity * selected bid mark * multiplier`.
Unrealized P&L is marked value minus immutable entry book value, and unrealized return
uses entry book value as its denominator. Account unrealized P&L is the sum of the
position values, while marked equity is `entry_book_equity + aggregate_unrealized_P&L`
and independently reconciles to `cash + remaining reservations + marked open-position
value`. Entry fees were already expensed when the position opened and are therefore
never subtracted a second time in unrealized P&L.

A long option with a valid fresh zero bid may mark to zero and therefore to a full loss
of its entry book value. Option delta-equivalent exposure remains the immutable
**entry reference** only; this package does not infer a current Greek from price marks.
All marked positions share the requested valuation timestamp, and a mark whose market
timestamp predates the position open is rejected. Empty accounts produce a complete
zero-position valuation deterministically.

This is deterministic simulation valuation only. It does not mutate the open-position
state and grants no realized-P&L, exit/closeout, provider/broker, order, PAPER, LIVE,
promotion or confluence authority. The next bounded Track A work is broker-neutral
simulated exit-fill evidence followed by deterministic closeout/realized-P&L accounting
with lifetime trade-P&L and account-equity semantics kept explicit so entry fees cannot
be double counted. The Strategy Evidence Register remains unchanged because this is
product/account-simulation architecture only.

## 2026-09-17 — Broker-neutral simulated exit-fill evidence

Track A now adds `atlas-simulated-exit-fill-evidence-v1` under contract
`d823bdf481f6ae6266be0a7e87d36702e1687d5a84f97da105e64cfc7e8f77c0`.
It consumes the exact accepted open-position account state, requires one exact active
open-position fingerprint, and binds a complete exit fill to an explicit source id,
source SHA-256, timezone-aware exit timestamp, exit price, and explicit exit fees.

V1 is deliberately **full-close only**. Quantity, quantity unit, instrument identity,
position lineage, and contract multiplier are inherited exactly from the active open
position; callers cannot silently resize or partially close a position. Gross exit
proceeds are `quantity * exit_price * multiplier`, and net exit proceeds are gross
proceeds less explicit exit fees. Exit price may be zero so a long stock/option
complete-loss case remains representable; exit fees may not exceed gross proceeds.

This object is descriptive broker-neutral fill evidence only. It does not remove the
position, mutate account cash, compute realized P&L, read/write a provider or broker,
create an order, assert a broker fill, or grant PAPER/LIVE/promotion/confluence
authority. The deterministic closeout layer described below now consumes this
evidence. The Strategy Evidence Register remains unchanged because this package
changes product/account-simulation architecture only.

## 2026-09-17 — Deterministic closeout and realized-P&L accounting

Track A now adds `atlas-simulation-closeout-account-state-v1` under contract
`d8363e6a0dba68ad8894691a308eff6231770e59ccea909a38fd95af317aa599`.
It consumes the exact accepted open-position account snapshot plus exact accepted
broker-neutral exit-fill evidence. Only the matched active position is removed;
unrelated positions and all remaining reservations are preserved exactly, while exact
net exit proceeds are returned to simulation cash.

The accounting boundary deliberately distinguishes two realized-P&L meanings. The
**account-state realized-P&L delta** is `net_exit_proceeds - entry_book_value`
because entry fees were already expensed when the position opened. The **lifetime
trade net P&L** is `gross_exit_proceeds - entry_book_value - entry_fees - exit_fees`.
For every closed trade, lifetime net P&L therefore equals account realized-P&L delta
less the already-expensed entry fee. Account book equity is
`initial_equity - cumulative_entry_fees + cumulative_account_realized_pnl` and
independently reconciles to cash plus remaining reserved capital plus remaining open
entry-book value.

Closeout transitions are chronological, fingerprint chained, and deterministic.
Reapplying the identical exit-fill fingerprint is idempotent; a different second
exit against an already closed position fails closed. Batch application is ordered by
exit timestamp/fingerprint and the full state/ledger can be reconstructed and
fingerprint-verified by deterministic replay. Closed-trade evidence retains entry and
exit economics, both fee layers, holding duration, instrument/strategy lineage, and
the two P&L views.

This remains simulation-only lifecycle accounting. It grants no provider/broker
read/write, order, PAPER, LIVE, promotion, or confluence authority. The post-close
valuation layer described below closes the remaining current-marked-equity gap before
browser integration. The Strategy Evidence Register remains unchanged because this
package changes product/account-simulation architecture only.

## 2026-09-17 — Post-close lifecycle marked-account state

Track A now adds `atlas-simulation-lifecycle-marked-account-state-v1` under contract
`4cc4fb35c5a95cb48603f581a48127fe188c844c44e445394ad3d662e07a5346`.
This closes the valuation gap that appears after one or more positions have been
deterministically closed: the closeout account remains the current book/realized-P&L
truth, while fresh mark evidence remains bound to each surviving immutable position.

The lifecycle valuation consumes the exact closeout-account fingerprint plus exactly
one fresh, valuation-eligible mark for every **currently open** position at one common
valuation timestamp. Missing, duplicate, stale, closed-position, or other extra marks
fail closed. Closed trades are never revalued. Current marked position value and
unrealized P&L are computed only for surviving positions, while cumulative entry fees,
exit fees, account-realized P&L, and lifetime trade net P&L are carried forward
unchanged from the accepted closeout state.

Marked equity is `account_book_equity + aggregate_unrealized_pnl` and independently
reconciles to cash + remaining reserved capital + current marked open-position value.
An account with no surviving positions has complete zero-mark coverage and marked
equity equal to closeout book equity. Option delta-equivalent exposure remains an
immutable entry reference only; current Greeks are not inferred from price marks.

This layer performs simulation valuation only. It grants no account mutation, new
realized P&L, exit/closeout, provider/broker read/write, order, PAPER, LIVE, promotion,
or confluence authority. The read-only operator projection described below now
consumes this current post-close truth. The Strategy Evidence Register remains
unchanged because this is product/account-simulation architecture only.

## 2026-09-17 — Engine-owned simulation lifecycle observability

Track A now adds a read-only lifecycle projection to the existing loopback
control-plane/browser surface. `SimulationLifecycleDashboardService` accepts only an
injected pair of accepted engine objects: the deterministic closeout account and the
post-close lifecycle marked-account state. It independently revalidates closeout
state/ledger fingerprints, the marked-state fingerprint, exact source-state binding,
carried accounting fields, and current open-position/mark lineage before exposing any
payload.

The new local endpoint is `/api/v1/ops/simulation-lifecycle`. It never initializes a
provider, broker, order adapter, or legacy execution-artifact fallback. With no
injected engine source it returns explicit `NOT_CONNECTED`; an invalid injected
source returns `INVALID`. Only a fingerprint-valid engine-owned source is rendered
as `AVAILABLE`.

The browser adds a Track A simulation-lifecycle panel showing current marked/book
equity, cash, realized and unrealized P&L, fee layers, currently open marked
positions, deterministic closed trades, and source fingerprints. It uses the existing
`atlas:observability-refreshed` event, adds no independent timer, performs GET only,
and carries zero browser/provider/broker/order mutation authority. The synthetic
preview server exposes the same response shape for UI development while remaining
explicitly synthetic and read-only.

This closes the projection/UI seam. The single-cycle coordinator described below now
supplies the accepted atomic engine-owned source, while post-close re-entry remains a
separate next lifecycle boundary. The Strategy Evidence Register remains unchanged.

## 2026-09-17 — Atomic single-cycle simulation lifecycle coordinator

Track A now implements the first production-facing lifecycle owner in the previously
empty `packages/simulation/engine.py` seam under contract
`atlas-simulation-lifecycle-coordinator-v1`
(`696254240971db5a9a7ae2a0307c2c847b376d360d5cfe1f8b5f30ec80a93a9b`).

`SimulationLifecycleCoordinatorV1` starts from one exact accepted
`OpenPositionAccountStateV1`, deterministically initializes the accepted closeout
account, and then owns that cycle's current closeout book state plus an optional
post-close marked state. It performs no provider, broker, order, or filesystem I/O;
exit fills and market marks must already exist as accepted evidence before they are
supplied.

The coordinator uses one re-entrant lock and immutable state replacement so readers
can obtain an atomic book+valuation pair. A real closeout event advances the logical
revision and invalidates any prior marked state. Reapplying an identical idempotent
exit does not mutate state, advance the revision, or destroy a still-current
valuation. Mark publication requires the accepted complete/fresh current-position
coverage contract; an identical mark snapshot is idempotent. Revision advancement is
defined by actual new closeout ledger events plus new valuation publications, so
sequential and batch application converge to the same logical revision and replay
fingerprint.

The control-plane adapter now converts only `current_dashboard_pair()` into the
read-only lifecycle projection. Until current marks exist—or immediately after a
closeout invalidates them—the browser remains `NOT_CONNECTED` rather than displaying
stale valuation. `create_phase19_status_server` may accept either an explicitly built
lifecycle dashboard service or a lifecycle coordinator, never both.

This is deliberately a **single-cycle** coordinator. It does not create new
reservations, accept new entries after the immutable source snapshot, or support
re-entry. Those capabilities remain outside v1 so current-state ownership can be
accepted independently before the account model is extended across subsequent
decision/entry cycles. No provider/broker/order/PAPER/LIVE/promotion/confluence
authority is created.

The lifecycle-native reservation layer described below now begins that post-close
re-entry path without conflating reservation with a filled position. The Strategy
Evidence Register remains unchanged.

## 2026-09-17 — Lifecycle-native post-close re-entry reservations

Track A now adds `atlas-simulation-lifecycle-reservation-account-v1` under contract
`b4b825cca77a59f2d65064c9644d513714968f4ae7b8cea03f0738411d3459bb`.
This is the first re-entry/account-continuation layer that operates against a
**current lifecycle book** rather than restarting the old reservation-only account
model after positions or realized P&L already exist.

The state is initialized from one exact accepted `CloseoutAccountV1` and carries
forward, unchanged, the closeout state/ledger fingerprints, current open positions,
closed trades, cumulative entry/exit fees, account-realized P&L, lifetime trade net
P&L, cash, book equity, and any still-active reservations. New decision records may
then reserve stock capital or long-option capital from **current unreserved cash**.
Reservations reduce cash and increase their dedicated reserved-capital/exposure
buckets while account book equity remains unchanged and continues to reconcile as
`cash + stock reservations + option reservations + open entry-book value`.

Reserved stock gross notional remains separate from existing open-stock exposure.
Reserved option signed/absolute delta-equivalent notional, max-loss cash, and premium
at risk remain separate from the immutable entry-reference exposure of already-open
options. Long-option reserved max loss remains equal to reserved option capital.
Abstentions, missing option terms, and insufficient-current-cash decisions are
fingerprint-chained ledger events with zero capital mutation. Duplicate decisions are
idempotent; conflicting option terms fail closed; chronological batch replay
reconstructs exact state and ledger fingerprints.

This package intentionally creates **no entry fill or new position**. Existing open
and closed histories are immutable across reservation transitions, and one decision
cannot exist simultaneously in an active reservation/open bucket and the closed
history. No mark, closeout, provider/broker/order, PAPER/LIVE, promotion, or
confluence authority is created.

The lifecycle-native fill/funding evidence layer described below is required first
because the earlier accepted evidence contracts are explicitly bound to the legacy
reservation-only account contract. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle-native re-entry fill and funding evidence

Track A now adds two descriptive lifecycle-native evidence contracts required before a
post-close reservation can become a new open position:

- `atlas-simulation-lifecycle-entry-fill-evidence-v1`
  (`a2bcaddbfba19370af070217cd2c4b911b121797abb76348747e575e17aa3b3c`);
- `atlas-simulation-lifecycle-funding-terms-v1`
  (`26266be782240511baadeb73d11aef393aaa6a52f12883b30cd3aab025f54870`).

This versioning is necessary rather than cosmetic. The earlier accepted
`atlas-simulated-entry-fill-evidence-v1` and
`atlas-simulation-funding-collateral-terms-v1` explicitly require
`atlas-simulation-account-state-v2-stock-option-reservations` as their account input.
After deterministic closeout, the authoritative reservation account is instead
`atlas-simulation-lifecycle-reservation-account-v1`, whose fingerprint also carries
open/closed history and realized accounting. Reusing the old evidence contracts would
therefore misstate provenance.

The lifecycle-native fill evidence binds one exact current lifecycle reservation-state
fingerprint, decision fingerprint, active reservation fingerprint, economic candidate,
explicit fill source id/SHA-256, timestamp, price, and entry fees. Stock quantity is
derived from the exact reserved economic notional and executable fill price; stock
funding remains unresolved at the fill-evidence layer. Long-option fills reuse the exact
accepted reservation terms, require the reserved contract count/multiplier, cap premium
debit and fees at the accepted reservation buckets, and record exact unspent reserve.

The lifecycle funding object then proves funding against the same current lifecycle
reservation state. Bullish stock longs remain cash-only: reserved capital is credited
first and any remaining required cash must come from **current unreserved lifecycle
cash**. Long options reuse the exact resolved reserved debit and may not require
supplemental cash. Prior realized P&L and prior fee history are not recomputed. Both
objects remain descriptive only and create no reservation release, account mutation,
position, provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The atomic reservation-to-position layer described below now consumes this evidence.
The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle-native reservation-to-position account state

Track A now adds `atlas-simulation-lifecycle-position-account-v1` under contract
`7c5f2a82a8583b9f7b2e90f994f7d6ca4c682888448b97ad287e79e6dad82f29`.
It consumes one exact accepted lifecycle reservation snapshot plus lifecycle-native
entry-fill and funding evidence and performs the first post-close **re-entry position
mutation**.

Initialization carries the exact lifecycle reservation state/ledger fingerprints,
current cash, active reservations, pre-existing open positions, closed trades, fee
history, account-realized P&L, lifetime trade net P&L, and book equity forward. Each
entry must bind the immutable source reservation snapshot and an exact reservation
that is still active in the current mutation state. Only that matched reservation is
removed and one exact new `SimulatedOpenPositionV1` is created.

Entry accounting remains explicit. Stock cash becomes current cash minus supplemental
cash plus any unspent reserve; long-option cash adds only the exact unspent reserved
debit. The new entry fee is added to cumulative entry fees **once**, while prior
realized P&L and exit fees remain unchanged. Account book equity remains
`initial_equity - cumulative_entry_fees + cumulative_account_realized_pnl` and must
also reconcile to current cash + remaining stock reservations + remaining option
reservations + total open entry-book value.

A critical competition rule is enforced at mutation time. Multiple fill/funding
objects may each have been individually fundable against the same immutable source
reservation snapshot, but deterministic application is ordered by fill timestamp then
fill fingerprint and each new entry must still have enough **current remaining cash**.
Thus stale per-fill source projections cannot overspend the account. Identical duplicate
fill/funding application is idempotent; a different second fill for an already-open
decision fails closed; state and ledger replay are exact.

This v1 creates positions only. It does not create new reservations after the source
snapshot, close positions, mark to market, read/write providers or brokers, create
orders, or grant PAPER/LIVE/promotion/confluence authority.

The lifecycle post-reentry valuation layer described below now binds current marks to
this position state. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle post-reentry marked-account state

Track A now adds `atlas-simulation-lifecycle-position-marked-account-v1` under
contract
`ba944922450d570ac15b6b28794cfe0cb2c7894cba0e62d09e0957df35c92863`.
It provides the account-level current valuation required after lifecycle-native
re-entry creates new positions.

Individual `SimulatedMarketMarkEvidence` objects remain reusable because they are
bound to immutable position fingerprints rather than to the older account contract.
The account-level valuation is versioned, however, because the accepted source is now
`LifecyclePositionAccountStateV1`, not the pre-reentry closeout snapshot.

The builder requires exactly one fresh, valuation-eligible mark for every currently
open lifecycle position at one common valuation timestamp. Missing, duplicate, stale,
or extra marks fail closed. Closed trades are never revalued. Current marked value and
unrealized P&L are computed for all surviving pre-existing and newly re-entered
positions while cumulative entry/exit fees, realized P&L, lifetime trade net P&L,
cash, remaining reservations, and book equity are carried forward unchanged.

Marked equity remains `account_book_equity + aggregate_unrealized_pnl` and must
independently reconcile to current cash + stock reservations + option reservations +
marked open-position value. This package performs valuation only and grants no account
mutation, new realized P&L, exit/closeout, provider/broker/order, PAPER/LIVE,
promotion, or confluence authority.

The lifecycle-native exit-evidence layer described below now supplies the exact
post-reentry exit provenance. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle-native post-reentry exit-fill evidence

Track A now adds `atlas-simulation-lifecycle-exit-fill-evidence-v1` under contract
`f3a952f971d693dbc0ca098d9eb5ff912d54443b9dcf2580409bb5558285df74`.
This is the descriptive exit boundary for positions held by
`LifecyclePositionAccountStateV1`.

A new exit-evidence version is required because the earlier accepted
`atlas-simulated-exit-fill-evidence-v1` explicitly consumes the pre-reentry
`atlas-simulation-open-position-account-state-v1` snapshot. Newly re-entered
positions and their current account history now live under the lifecycle position
contract, so reusing the old account-level source fingerprint would lose provenance.

The builder requires one exact lifecycle position-account state fingerprint and one
exact active position fingerprint. Quantity, quantity unit, instrument/option identity,
entry-fill/funding/reservation lineage, and contract multiplier are inherited from
that position. Exit evidence binds an explicit source id/SHA-256, timezone-aware exit
timestamp, nonnegative exit price, and explicit nonnegative exit fees. Gross proceeds
are `quantity * exit_price * multiplier`; net proceeds are gross less exit fees.
Zero-price complete-loss exits remain representable, while fees may never exceed gross
proceeds. V1 is full-close only.

This object remains descriptive broker-neutral evidence. It does not remove the
position, mutate account cash, compute realized P&L, read/write providers or brokers,
assert a broker fill, create an order, or grant PAPER/LIVE/promotion/confluence
authority.

The deterministic lifecycle closeout layer described below now consumes this evidence.
The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle-native post-reentry deterministic closeout

Track A now adds `atlas-simulation-lifecycle-closeout-account-v1` under contract
`9588c3ac326a78103803371071655f0133608beaf0fb10ee7932b3cf0cbace1b`.
It consumes one exact lifecycle position-account state plus exact lifecycle exit-fill
evidence and performs deterministic realized-P&L closeout after re-entry.

The source lifecycle position state/ledger fingerprints are frozen at initialization.
Each accepted exit must still match one currently open position exactly and reproduce
its decision, reservation, entry-fill, funding, instrument, quantity, multiplier, and
option lineage. Only the matched position is removed; remaining reservations and
unrelated positions are unchanged. Exact net exit proceeds return to cash.

The closeout keeps two historical record classes deliberately separate. Closed trades
that predate lifecycle re-entry remain immutable `ClosedTradeV1` records with their
original open-position source semantics. New post-reentry exits append
`LifecycleClosedTradeV1` records whose source fingerprint explicitly names the
lifecycle position-account snapshot. This avoids relabeling old provenance merely to
make the collections uniform.

For every new lifecycle closed trade, account realized-P&L delta remains
`net_exit_proceeds - entry_book_value`; lifetime trade net P&L remains that delta
minus the already-expensed entry fee. Cumulative entry fees never change at closeout,
while cumulative exit fees, account realized P&L, and lifetime trade net P&L add only
the new closeout contribution. Book equity remains
`initial_equity - cumulative_entry_fees + cumulative_account_realized_pnl` and must
also equal cash + remaining reservations + remaining open entry-book value.

Identical exit-fill reapplication is idempotent, conflicting second closes fail
closed, batch order is exit timestamp then exit-fill fingerprint, and exact state and
ledger replay is required. No provider/broker/order/PAPER/LIVE/promotion/confluence
authority is created.

The stable recurrent-account foundation described below now performs that
consolidation without erasing source provenance. The Strategy Evidence Register
remains unchanged.

## 2026-09-18 — Stable recurrent lifecycle account foundation

Track A now introduces the consolidation target
`atlas-simulation-recurrent-lifecycle-account-v1` under contract
`9a22ebdb75a85c7d602851f48ae19a4262b0ab5a28441fc80f26b22a96781299`.
This is intentionally a **stable multi-cycle account contract**, not another numbered
copy of the reservation → position → closeout bridge.

The bootstrap consumes one exact accepted lifecycle-closeout state/ledger pair and
carries forward current cash, active reservations, open positions, fee totals,
realized P&L, lifetime trade net P&L, and book equity. Historical closed trades are
canonicalized into `RecurrentClosedTradeV1` records without erasing provenance.
Each canonical record retains:

- whether it originated from the original closeout path or the lifecycle closeout path;
- the exact source-state contract fingerprint;
- the exact source-state fingerprint;
- the exact original closed-trade record fingerprint; and
- the full immutable trade economics/fee/P&L lineage.

This removes the need to pretend that a lifecycle-native closed trade came from the
original open-position contract merely to combine histories. The recurrent state then
uses one chronological closed-trade collection for accounting while the source record
remains independently verifiable.

The recurrent account also freezes one append-only event-ledger schema broad enough
for reservation, entry, and closeout state transitions. The bootstrap ledger begins
empty at the exact recurrent initial-state fingerprint; later accepted mutation
packages will append fingerprint-chained events rather than replace the account
contract again. Current marks remain a read-only projection and are not ledger
mutations.

The recurrent state grants no provider/broker/order/PAPER/LIVE/promotion/confluence
authority. The recurrent reservation transitions described below now begin mutating
this stable account directly. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle reservation transitions

Track A now extends the stable recurrent account with
`atlas-simulation-recurrent-reservation-transitions-v1` under contract
`8e7cb6b4cf3d64bcafc8f0af9443bde8022df92c5b200aec67f4611fbedae796`.
Unlike the bounded bridge, these transitions mutate
`RecurrentLifecycleAccountV1` directly and append to its existing recurrent ledger;
no new reservation-account contract is created for each cycle.

Every decision is evaluated against current recurrent unreserved cash while existing
open positions and canonical closed history remain unchanged. Bullish stock
reservations retain separate reserved capital and economic gross notional. Long-option
reservations require the exact accepted reservation terms and maintain reserved
capital, max-loss, premium-at-risk, signed delta-equivalent, and absolute
delta-equivalent exposure separately from already-open option exposure.

The recurrent ledger now retains decision, reservation, reservation-terms, option
economics, candidate, option-contract, instrument, ticker, direction, state-chain, and
monetary/exposure deltas. Abstentions and rejected decisions advance deterministic
account time through zero-money ledger events. Duplicate decisions are idempotent;
supplying conflicting option reservation terms for an already-applied option decision
fails closed. Batch competition is ordered by decision timestamp then decision-record
fingerprint.

This package still creates reservations only. It grants no entry-fill, new-position,
exit/closeout, provider/broker/order, PAPER/LIVE, promotion, or confluence authority.
The recurrent entry/funding evidence layer described below now binds fills directly to
the same stable recurrent state. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle entry-fill and funding evidence

Track A now adds two descriptive operation contracts against the stable recurrent
account:

- `atlas-simulation-recurrent-entry-fill-evidence-v1` —
  `6802682c78dac10921afd49a023bab774dded6d5c8415e53f17ac92f852bf15a`;
- `atlas-simulation-recurrent-funding-terms-v1` —
  `4340cbe3d39b1026663db416094093814dab691ef611e7fca8a8a93e5023b6fc`.

Both objects bind one exact **current recurrent-state fingerprint** and one exact active
reservation fingerprint. They therefore cannot be reused after unrelated recurrent
state mutation. Stock fill evidence preserves the reserved economic gross notional and
derives complete share quantity from the explicit fill price while leaving funding
semantics unresolved. Long-option fill evidence reuses the exact accepted option
reservation terms, contract count/multiplier, premium/fee reserve, and records any
unspent reserved capital.

Funding evidence then proves the same fill against the same recurrent snapshot.
Bullish stock longs remain cash-only: existing reserved capital is credited and any
remaining requirement must be available in current recurrent unreserved cash. Long
options reuse the exact reserved debit and require zero supplemental cash. Neither
evidence object changes cash, releases a reservation, creates a position, recomputes
historical fees/P&L, or grants provider/broker/order/PAPER/LIVE authority.

The recurrent reservation→position transition described below now consumes that
evidence on the same stable account and append-only ledger. The Strategy Evidence
Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle reservation-to-position transitions

Track A now adds `atlas-simulation-recurrent-position-transition-v1` under contract
`998b3c505aaabd429b5009cb1c9cfebe864810f2d6e871d60450f4ccc2d7e084`.
This operation consumes and returns `RecurrentLifecycleAccountV1`; it does not create
a new position-account generation.

A transition requires recurrent entry-fill and funding evidence from one accepted
recurrent source snapshot and the exact reservation must still be active when the
mutation is applied. Only that reservation is consumed. The new
`SimulatedOpenPositionV1` preserves decision/candidate/reservation/fill/funding and
option lineage, the new entry fee is expensed once, canonical closed history remains
unchanged, and one fingerprint-chained `OPEN_POSITION` event is appended.

Single-entry application requires evidence to bind the exact current state. Batches may
pre-materialize several fills/funding objects against one common source snapshot, but
application is deterministic by fill time/fingerprint and each transition rechecks the
current remaining cash and reservation. Thus separately valid evidence cannot spend the
same supplemental cash twice. Exact duplicate fill/funding reuse is idempotent and a
conflicting second fill for an already-applied decision fails closed.

The operation grants no exit/closeout, mark-to-market, provider/broker/order,
PAPER/LIVE, promotion, or confluence authority. The read-only recurrent marked-account
projection described below now supplies current valuation without mutating the
recurrent ledger. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle marked-account projection

Track A now adds `atlas-simulation-recurrent-marked-account-v1` under contract
`6f473d2480167efa77e7826c994661d12141621122e99b644cb58cc39bbf5532`.
It consumes one exact recurrent account state plus accepted position-bound market-mark
evidence and produces current unrealized-P&L/equity state without appending a recurrent
ledger event.

Exactly one fresh, valuation-eligible mark is required for every current open
position at one common valuation timestamp. Missing, duplicate, stale, or extra marks
fail closed. Both inherited positions and newly recurrent-opened positions are valued
through their immutable position fingerprints; canonical closed history is never
revalued.

Marked position value is quantity × selected mark × multiplier. Aggregate unrealized
P&L is the sum of marked value less entry-book value for current open positions.
Marked equity is `account_book_equity + aggregate_unrealized_pnl` and must
independently reconcile to cash + stock reservations + option reservations + marked
open-position value. Cash, reservations, entry/exit fees, realized P&L, lifetime trade
net P&L, book equity, and the recurrent ledger remain unchanged.

This projection grants no account mutation, new realized-P&L, exit/closeout,
provider/broker/order, PAPER/LIVE, promotion, or confluence authority. The recurrent
full-close exit evidence described below now supplies exact current-position exit
provenance. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle exit-fill evidence

Track A now adds `atlas-simulation-recurrent-exit-fill-evidence-v1` under contract
`61135bbede1416c852d7c84fa2914876c056508be9fdad1a87b834cb71f659ad`.

The evidence binds the exact current recurrent-state fingerprint and the active
position's immutable entry-source account-state fingerprint separately. It requires one
exact active position, explicit source id/SHA-256, timezone-aware exit time,
nonnegative exit price, and explicit nonnegative fees. Quantity, multiplier, all
decision/candidate/reservation/entry/funding lineage, and option identity are inherited
from the position. V1 is full-close only; zero-price complete losses remain valid.

This object is descriptive only: it creates no realized P&L or account/ledger mutation
and grants no provider/broker/order/PAPER/LIVE authority. The recurrent
`CLOSE_POSITION` transition below now consumes it.

## 2026-09-18 — Recurrent lifecycle close-position transitions

Track A now adds `atlas-simulation-recurrent-close-position-transition-v1` under
contract
`9f2f32d8905c19bfb377184abd1fa3f9842eb979829ce5ca03c3a44068e17e39`.

The operation consumes and returns `RecurrentLifecycleAccountV1`. Each close requires
exact recurrent exit evidence and a currently open matched position. Only that position
is removed; active reservations and unrelated positions remain unchanged. Net proceeds
return to cash and one fingerprint-chained `CLOSE_POSITION` event is appended.

New closes append canonical `RecurrentClosedTradeV1` records with native
`RECURRENT_ACCOUNT_V1` provenance. Account realized P&L is net proceeds minus entry
book value; lifetime trade net P&L additionally subtracts the entry fee already
expensed at open. Entry fees therefore are not double counted. Duplicate exit-fill
reuse is idempotent, conflicts fail closed, common-source batches are deterministic,
and exact replay is required.

This completes the stable recurrent simulation loop on one account contract:
**reserve → entry evidence/funding → open → mark → exit evidence → close → reserve
again**. The recurrent coordinator described below now becomes the atomic runtime owner.
The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle coordinator

Track A now adds `atlas-simulation-recurrent-lifecycle-coordinator-v1` under contract
`0cadfd2c89c09c26731b8895ca70893dde3855c3eded4773c4455bce94b8e882`.
It is a new runtime owner rather than a mutation of the earlier single-cycle
coordinator, which remains intact for compatibility.

`RecurrentLifecycleCoordinatorV1` owns one accepted
`RecurrentLifecycleAccountV1` behind a single `RLock` and delegates only to the
accepted recurrent reservation, entry, mark, and close operations. It performs no
provider, broker, order, filesystem, or network I/O. The initial logical revision is
the current recurrent ledger-event count; every newly appended ledger event advances
the revision, including zero-money abstention/rejection events. Each unique mark
publication advances revision once but does not alter the recurrent ledger.

Any real account mutation invalidates the previously published marked state because its
source-state fingerprint is no longer current. Exact idempotent reservation/entry/close
reuse does not change account state, does not advance revision, and does not destroy a
still-current valuation. Republishing an identical complete mark snapshot is likewise
idempotent. `current_dashboard_pair()` returns an atomic recurrent account + marked
state only when their fingerprints match exactly.

The next bounded Track A package is recurrent lifecycle observability: adapt this
atomic recurrent pair into the existing loopback/browser payload, retaining one
engine-owned source of truth and zero browser/provider/broker/order mutation authority.
The Strategy Evidence Register remains unchanged.

## A33/B33 reference foundation

The **A33/B33 — Practitioner Strategy Laboratory and Product Rebaseline**
foundation implements:

1. a stable, versioned reference catalog alongside the accepted registry;
2. separate indicators, setup signals, complete trade policies, routing, and
   authority;
3. the missing daily features required by the first six reference families;
4. the first finite daily reference library;
5. a reusable, PIT-safe historical runner and opportunity/outcome
   ledger that records fired, rejected, routed, and counterfactual strategies;
6. report structures by time, market/sector/ticker regime, volatility, liquidity,
   and direction without mining sparse condition combinations;
7. a read-only product/control-plane catalog view and append-only trials ledger;
8. proof that these research baselines cannot become PAPER or LIVE
   authority accidentally; and
9. a read-only adapter from accepted Massive canonical daily partitions and
   retained identity/split evidence into the frozen runner input contract.

The first six families contain nine direction-specific policy versions:

1. 50/200 moving-average trend cross;
2. 20/50 EMA pullback continuation;
3. MACD momentum shift;
4. RSI trend-filtered mean reversion;
5. 20-session Donchian high-volume breakout;
6. Bollinger compression breakout.

Gap/opening-range and premarket relative-volume consolidation breakouts follow only
after trusted minute/premarket coverage and exact session semantics pass a
source-only readiness gate. The Reddit “Highest Volume Day” setup belongs in that
later intraday pack as a quantitatively defined, unverified practitioner hypothesis;
its reported statistics are not ATLAS evidence.

No historical performance is opened until each implemented strategy version has a
frozen universe, signal, direction, timing, exit, risk, cost, and evaluation
contract. One canonical version per genuinely different family comes before
variants.

Frozen A33/B33 contracts:

- reference strategy-policy fingerprint:
  `26a6aae124b1a5d2b14b8a11a72671b06ac34d3cf94eb7ac47f16d2cfb94a8b3`;
- strategy-authority fingerprint:
  `a23ec27367ae540b869abc428d118241e84436719a8a543cbdbc3f3b678c69c5`;
- daily reference-feature fingerprint:
  `ee7e09b680b64b65280dea88c01d402bd9576a04cc70bc7748d8e3048ff57159`.
  This pre-outcome correction binds the PIT `$5` price floor to the unadjusted
  same-session close while indicators and returns remain split-adjusted.
- retained legacy trusted-lake adapter contract:
  `reference-lake-adapter-v1-massive-development-split-free-identity-exact`.
- isolated V2 adapter contract:
  `reference-v2-lake-adapter-v2-alpaca-sip-hash-bound-explicit-evaluation-scopes`.

All nine policies remain `RESEARCH` authority and are permitted only in
`RESEARCH_REPLAY`. The runner accepts caller-supplied split-adjusted daily bars,
rejects every post-DEVELOPMENT row by default, creates signals only at finalized
closes, and enters no earlier than the next session open. Its distinct one-time
walk-forward mode requires explicit master-holdout authorization, uses earlier rows
only for indicator warm-up, filters signal generation to `2026-05-12` onward, and
counts the protected rows it reads.
It retains fired, rejected, selected-independent, and overlap-suppressed
counterfactual opportunities across the `0/5/10/25/50` bps grid. Empirical V2
DEVELOPMENT and frozen walk-forward account replays now exist. The retained master
holdout was consumed exactly once; **93,380** master-protected return rows were
read. The frozen walk-forward continued unchanged through `2026-09-03`; no
parameter revision or strategy promotion occurred. Broker writes: **0**; PAPER
submits: **0**; LIVE writes: **0**.

The retained adapter is deliberately narrower than the accepted complete daily history. V1
uses Massive only from `2021-08-16` through at most `2026-05-11`, requires every
requested XNYS partition, resolves exact identity without current active/delisted
filters, rejects internal stream gaps, and excludes an entire identity if any of its
observed tickers has a documented split in scope. Because retained canonical prices
are unadjusted, only these factor-1-equivalent streams may be labeled
`SPLIT_ADJUSTED`; no factor is guessed. This costs coverage but prevents false
signals and returns. Alpaca pre-seam and split-affected streams remain deferred to a
separately validated adjustment-capable V2. The new V2 adapter accepts only
`data/v2_build/alpaca_sip_v2/manifests/research_daily.json` and its exact partition
hashes; arbitrary paths and legacy fallback are forbidden. It validates Alpaca SIP,
split-adjusted, regular-session, identity-clear common-stock provenance and the
regular-open/source versus regular-close/signal clocks before returning a row.
A separate `ReferenceV2WalkForwardLakeAdapter` accepts only
`walk_forward_daily.json`, verifies its immutable authorization self-hash and frozen
strategy/feature/portfolio fingerprints, requires a permanent consumption receipt,
requires the exact authorized warm-up start plus the complete protected interval,
and requires the requested end to equal the source cutoff. It is never an automatic
fallback.

The replay input now has two separate clocks. The canonical daily
`timestamp_utc` remains the provider's regular-open stamp for source provenance;
`signal_available_at_utc` is derived from the XNYS regular close under contract
`reference-signal-availability-v1-xnys-regular-close-next-open`. Close-derived
signals are recorded at that availability time and still cannot enter before the
next regular-session open. This corrects evidence labeling without changing the
previous next-open return simulation or claiming that any empirical result exists.

The retained read-only regime adapter contract
`reference-regime-context-v1-exact-asof-hash-bound-same-close-market-only` attaches
the accepted same-session finalized market regime to a next-open decision. It
requires the split-origin manifest whose `as_of_date` exactly equals the replay end,
verifies the bound snapshot and `market_effective.parquet` SHA-256 values, rejects
future, duplicate, blank, or missing-session state, and writes no production state.
No accepted PIT instrument-to-sector mapping or reference ticker-state join exists,
so ticker and sector regime fields remain `UNAVAILABLE` rather than inferred.
No accepted V2 PIT regime generation exists yet. V2 replay therefore labels market,
sector, and ticker regime `UNAVAILABLE` and reads zero retained V1 regime rows rather
than importing the decommissioned generation or guessing a label.

The native V2 acquisition, post-build, DEVELOPMENT replay, and frozen one-time
walk-forward have all completed on the operator workstation. The browser read model
prefers the hash-valid completed walk-forward and fails closed rather than silently
falling back to legacy or DEVELOPMENT evidence when protected-state artifacts are
invalid. DEVELOPMENT account replay returned **-17.912608%** with
**-20.803073%** max drawdown. The frozen walk-forward through `2026-09-03` returned
**-8.372772%** with **-8.372772%** max drawdown and read **93,380** rows from the
retained master protected interval. Performance is now opened for these frozen
versions; no strategy was promoted.

The local command first runs the adapter, binds its source fingerprint,
and registers the frozen trial before calculating any strategy outcome. It can stop
after source validation or continue through the independent-strategy replay:

```powershell
.\.venv\Scripts\python.exe scripts\run_a33_b33_reference_development.py --data-source v2 --source-only
.\.venv\Scripts\python.exe scripts\run_a33_b33_reference_development.py --data-source v2
```

The full command writes its lake-adapter and regime-context reports, independent
opportunity ledger, account admission decisions, simulated orders, position
outcomes, equity curve, summaries, and append-only trial records beneath the V2
generation; it does not write to a provider, broker, PAPER account, or LIVE account
and cannot promote authority. `--source-only` validates V2 input and explicit
unavailable regime context and stops before any performance outcome is opened.
`--data-source legacy` preserves the former Massive-only evidence path for
reproducibility; it is never an automatic fallback.

The first V2 analytical stream is provider-native **split-adjusted price return**.
It does not yet credit or debit cash distributions in position P&L. Any optional
first replay is therefore a product/research diagnostic, not qualifying historical
evidence; dividend and spin-off cash-flow economics must be added or conservatively
bounded before a strategy can earn historical authority.

## A34 RESEARCH account replay

The first A34 product vertical slice has frozen portfolio-policy fingerprint
`c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa`.
It processes each session in this order: opening exits, opening candidate admission,
intraday daily-bar exits, then closing valuation. The fixed baseline begins with
`$100,000`, risks at most `0.25%` of current equity per admitted position, caps one
position at `10%` of equity, gross exposure at `100%`, open positions at `10`, and
active positions from one strategy family at `3`. Same-session candidates are
balanced by current family load and then stable identifiers; realized returns are
never used to rank them.

This is a **RESEARCH account replay**, not qualifying historical validation. V1 is
long-only: short signals and their independent counterfactual results are retained,
but account admission rejects them until short borrow, locate fees, recalls, and
asymmetric execution are modeled. Correlation and sector controls also remain
explicitly unavailable rather than guessed. A conservative `10` bps round-trip cost
is charged as `5` bps on entry and `5` bps on exit. Candidates without a resolved
historical exit are rejected so the V1 account finishes cash-reconciled and flat.

The local control plane exposes the latest result read-only at
`/api/v1/research/reference-replay`. The browser shows all nine frozen policies,
RESEARCH authority, per-strategy account statistics, replay
return/drawdown/costs, recent completed positions, admission decisions, simulated
order events, and a closing-equity/exposure curve. Before displaying an available
run, the read model verifies the recorded SHA-256 binding and schema of every
decision, order, outcome, and equity artifact; drift fails closed as `INVALID`. It
shows `NOT_RUN` honestly until the trusted-lake command produces artifacts. After
the one-time walk-forward completes, it prefers that separately labeled result,
verifies the completed consumption receipt and protected-row count, and labels the
GUI `WALK-FORWARD`; an incomplete/failed consumption never falls back to a seemingly
clean DEVELOPMENT display. Policy
promotion: **false**; master-protected return rows read: **93,380**; holdout
consumed: **true exactly once**; provider writes: **0**; broker writes: **0**; PAPER
submits: **0**; LIVE writes: **0**.

The current operator entry point is the stacked Phase19 dashboard, not the older
Phase16 shell. Start it from the repository root with
`python scripts/run_phase19_control_plane.py` (or
`.\.venv\Scripts\python.exe scripts\run_phase19_control_plane.py` on Windows), then
open `http://127.0.0.1:8765`. Its A33/A34 Strategy Laboratory panel reads the
catalog and latest replay through the two local GET endpoints; loading or refreshing
the panel does not call a market-data provider or broker.

Market-regime condition slices now use the hash-bound same-session finalized market
regime that was knowable at the signal close and before the next-open entry. Ticker
and sector condition slices remain explicitly `UNAVAILABLE`; they must not be used
for conditional performance claims until their separate PIT joins are accepted.

## A34.5 operator live observability gate

PR #60 (`a34-5-frontend-operator-dashboard`) completes the A34.5 read-only
operator-observability gate when this closeout is accepted and merged.
`PaperDashboardService` reads accepted local Phase15 execution evidence plus
Phase5 persisted marks, verifies artifact path/hash/schema before display, and
never initializes a provider or broker merely to refresh the browser. Fresh LONG
positions mark conservatively at bid and SHORT positions at ask; stale marks cannot
create P&L, provider uncertainty is visibly `DEGRADED`, and invalid evidence is
`INVALID`. Strategy provenance and realized net P&L remain explicitly unavailable
where the accepted upstream evidence does not bind them.

The production surface is GET-only at `/api/v1/ops/paper-dashboard` on the existing
loopback-only Phase19 server. The operator console uses bounded 5/15/30-second
polling and organizes Overview, Market, Research, Portfolio, Execution, Brokers &
Data, Operations, and Controls without maintaining a second trading truth. A
separate synthetic Codespaces preview never loads `.env`, never initializes real
providers/brokers, disables mutation controls, and rejects POST. A34.5 grants no
PAPER strategy authority or broker-write authority; it only satisfies the
observability prerequisite so A35 can begin under its own explicit authority gate.

This is a product-readiness gate, not a strategy-evidence promotion.
The accepted dashboard must make it easy to see, as the PAPER system operates:

- account equity, cash/buying power, exposure, realized P&L, unrealized P&L, and
  relevant daily/session totals;
- every open position with ticker, strategy/version, side, quantity, entry/current
  price, stop/target/invalidation state, risk, and unrealized dollar/percent P&L;
- the decision stream: what setup fired, relevant market/condition context, concise
  deterministic selection/rejection reasoning, sizing/risk reasoning, authority,
  and AI audit/review state when applicable;
- planned/submitted/accepted/partially-filled/filled/canceled/rejected order events
  and reconciliation state;
- exits/sales with exit reason, price, realized dollar/percent P&L, costs, and hold
  duration;
- searchable/reviewable closed-trade and decision history plus strategy-level and
  account-level statistics; and
- market-data/provider/broker freshness and health, last successful update,
  orchestration state, authority mode, and kill/emergency-control visibility.

The UI must update through an accepted event-driven or short-polling mechanism
without requiring the operator to manually refresh the page. It must read the same
engine-owned decision/order/position/account records used for execution and
reconciliation; it may format or aggregate them but must not maintain a separate
trading truth or recompute trading decisions independently. Unknown or stale state
must be obvious and fail closed. A34.5 completion grants no PAPER authority by
itself; it removes the observability prerequisite so A35 can begin under its own
centralized PAPER authority gate.

## Strategy authority and PAPER/LIVE boundary

Every strategy carries two separate labels:

- **Evidence source:** `PRACTITIONER_BASELINE`, `LITERATURE_ANCHORED`, or
  `INTERNAL_CHALLENGER`.
- **Authority:** `RESEARCH` → `CANDIDATE` → `HISTORICALLY_VALIDATED` →
  `PAPER_VALIDATED` → `LIVE_ELIGIBLE`.

Authority controls what a strategy may do. Ranking controls which eligible
opportunity ATLAS prefers. A high score cannot bypass an authority gate.

Two PAPER modes are required:

- **Operational PAPER** exercises the product with baselines. Results are useful
  for debugging and learning, but cannot qualify a strategy for LIVE. Operational
  PAPER is additionally blocked until the A34.5 operator live-observability gate is
  accepted.
- **Qualifying PAPER** begins only after a version is historically validated and
  the prospective policy is frozen. It is the strongest empirical gate to LIVE,
  but still must pass profitability, sample, risk, drawdown, stability, execution,
  concentration, and operational checks.

`PAPER P&L > 0` alone is never enough. LIVE also requires `LIVE_ELIGIBLE` status,
system-level readiness, explicit operator authorization, small initial exposure,
hard loss limits, reconciliation, a kill control, and no automatic broker failover.

## Non-negotiable safeguards

- Preserve point-in-time identity, provider-native symbols, chronology, corporate
  actions, delistings, and session semantics; fail closed on ambiguity.
- Do not silently weaken transaction-cost, slippage, spread, borrow, capacity,
  liquidity, or market-impact assumptions.
- Use the retained `0/5/10/25/50` bps diagnostic grid where comparable, with
  10 bps primary and 25 bps stress for signal-level daily screening; executable
  replay must replace generic costs with instrument-, side-, liquidity-, volatility-,
  and order-aware costs.
- Signals computed at a bar close enter no earlier than the next executable event.
  Same-bar high/low cannot fill an order created from that bar's close.
- Treat overlapping trades, shared sessions, tickers, sectors, and market moves as
  dependent observations.
- Keep a trials ledger and apply family-level multiple-testing controls. A hundred
  indicator parameterizations are not a hundred independent discoveries.
- Use chronological walk-forward selection, purging/embargo where labels overlap,
  frozen challengers, and untouched qualifying periods.
- Use the master protected window only once for the already-frozen practitioner
  walk-forward evaluation. Never use its results to select parameters and then call
  the same interval validation; any revision becomes a new version whose evidence
  starts after the revision.
- No production self-modification. A learned selector or strategy revision is a new
  version that must be frozen, replayed, PAPER qualified, and explicitly promoted.
- Zero trades or negative results are valid. Stop a branch when expected information
  gain no longer justifies its infrastructure or source-repair cost.
- Prefer trusted existing market data. Novel difficult sources must beat simpler
  available experiments on expected research value before receiving priority.

## Data repair and V2 policy

When historical data becomes materially questionable:

1. investigate root cause and reconcile local files, transformations, provider
   semantics, and authoritative sources;
2. repair V1 only when the economic meaning remains trustworthy;
3. otherwise preserve V1 results/provenance and either freeze the persisted V1 lake
   or, when explicitly authorized as here, decommission only its exact historical
   namespaces through a reviewed hash-bound plan;
4. build a separately versioned V2 with authoritative sources and explicit
   canonical rules;
5. never substitute V2 underneath an observed experiment or describe it as the
   same experiment; and
6. preserve provenance and old results for audit.

Repeated authoritative-source contradictions do not justify purge/refetch loops
whose only purpose is to make evidence disappear.

The current Alpaca V2 rebuild is started or resumed from PowerShell with:

```powershell
.\.venv\Scripts\python.exe scripts\run_alpaca_v2_rebuild.py --build-v2
```

The first invocation may display a small residual cleanup plan and require its exact
generated token. Later invocations reuse the frozen cutoff/source/plan and verify
completed artifacts before continuing. Do not delete the V2 checkpoint tree or vary
`--start-date` between resumes. `Ctrl+C`, a time limit, a network failure, or the disk
floor leaves a resumable checkpoint; none grants production-data or trading authority.

After that command returns `NATIVE V2 ACQUISITION COMPLETE`, do not delete or move
its generation. Pull the accepted post-build package and run one of these:

```powershell
# Source validation, identity/lifecycle, split-adjusted daily acquisition, and V2 research view.
.\.venv\Scripts\python.exe scripts\run_alpaca_v2_postbuild.py

# The same fail-closed chain, then the frozen DEVELOPMENT strategy/account replay.
.\.venv\Scripts\python.exe scripts\run_alpaca_v2_postbuild.py --through-reference-replay

# Recommended authorized chain: DEVELOPMENT through May 11, then one-time
# walk-forward from May 12 through the exact validated V2 cutoff.
.\.venv\Scripts\python.exe scripts\run_alpaca_v2_postbuild.py --through-walk-forward-replay --authorize-master-holdout-consumption
```

The post-build command is resumable at split-adjusted daily unit boundaries.
`--max-hours` can create a graceful checkpoint and the identical command continues
it. `--validate-only` performs no provider request. `--through-reference-replay`
opens DEVELOPMENT outcomes only and cannot read beyond `2026-05-11`.
`--through-walk-forward-replay` first completes that same DEVELOPMENT run, then
requires `--authorize-master-holdout-consumption`. Before any protected performance
read it writes an immutable self-hash-bound authorization tied to the exact source
and frozen policy fingerprints. After DEVELOPMENT succeeds and before protected
materialization starts, it writes the permanent consumption receipt; a materialization
or replay failure therefore remains consumed and cannot reset the holdout. Before
each receipt update, its previous state is preserved under
`manifests/master_holdout_consumption_history/`; the current self-hash and every
prior snapshot are verified on reads and retries. Known protected-row counts cannot
be cleared or changed. A verified completed run is reused without repeating either
replay; a missing or damaged completed result stops for repair. It then
creates a separate analytical manifest, starts signals on `2026-05-12`, and advances
chronologically through the exact source cutoff. Earlier rows in that input are
warm-up only. Neither replay may promote a strategy or submit a PAPER/LIVE order.
The DEVELOPMENT files remain physically capped at May 11; the authorized walk-forward
files and results remain separately labeled.
Provider rejections and malformed split-source rows remain evidence: when their
literal symbol is attributable, that symbol is excluded globally and the clean
remainder may proceed; an unattributed anomaly or unit-level validation failure
blocks materialization rather than poisoning or discarding the full database.
If source preparation passes but replay fails, the valid V2 daily foundation remains
recorded while the replay failure is explicit. Do not start this command in the same
working tree while the native acquisition process is still running.

Daily indicators are calculated by the frozen reference engine from the promoted V2
research view when a replay runs; a second giant feature lake is not created merely
to duplicate them. News acquisition is not part of this database acceptance chain:
it neither validates price history nor has a frozen provider/PIT contract, so it is
deferred to its own finite research package. Native minute evidence, extended-hours semantics, and initial intraday strategy readiness are accepted by B34. **B35 DEVELOPMENT replay and all preregistered B35 robustness/targeted diagnostics are CLOSED / ACCEPTED-NO-PROMOTION (2026-09-13).** The frozen `2016-01-04..2026-04-30` replay completed all **482/482 groups** and **59,768/59,768 source units**, with **482 validated receipt ids**, **20,171,286 fired opportunity/context/outcome records**, and run fingerprint `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`. The authoritative summary confirms consumed-master rows read `0`, future-blind rows read `0`, provider calls `0`, broker reads/writes `0/0`, PAPER/LIVE authority `false/false`, and strategy/selector promotion `false/false`. The canonical replay, condition/selector analysis, retained-artifact robustness, and exact targeted perturbations are all complete. Track B has moved to the frozen successor practitioner laboratory: PR #82 merged the exact 21-family rule/feature implementation, and PR #83 is the source/runner-contract plus hash-only source-verification gate. B35 v1 will not be replayed or parameter-tuned again.

## Planned practitioner strategy library and confluence architecture

ATLAS already contains more practitioner work than the current four-strategy B35
pack. The accepted A33/B33 reference library has **six daily practitioner families
with nine direction-specific policies**, and B34/B35 adds **four intraday/opening
families**. Those ten existing families are retained; the successor package adds
**eleven genuinely new mechanisms** for a planned **21-family practitioner library**.
Do not duplicate an existing mechanism under a new name merely because a later chat
rediscovers it.

The completed B35 DEVELOPMENT experiment remains frozen around its four B34
strategies and is now immutable historical evidence. It must not be rewritten or
replayed to rescue a disappointing result. The broader library is successor work
under a new preregistered fingerprint.

### Existing practitioner families to retain

1. **50/200 moving-average trend cross / Golden Cross** —
   `ma_trend_cross_50_200_long_v1`. The accepted policy uses the standard 50-session
   SMA crossing above the 200-session SMA, 201 sessions minimum history, ATR-based
   risk, and reverse-cross/maximum-hold exit logic. This is already ATLAS's Golden
   Cross implementation; do not create a duplicate `golden_cross` strategy.
2. **20/50 EMA pullback continuation** — `ema_pullback_20_50_long_v1`. Established
   EMA uptrend, bounded pullback into the 20/50 trend zone, objective recovery,
   ATR/pullback-low risk geometry and finite holding horizon.
3. **12/26/9 MACD momentum shift** — `macd_shift_12_26_9_long_v1` and
   `macd_shift_12_26_9_short_v1`. Long requires an upside signal cross below zero;
   short mirrors it above zero. The short profile remains research-only for account
   admission until borrow/locate/recall economics exist.
4. **RSI trend-filtered recovery / mean reversion** —
   `rsi_recovery_14_trend_long_v1`. RSI(14) recovery through the frozen level inside
   the accepted long-trend filter; strong-trend behavior is measured rather than
   assumed to mean-revert.
5. **20-session Donchian high-volume breakout** —
   `donchian_breakout_20_volume_long_v1` and
   `donchian_breakout_20_volume_short_v1`. Prior rolling-channel escape, aligned
   trend and relative-volume evidence, with the decision bar excluded from the prior
   boundary. Short remains research-only for account admission.
6. **20-session Bollinger squeeze breakout** —
   `bollinger_squeeze_breakout_20_long_v1` and
   `bollinger_squeeze_breakout_20_short_v1`. Prior-session compression followed by a
   directional band escape, relative-volume evidence, ATR risk and finite hold.
7. **Gap continuation** — `b34_gap_continuation_v1`. Material overnight gap followed
   by the frozen continuation trigger; prior regular close anchors the B34/B35 risk
   rule.
8. **15-minute opening-range breakout** —
   `b34_opening_range_breakout_15m_v1`. Uses the completed 09:30-09:44 ET opening
   range and only acts after the range is information-safe; the opposite boundary
   anchors risk.
9. **Premarket relative-volume consolidation breakout** —
   `b34_premarket_relvol_consolidation_v1`. Requires unusual premarket participation,
   an objective premarket consolidation and the frozen post-open breakout.
10. **Highest-volume-day style** — `b34_highest_volume_day_style_v1`. Tests the
    practitioner thesis that exceptional current premarket participation versus
    prior high-volume sessions, combined with the frozen price-structure trigger,
    can identify continuation.

### Eleven new successor families

The successor package adds only mechanisms that materially broaden the library. Exact
lookbacks, tolerances, bar authority, stops, targets and exits are frozen before any
new performance is opened.

11. **Bollinger-band mean reversion — `pract_bollinger_mean_reversion_v1`.** Detect a
    price excursion to/outside a frozen Bollinger envelope and require objective
    rejection/re-entry toward the band structure. A band touch alone is not a trade.
    Band width, trend regime, volume and volatility remain explicit conditional
    evidence so ATLAS can learn where mean reversion does or does not work.
12. **ATR volatility-expansion / consolidation breakout —
    `pract_atr_volatility_expansion_v1`.** Identify a normalized low-ATR/range
    contraction, then require directional price/range expansion beyond a frozen
    boundary. ATR measures volatility and supplies adaptive risk geometry; it does
    not choose direction by itself.
13. **VWAP reclaim / reject — `pract_vwap_reclaim_reject_v1`.** Intraday session-VWAP
    setup. Long research signal requires trading below VWAP followed by a
    deterministic reclaim-and-hold; the mirrored reject is the short research
    profile. Closed bars and an explicit confirmation rule are required; a single
    touch/cross is insufficient.
14. **Pivot support/resistance breakout — `pract_pivot_sr_breakout_v1`.** Build
    information-safe structural support/resistance from prior deterministic pivots
    or accepted ranges, then fire only on a confirmed boundary break. Relative
    volume, OBV and breakout distance are recorded as corroborating evidence rather
    than made hidden mandatory filters. This differs from Donchian by using
    structural pivot levels instead of a simple rolling extreme.
15. **Head-and-Shoulders / inverse Head-and-Shoulders —
    `pract_head_shoulders_v1`.** A shared deterministic pivot engine must identify
    the five alternating pivots that form left shoulder, head, right shoulder and
    the two neckline points. Freeze shoulder-similarity, head-prominence, spacing,
    neckline-slope and prior-trend rules. The setup is incomplete until an
    information-safe neckline break. Classic H&S is research-only short; inverse H&S
    is the long counterpart. Volume and formation duration are confirmation features.
16. **Double top / double bottom — `pract_double_top_bottom_v1`.** Require two
    separated tests of approximately the same resistance/support region, a material
    intervening reversal, and a break of the intervening neckline/support/resistance
    before firing. Double bottom is the long counterpart; double top is research-only
    short until short admission is available.
17. **Flag / pennant continuation — `pract_flag_pennant_v1`.** Require an objective
    impulse leg followed by a bounded, short consolidation with frozen retracement
    and contraction geometry, then a breakout in the original direction. Impulse
    strength, consolidation tightness, volume and breakout quality are retained as
    separate evidence.
18. **Triangle breakout — `pract_triangle_breakout_v1`.** Fit deterministic converging
    support/resistance boundaries from repeated prior pivots, classify ascending,
    descending or symmetrical geometry, and fire only on an information-safe
    boundary breakout. Breakout direction controls the signal; the visual pattern
    name alone never does.
19. **ADX/DMI continuation/filter — `pract_adx_dmi_continuation_v1`.** Use DMI for objective directional state and ADX for trend-strength state under one frozen rule. ADX alone never chooses direction. Test whether established directional strength improves continuation expectancy rather than assuming all high-ADX conditions are favorable.
20. **Relative-strength momentum — `pract_relative_strength_momentum_v1`.** Measure PIT ticker out/underperformance versus SPY over a small frozen horizon set and test continuation as its own family. The same relative-strength features may also be shared context for other strategies; sector-relative strength waits for an accepted PIT sector map.
21. **Session-level failed-break/reclaim — `pract_session_failed_break_reclaim_v1`.** Test breach and bounded reclaim of objective previous-day high/low and premarket high/low levels with normalized breach depth, explicit reclaim confirmation, sweep-extreme invalidation and one coherent exit hierarchy. This is observable failed-break/reversal research, not a claim about hidden institutional liquidity.

Cup-and-handle, candlestick-only patterns, stochastic-only systems and other popular
setups remain backlog candidates. Add them later only if they introduce a genuinely
new mechanism or evidence source rather than another correlated restatement of an
existing family.

### Confluence / evidence-strength layer

ATLAS will **not** turn simultaneous strategy alerts into a naive confidence vote.
Every strategy fires independently and keeps its own lineage, outcome history and
standalone statistics. A separate confluence layer asks whether *independent*
corroborating evidence improves conditional probability, net expectancy, downside or
capital efficiency.

Evidence is grouped into at least seven families: **trend**, **momentum**,
**volume/participation**, **price structure**, **volatility**, **chart pattern**, and
**context** (market/sector regime, liquidity, price band, time of day and other
point-in-time state). Raw same-direction strategy count is recorded, but correlated
signals inside one family are capped/regularized so several moving-average-derived
signals cannot masquerade as several independent confirmations. Distinct-family
agreement is measured separately. Opposing/conflicting evidence is preserved as a
negative feature; it is never silently removed.

This is why ATLAS should not initially create a new hard-coded "EMA + MACD" strategy:
the existing EMA-pullback and MACD families remain independently testable, and the
confluence layer can directly measure whether their same-direction agreement adds
value beyond either signal alone.

Research compares three systems: **A) standalone strategies**, **B) explicit
confirmation-filter variants**, and **C) confluence-ranked candidates**. First report
conditional outcome tables without invented manual point weights. If sample size and
stability justify it, a later interpretable conventional probability/expectancy model
may learn weights from training-only walk-forward data. Any displayed 0-100 strength
or confidence must map to a documented calibrated probability, percentile or frozen
score; it cannot be an arbitrary sum of indicators.

Confluence inputs may include primary strategy, distinct evidence-family agreement,
opposing signals, regime, trend, momentum, volume, volatility, structure, liquidity,
estimated cost, signal age and time-of-day. Same-session/future outcomes are forbidden
inputs. Confluence itself is a hypothesis and must beat standalone baselines out of
sample before it can affect qualification or capital priority.

### Controlled calibration and refinement

A losing v1 is evidence, not an instruction either to discard the mechanism
immediately or to tune it until green. After each frozen v1 evaluation, perform one
structured diagnostic review covering regime, liquidity, price band, time, volatility,
setup intensity, entry delay, MFE/MAE, stop/target path, cost drag, unresolved/no-entry
rate, loss concentration, losing streaks and confluence/conflict state.

Per strategy family and research cycle, create **no more than three materially
distinct v2 candidates by default**. Each requires a ledgered failure/opportunity
rationale, practitioner/statistical basis, exact rule change, declared trial count and
untouched evaluation source before performance is opened. Dense threshold sweeps,
tiny parameter stepping and repeated same-sample optimization are prohibited.
Original v1 results remain permanently ledgered. Data used to propose v2 is
training/diagnostic evidence only; v2 promotion requires a fresh walk-forward or other
untouched evaluation under a new fingerprint. Consumed master evidence is never
recycled, and an existing blind window is never reassigned after results are known.

### Implementation order and efficiency

B35 canonical replay, condition/selector analysis, retained-artifact robustness, and exact targeted minute perturbations are complete. The successor **21-family / eleven-new-family** PRE-OUTCOME contract is frozen in `packages/strategies/successor_practitioner_lab.py` and `docs/successor_practitioner_lab_preoutcome.md`; PR #82 merged the exact family/challenger evaluators and shared PIT feature layer without opening successor performance. PR #83 now freezes the portable source/runner contract and restart-safe hash-only source-verification gate under `atlas-successor-development-runner-contract-v2-project-relative-source-binding-preoutcome-no-authority`. It binds the 28 concrete routes to the accepted DEVELOPMENT sources, freezes profile-independent grouping and preregistered outcome/artifact semantics, and keeps project-root/runtime-profile details outside scientific identity. The preflight hashes exact source bytes and opens no bar rows, signals, returns, or outcomes. After PR #83 acceptance, run the workstation hash-only preflight to bind actual V2 source fingerprints; then implement the separate outcome-opening broad evaluator/output runner, prove golden-output/restart/authority behavior, benchmark exact-equivalent worker shapes, and only then open permitted DEVELOPMENT performance. Reuse the six accepted daily families and four B34 intraday families rather than reimplementing them. Shared point-in-time feature extraction, canonical bars, indicator primitives, deterministic pivots, market/relative-strength context, and the validated parallel execution pattern should be reused where exact-equivalent, while every strategy evaluator remains independently testable and deterministic.

The destination is not one universal strategy. It is a library of versioned
mechanisms whose standalone evidence, condition profile, confluence value, costs and
correlation are known well enough for ATLAS to rank good opportunities, abstain when
evidence is weak, and explain why one candidate outranks another.


### Successor selected-path evidence — COMPLETE / NO PROMOTION (2026-09-15)

**Exact-minute execution repair (2026-09-15).** The first exact-minute invocation stopped before any minute source read because the compact `eligibility_assignments.parquet` selector artifact intentionally does not persist `gross_return`, MFE/MAE, or entry/exit timestamps. The minute diagnostic now re-joins those selected assignments to the already SHA-validated normalized opportunity artifacts on the same unique conditioning key used by the accepted option-worthiness analysis (`policy_id`, `native_timeframe`, `instrument_key`, `session_date`, `direction`). Return/comparability bindings are checked before path construction. No minute result was opened by the failed invocation and all research/trading authority remains unchanged.

The retained option-worthiness pass showed that 20-session MFE is too broad to answer whether a signal moves fast and cleanly enough for stock/option construction: even losing routes frequently reached 1-5% favorable excursion eventually. ATLAS therefore froze a separate five-session path diagnostic before opening those results. The completed selected-daily run is bound by contract fingerprint `14d3598599e21a8603f95933368c9bdfaf6480577a51064d6110706a9682d1ca` and analysis fingerprint `e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20`. It covered exactly **35,995** already-selected comparable daily DEVELOPMENT opportunities, entered at the next regular-session open and measured favorable/adverse path through five instrument trading sessions at frozen 1/2/3/5% thresholds. Same-session two-sided daily touches remain unordered; no intraday ordering is inferred from daily bars.

The path result reinforces specialization rather than promotion. The broadest positive diagnostic remains `pract_bollinger_mean_reversion_v1` LONG (n=5,516; mean five-session gross +0.55%; MFE5 5.19%; adverse excursion 4.93%; favorable-before-adverse 43.49% at 2% and 43.65% at 3%). `pract_flag_pennant_v1` SHORT is cleaner but much smaller (n=191; +0.98%; favorable-before-adverse 54.45% at 2% and 50.79% at 3%). `donchian_breakout_20_volume_short_v1` SHORT (+0.72%, n=379), `pract_adx_dmi_continuation_v1` LONG (+0.63%, n=204), and `rsi_recovery_14_trend_long_v1` LONG (+0.47%, n=189) remain bounded specialist hypotheses. Triangle LONG is positive but only n=57 and highly concentrated. These are post-result DEVELOPMENT diagnostics, not a new valid portfolio or historical qualification result.

The important system-level finding is **path quality**: many routes reach 2-3% favorable excursion within five sessions while favorable-before-adverse rates are only about 30-50%. Expected endpoint return alone is therefore insufficient for options. Trade construction must model move magnitude, speed, adverse path, and then contract-specific delta/gamma/theta/vega, IV/skew/term structure, DTE/strike, spread/liquidity and scenario P&L before an option can pass the universal actionability gate. A stock candidate may remain valid when the option expression fails in modes that permit stock fallback.

The arithmetic mean of per-opportunity `five_session_return / MFE` is denominator-unstable when MFE is near zero and produced misleading aggregate values; it is **not** route evidence. Operator output now uses the retained median capture statistic and explicitly labels the mean as unsuitable for comparison. Underlying path/MFE/MAE/threshold artifacts remain unchanged.

The **259** selected comparable intraday opportunities are deliberately separate. They are all `orb_15m_close_retest_v2` and now have a preregistered exact-minute diagnostic: retained actual entry through retained actual exit, frozen 1/2/3/5% favorable/adverse thresholds, exact minute-bar first-touch time, same-minute collisions unordered, and no use of exit-bar high/low extremes after the strategy may already have exited. The accepted serialized native-unit bindings are reused; only selected symbol/month units are SHA-verified and selected symbol/session paths are queried. This is DEVELOPMENT diagnosis only and grants no consumed-master, future-blind, provider, broker, confluence, promotion, PAPER/LIVE or option-trading authority.

After this minute-path closeout, Track B proceeds through failure-specific external research and at most a small bounded set of versioned specialist hypotheses. Track A account simulation/control-plane work remains free to advance using clearly labeled baseline evidence; alpha research does not block product construction.

## How progress is reported

### Reusable validated performance-optimization protocol

The B35 replay established the default ATLAS pattern for expensive deterministic or research workloads. Apply the same pattern, adapted to the workload's own correctness contract, to historical replays, data builds, validation passes, simulations, feature generation, large audits, and other batch work where runtime becomes material:

1. **Instrument before optimizing.** Establish a real baseline on the target workstation: completed work unit, elapsed time, throughput, ETA, worker/thread shape, and restart state. Do not optimize from intuition alone.
2. **Make the job restartable first.** Preserve atomic checkpoints, self-hash receipts, immutable input fingerprints, and validated completed work so experiments or interruptions never require discarding good canonical progress.
3. **Separate science/correctness from execution.** Frozen strategy rules, source scope, validators, outcome mechanics, authority, and final scientific fingerprints must not change merely to improve speed. Runtime metadata and completion order are non-authoritative.
4. **Profile the actual bottleneck.** Test concurrency, I/O shape, Python/object overhead, reusable process-local resources, and data-layout costs independently. More threads or fewer scans are not assumed faster; B35 demonstrated both diminishing concurrency returns and a major single-scan regression.
5. **Use isolated golden-output probes.** Recompute already completed canonical work in a temporary location and require the strongest available equivalence evidence—preferably byte-identical output hashes plus receipt/scientific-field parity—before an optimization may touch the canonical continuation path.
6. **Change one execution layer at a time.** Keep experiments narrow enough that gains or regressions have an attributable cause and can be cleanly reverted.
7. **Tune the real hardware empirically.** Benchmark worker x library-thread combinations on the actual host while reserving enough CPU/RAM/I/O headroom for the OS, remote administration, and coordinator. Keep the fastest scientifically equivalent measured shape, not the configuration that merely looks most parallel.
8. **Reuse infrastructure, not evidence shortcuts.** Safe examples include process-local database connections, immutable calendars, compiled/read-only helpers, and bounded non-scientific caches. Do not bypass source hashes, validators, checkpoint verification, protected-data boundaries, or required model/schema validation solely for speed.
9. **Reject regressions explicitly.** Preserve benchmark evidence for failed ideas so future work does not repeat them. Exact equivalence is necessary but not sufficient: a slower equivalent implementation is rejected unless it solves another material operational problem.
10. **Stop optimizing when execution is tractable.** Among accepted candidates, use the fastest measured scientifically equivalent implementation. Continue searching only when the projected time saved reasonably exceeds the engineering and revalidation cost or a clearly larger safe gain is available.
11. **Resume; do not restart.** Once the execution path is accepted, continue the canonical job from all validated receipts/checkpoints. Benchmark recomputes remain isolated and never advance or erase canonical progress.
12. **Close the loop with real-run evidence.** After the canonical workload completes, record final elapsed time, sustained throughput, interruptions/restarts, resource shape, and any difference from benchmark projections. Use that case history to size and design future long-running ATLAS work.

For B35 specifically, the measured path moved from about **660.6 units/hour** in the serial restart to a final isolated exact-equivalent benchmark of **2,942.2 units/hour** at 10 x 1, while preserving **10/10 byte-identical sampled outputs** and all scientific/authority boundaries. The accepted canonical continuation then reused 82 validated groups and computed the remaining **400 groups / 49,600 units in 11:40:46 at 4,246.7 units/hour**. That sustained real-run rate was about **6.43x the original serial rate** and **44.3% faster than the accepted isolated benchmark**, saving about **63.4 hours** versus serial processing for the remaining 49,600 units. At that sustained rate the equivalent full 59,768-unit workload is about **14.1 hours** instead of roughly **90.5 hours** serial. This completed case is the reference example for the reusable ATLAS efficiency protocol.

**Mandatory long-running runtime observability.** Any ATLAS command expected to run materially longer than an interactive task must expose operator-visible progress without changing scientific authority. At minimum it reports a start timestamp and PID, frozen scope and execution profile, completed/total groups or units and percentage, elapsed time, restart-reused work, throughput, a timestamped heartbeat at least once every 60 seconds even while one work item is long, and an ETA once enough new work exists (otherwise explicitly unavailable). Completion, failure, and interruption report their timestamp and elapsed duration. Terminal output is flushed promptly, and an atomic machine-readable status artifact is maintained for second-terminal and future GUI inspection. Runtime progress/status is **NON_AUTHORITATIVE**: wall-clock fields, worker order, heartbeats, throughput, ETA, and the status artifact never enter scientific identities, source/group fingerprints, receipt hashes, trial identity, strategy decisions, or final result fingerprints. Validated receipts and final scientific summaries remain the completion authority.

Every accepted package reports both scientific control and functioning product
progress. Examples include:

- strategy specified and implemented;
- historical replay completed;
- candidate generated and routed;
- trade and portfolio constructed;
- operational PAPER order planned or submitted under explicit authority;
- position managed and outcome recorded;
- strategy statistics and calibration updated;
- replay/dashboard/GUI control functioning;
- PIT audit, cost policy, protected reads, trial count, fingerprints, and authority
  state preserved.

Implementation uses the largest safe coherent package. Each package begins and
ends with a short plain-English account of its goal, capability change, result,
remaining risk, authority change, and next work. Root causes are repaired at the
owning layer; validators and scientific rules are never weakened to manufacture a
pass.

Documentation is part of acceptance, not cleanup. Every repository-changing
package must update this README and `docs/roadmap.md` together before merge with the
exact current capability, test/CI state when known, safety/authority effect,
unresolved limitations, and next action. Strategy-evidence-changing packages must
also update `docs/strategy_evidence_register.md`. If implementation or strategy
evidence changes but the applicable living documents do not, the package is
incomplete and must not be treated as the new handoff.

## Historical evidence that remains binding

The complete ledger is in the roadmap and immutable closeout documents. Key facts:

- Phase32 is `ACCEPTED_NEGATIVE`; frozen finalist `solvency_distress_short` had
  **46 event rows / 33 signal sessions / 40 unique instruments** versus
  **50 / 20 / 20**; protected stock/SPY returns remained unread.
- Phase32 scientific policy fingerprint:
  `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`;
  protected return rows read = 0; holdout consumed = false.
- Phase31 SEC Form 4 insider-transaction alpha is `ACCEPTED_NEGATIVE`; it produced
  zero survivors, winners, finalists, support, and protected reads.
- XBRL quality/accrual: 200 documents, 170 accrual-ready and 92 profitability-ready
  issuers; zero development passers; protected reads zero.
- XBRL protected return rows read = **0**.
- XBRL retained lineage: Phase32 merge `69f8aa81289934b71f2652482c747391917c15a3`;
  contract `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`;
  `FEASIBILITY_PASS`; feasibility fingerprint
  `6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`;
  accepted evidence fingerprint
  `33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`;
  PIT audit fingerprint
  `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`.
- Schedule 13D/13G: 3,652 predictors and 2,412 usable development outcomes; zero
  passers; protected reads zero; closeout fingerprint
  `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`.
- FINRA: 19,343 predictors; `rapid_short_cover_crowded_long` had 257 protected rows
  versus 300 required; no outcomes opened; closeout fingerprint
  `bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`.
- Diluted EPS: three ambiguous contexts and six metadata contradictions reproduced
  by clean authoritative replay; no outcomes opened; closeout fingerprint
  `29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc`.
- Form 13F: 10,431 malformed CUSIPs across 374 accessions reproduced exactly in
  original EDGAR XML; no outcomes opened; closeout fingerprint
  `0375d5567e0547c151f9fb140309aa568d17528246e611a68fa5984a1c481acd`.

These results may inform future work but may not be retuned into positive findings.
The retained master holdout was subsequently consumed exactly once by the frozen
A33/B33 V2 walk-forward on 2026-09-07; that consumption does not rewrite the
separate earlier branch statements below, which correctly record zero protected
return reads for those experiments. LIVE and automatic broker failover remain
disabled.

### Retained exact historical validator statements

The following literals are retained as **historical evidence**, not as the current
product dependency. They allow accepted phase validators to continue recognizing
the facts they were written to certify:

- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well.
- Phase32 policy fingerprint: `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`.
- Phase32 frozen source evidence: 46 event rows / 33 signal sessions / 40 unique instruments.
- Phase33 signal-to-trade remains blocked was the superseded roadmap rule; its LIVE-authority conclusion remains binding, while baseline Product construction is now allowed.
- XBRL protected return rows read = **0**; closeout fingerprint `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.
- LIVE and automatic broker failover remain disabled.

## Successor Strategy Lab direction — 21 families

The accepted B35 targeted perturbation diagnostic is closed. Track B now proceeds under a new preregistered successor research package rather than modifying B35 v1. The next broad historical experiment targets **21 economic strategy families** plus a bounded set of explicitly versioned challengers. The ten retained families remain immutable baselines; eleven distinct additions are planned: Bollinger mean reversion, ATR/range expansion, VWAP reclaim/reject, pivot support/resistance breakout, ADX/DMI continuation/filter, relative-strength momentum versus market/sector, deterministic head-and-shoulders/inverse, double-top/bottom, flag/pennant continuation, triangle breakout, and objective session-level failed-break/reclaim. Nearby parameterizations remain members of one economic family for multiplicity and confluence.

The Opening Range family receives two high-priority successor policies, not two new independent families: a **Stocks-in-Play 5-minute ORB/opening-momentum** policy using abnormal same-time opening participation and executable liquidity/volatility controls, and a **15-minute ORB close + bounded retest confirmation** challenger designed to test false-break reduction. The failed-break/reclaim family uses only observable PIT levels (initially previous-day high/low and premarket high/low) and makes no hidden-liquidity or ICT/SMC claim.

The successor experiment also adds a shared PIT context layer before confluence/ranking: broad-market alignment, ticker relative strength/weakness versus SPY, bounded higher-timeframe trend, trend maturity/extension, participation/relative volume, overnight gap, signal time, price band, realized volatility, and liquidity/execution quality. Sector-relative strength waits for an accepted PIT sector map. Context is measured first for incremental value and is not automatically a hard filter. Confluence remains separate from standalone strategy firing and counts independent evidence families rather than correlated indicators. Portfolio loss limits, simultaneous-position competition, concentration, and capital allocation remain account/PAPER-layer questions; fixed arbitrary stops/targets, human psychology rules, small discretionary watchlists, and reopened failed SEC hypotheses are not part of this successor strategy package.

The large successor run must report standalone v1 baselines, each frozen challenger, condition coverage, win rate, payoff ratio, net expectancy/net-R, cost decay, MFE/MAE, drawdown, concentration, fold stability, and abstention. The objective is broader **economically viable condition coverage**, not maximizing win rate or forcing every strategy to trade broadly. Candidate context interactions are frozen before performance, tested incrementally with multiplicity control, and any favorable condition-gated successor requires new untouched/prospective evidence before authority promotion.


## 2026-09-15 strategy-development and trade-expression direction

The successor DEVELOPMENT standalone and conditioning work has now moved ATLAS from broad strategy implementation into a repeatable **Strategy Development Cycle**. Existing strategy versions are not discarded when a broad or conditioned result is weak. Their observed v1 evidence remains immutable, and ATLAS uses the result to diagnose where the mechanism works, where it fails, and whether one or more bounded versioned revisions are justified. Operationally the cycle is:

`baseline -> diagnose -> targeted external research -> bounded revision -> retest -> specialize or park -> move on`

A strategy can improve in two economically useful ways: **higher edge per qualified opportunity** or **more quality opportunities without destroying edge/risk quality**. After each baseline, diagnose direction, regime, relative strength, trend/extension, volatility, liquidity, price band, participation, signal time, entry/confirmation, exit behavior, MFE/MAE, stop/target path, cost drag, false-signal rate, concentration, fold/year stability, move magnitude/speed, and option-worthiness. Then research the observed failure/opportunity mechanism using credible academic literature, original indicator/strategy sources, exchange/broker/quant research, books, respected practitioner material, and community experience. External popularity is never proof; it is evidence for a bounded candidate change. By default no more than three materially distinct revisions per family per research cycle are admitted, dense parameter sweeps remain prohibited, and the data that motivates a revision cannot independently validate it. Parked strategies remain versioned research assets and may be revisited when new data, research, market behavior, or option-source capability justifies it.

ATLAS is also explicitly an **options-capable and options-oriented** trading system, while preserving stock trading as a valid expression. The operator-facing product should support four trade-expression modes: `OPTIONS_ONLY`, `STOCKS_ONLY`, `OPTIONS_PREFERRED`, and `STOCKS_PREFERRED`. These are preferences/permissions, not commands to force a trade. Every signal must pass a universal **economic actionability gate** before capital is committed. If expected profit is too small relative to costs, spread, slippage, uncertainty, capital consumption, downside, liquidity, or portfolio risk, ATLAS abstains regardless of mode.

The strategy/forecast layer must estimate the underlying move before choosing the instrument: direction, expected move magnitude, expected holding/time-to-move window, uncertainty/distribution, and useful thresholds such as probabilities of positive, 1%, 2%, 3%, 5%, 1-ATR and 2-ATR moves, together with MFE/MAE and path/speed information. The trade-construction layer then evaluates whether available option contracts can profit from that projected move within the projected timeframe. A good underlying opportunity may therefore remain a stock candidate even when every option contract is rejected; in `OPTIONS_ONLY` mode the same case abstains.

Option construction must account for strike/expiration/moneyness, delta, gamma, theta/time decay, vega, implied-volatility level and plausible change, skew/smile and term structure when available, interest rates, dividends/early-exercise effects for American-style equity options, bid/ask spread, volume/open interest/liquidity, known events such as earnings, expected option P&L, probability of profit, downside/loss probabilities, and expected value per dollar of capital/risk. Black-Scholes-Merton and related pricing/Greek models are reference/scenario tools, not historical option-P&L truth. Apparent cheapness is **model-relative undervaluation evidence** that must be checked against the observed option surface and executable liquidity. Historical option qualification ultimately requires real point-in-time option-chain/quote/IV evidence rather than synthetic stock-return translation.

Efficiency remains a design constraint. Broad market/strategy discovery stays cheap; detailed option-chain retrieval and scenario pricing occur only after a stock candidate clears strategy/forecast/actionability gates. Cheap option filters narrow the chain before detailed scenario valuation, and vectorized/cached pricing should keep compute cost small relative to market-data acquisition. The intended flow is:

`broad discovery -> strategy/condition evidence -> underlying move/time distribution -> actionability -> permitted instrument modes -> option-chain filter/scenario economics -> stock/option/abstain -> portfolio risk`

This direction does not grant historical, PAPER, LIVE, strategy, selector, or option-trading authority. It defines the product and research requirements that subsequent implementation must satisfy.

### Successor option-worthiness diagnostic package — PRE-RUN

ATLAS now has a separately authorized DEVELOPMENT-only diagnostic package that derives option-relevant **underlying** move evidence from the already accepted successor conditioning artifacts without rereading the raw market lake. It compares all comparable DEVELOPMENT opportunities, the walk-forward test population, and the frozen conditioning-v1 selected population; reports route/direction MFE/MAE distributions, 1/2/3/5% favorable/adverse excursion frequencies, daily 1/5/20-session behavior, intraday holding-time behavior, selected-fold stability, and an exact 28-route / 21-family implementation inventory. Daily retained MFE/MAE covers the full 20-session diagnostic window, while intraday MFE/MAE covers entry-to-actual-exit; the report labels this explicitly and does not reinterpret daily threshold hits as five-session hits. It creates no new selector, ranking score, confluence rule, or strategy authority.

The retained artifacts do **not** preserve exact threshold-crossing timestamps, entry ATR magnitude, complete MFE/MAE path ordering, hold-period realized-volatility paths, or historical option chains. Therefore this package explicitly refuses to claim exact time-to-1/2/3/5% moves, 1ATR/2ATR hit frequencies, path ordering, historical option P&L, or contract-level Greeks/IV/skew/term-structure evidence. Those require separate future source/path packages. Repository acceptance opens no new empirical diagnostics; the workstation command remains separately gated.

### Successor selected-path timing diagnostic (2026-09-15)

The retained-artifact option-worthiness diagnostic completed successfully with analysis fingerprint `6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3`. It confirmed 28 replayed routes / 21 economic families and 36,254 walk-forward-selected comparable opportunities. The retained daily MFE/MAE fields span **through 20 sessions**, so their high 1%/2%/3%/5% favorable-excursion rates must not be interpreted as five-session or option-speed evidence. Losing routes also frequently reached large favorable excursions somewhere in that long window.

The next frozen diagnostic is therefore `successor_selected_daily_path_v1`: it reads only the already-selected comparable **daily** opportunities (35,995; about 99.3% of selections) against the accepted DEVELOPMENT daily lake, enters at the same next-session open, and measures five-session MFE/adverse excursion, first 1%/2%/3%/5% favorable/adverse touch session, session-level first-touch ordering, exit capture versus available MFE, and peak give-back. Same-session high/low collisions remain explicitly unordered because daily bars cannot reveal intraday ordering. This is post-result DEVELOPMENT diagnosis only; it creates no strategy, selector, confluence, PAPER, LIVE, promotion, or option-trading authority. The 259 selected ORB minute opportunities remain deferred to a separate minute-path diagnostic rather than mixing minute and daily path semantics.

## Exact-minute ORB closeout and literature-fidelity v2 freeze — 2026-09-15

The selected-minute diagnostic is complete under analysis fingerprint `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`. It reopened only the 259 already-selected/comparable DEVELOPMENT `orb_15m_close_retest_v2` opportunities, verified 218 bound native minute units by exact path and SHA-256, and read 55,581 entry-to-exit minute bars. The consumed master and future blind remained closed.

The exact path result diagnoses a **direction/order failure, not a lack-of-movement failure**. LONG (`n=157`) finished at -0.71% gross / -1.20% primary / -1.70% stress with 8.82% MFE and 7.78% MAE; favorable-first frequency fell from 48.41% at 1% to 40.76% at 5%. SHORT (`n=102`) finished at -0.01% gross / -0.51% primary / -1.01% stress with 3.85% MFE and 3.88% MAE; favorable-first frequency fell from 42.16% at 1% to 29.41% at 5%. Large moves occur, but the retained directional retest entry does not order those moves favorably often enough to justify leverage or an option-expression rescue. Historical option P&L remains unclaimed.

The next opening-range revision is therefore **not** another 15-minute retest parameter tweak. ATLAS preserves `orb_stocks_in_play_5m_v1` unchanged and preregisters a separate `orb_stocks_in_play_5m_literature_v2`, anchored to Zarattini, Barbon & Aziz, *A Profitable Day Trading Strategy For The U.S. Equity Market* (Swiss Finance Institute Research Paper 24-98 / SSRN 4729284). The v2 freezes: first-five-minute range; price > $5; prior-14-session average share volume >= 1,000,000; prior ATR14 > $0.50; first-five-minute relative volume versus the prior 14-session average >= 1.0; top-20 daily relative-volume rank; first-candle direction with doji abstention; direction-specific stop entry at the opening-range boundary; 10% ATR14 stop; and end-of-day exit. ATLAS retains its stricter 0/10/25/50/100-bps cost grid with 50/100 bps primary/stress diagnostics.

The frozen pre-outcome contract fingerprint is `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`. This is a DEVELOPMENT-only, B35/opening-range-motivated challenger. Because both the internal diagnosis and the published study overlap DEVELOPMENT-era evidence, DEVELOPMENT can diagnose this v2 but cannot self-validate or promote it. Master/future/provider/broker/PAPER/LIVE/confluence/option-trading authority remains zero/false.

## 2026-09-15 — literature-fidelity 5-minute ORB v2 DEVELOPMENT runner

The retained `orb_15m_close_retest_v2` exact-minute path diagnostic is closed with analysis fingerprint `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`: 259 selected/comparable cases across 208 symbols and 218 SHA-verified native units showed substantial move magnitude but unfavorable path ordering. LONG averaged -0.71% gross / -1.20% at the 50-bps primary cost assumption with 8.82% path MFE and 7.78% path MAE; SHORT averaged -0.01% gross / -0.51% primary. Favorable-first frequency was below 50% at every measured 1/2/3/5% threshold in both directions. The diagnostic therefore motivates a direction/selection redesign rather than leverage or another 15-minute retest parameter sweep.

A separate `orb_stocks_in_play_5m_literature_v2` is preserved under base strategy contract `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`. Its DEVELOPMENT analysis contract is frozen at `87ee4ff703f8040d88c22147444aa992d196ab49be91dc749e3035e3c15e739b`. Before any v2 historical outcome was opened, the runner was corrected to honor the accepted V2 source semantics: raw daily OHLC is reconstructed only for ATR14 using the accepted unadjusted-close price factor, while the one-million-share prior-volume gate consumes Alpaca's provider-native split-adjusted daily volume exactly as supplied; no inverse-price-factor volume transform is permitted. First-five-minute relative volume requires the exact previous 14 XNYS sessions to each contain a complete 09:30-09:34 ET five-bar snapshot, so missing opening sessions cannot be bridged with older observations.

Execution uses a two-stage efficiency funnel. Stage 1 SHA-verifies the accepted DEVELOPMENT minute units and reads only the exact five opening regular-minute bars across the 482 accepted symbol groups, computes the frozen filters and deterministic top-20 relative-volume cross-section, and lets a doji consume its rank slot while abstaining. Stage 2 opens full-session minute paths only for the selected directional candidates, applies the frozen stop-entry/gap-through/0.10xATR14/EOD mechanics, treats same-minute entry-stop collisions as unordered/noncomparable, and reports the 0/10/25/50/100-bps cost grid plus 1/2/3/5% move timing. Per-group SHA-bound receipts make both stages restart-safe; runtime worker count is operational and excluded from scientific identity.

**Outcome status remains UNOPENED at this repository state.** The next permitted evidence action is the explicitly gated DEVELOPMENT workstation run after this runner package is accepted. That run cannot self-validate or promote the revision because the hypothesis was motivated with DEVELOPMENT evidence and the external study overlaps the DEVELOPMENT era. Consumed master and future blind remain closed; provider/broker reads and writes, PAPER, LIVE, promotion, confluence, historical option-P&L, and option-trading authority all remain zero/false.


## 2026-09-16 — ORB v2 DEVELOPMENT closeout and trade-expression foundation

The frozen `orb_stocks_in_play_5m_literature_v2` DEVELOPMENT diagnostic is complete under analysis fingerprint `cc6c34b18479aa76558e3c73cbc17ae75d85dd2c7b45d3806a8ac00d17b3a035`. It produced 4,957,662 five-minute opening snapshots, 62,516 eligible rank-pool rows, 40,606 top-20 selections, 40,345 directional candidates, 33,773 entries and 23,412 comparable outcomes. Aggregate comparable mean was **+0.12% gross, -0.38% at the frozen 50-bps primary cost and -0.88% at 100 bps**, with 1.27% mean MFE and 0.41% mean adverse excursion. LONG and SHORT were economically similar. The setup is therefore preserved as a cost-sensitive research reference but is **not promoted**. The exact immutable closeout is `docs/research/orb_stocks_in_play_literature_v2_development_closeout_20260916.md`.

A material execution-path diagnostic is retained rather than optimized away: 10,361 entries, about 30.68% of entered cases, had entry and the frozen 0.10xATR14 stop touched in the same minute and remain unordered/noncomparable. Changing that stop, relative-volume gate, top-20 rank, range length, entry timing or exit after seeing this result would create a new version and would require a newly frozen hypothesis plus untouched/prospective evidence. Historical option P&L remains unclaimed; the 1/2/3/5% path statistics are underlying option-worthiness evidence only.

Track A now has a pure product-side trade-expression foundation under contract `a9341b7c0e6399165403cfa3d2f33e9f3b2749194ce39d41044a260dbd5fef4c`. It implements `OPTIONS_ONLY`, `STOCKS_ONLY`, `OPTIONS_PREFERRED` and `STOCKS_PREFERRED` as permission/preference modes behind a universal economic actionability gate. There are deliberately no hidden production thresholds: expected value, return on capital, probability of profit, loss/gain, execution-cost burden, liquidity and material-superiority thresholds must be supplied explicitly by policy. Options additionally require complete contract, Greeks, IV, liquidity and event context. Model-relative undervaluation is evidence only and can never independently make an option actionable. Preferred modes may use a materially superior alternate expression; no mode can force an uneconomic trade. This layer creates no broker read/write, PAPER, LIVE or strategy-promotion authority.

## 2026-09-16 — underlying move/time forecast foundation

Track A now has a versioned, broker-neutral underlying move/time forecast contract: `93525886fb2f0e8af3821caba8c87854ab1d732d5619dc02838df0ef98d931e1`. This object sits **before instrument selection** and carries the distribution evidence needed by the economic actionability layer: signed-return mean/median and p10/p25/p75/p90, probability of a positive underlying return, MFE/MAE, forecast horizon, source/sample lineage, uncertainty, and direction-relative move-threshold timing/path probabilities.

Directional forecasts may carry one or more unique move thresholds such as 1/2/3/5%; larger thresholds cannot report a higher touch probability than smaller thresholds. Favorable-first, adverse-first and same-interval-collision probabilities are validated for internal consistency, and favorable timing must fit inside the forecast horizon. Neutral forecasts intentionally carry no favorable/adverse threshold table. Unavailable forecasts remain first-class objects but may not carry a partial distribution.

The schema enforces PIT ordering (`evidence_cutoff_utc <= forecast_created_utc`), timezone-aware timestamps, finite numerics and a SHA-256 source fingerprint. It is explicitly underlying-only: historical option P&L, instrument-selection authority, broker reads/writes, PAPER, LIVE and strategy-promotion authority are all forbidden. The existing Phase 13 equity-only case-file contract and Phase 15 equity execution path are unchanged; later simulator integration will use a separately versioned product path rather than mutating those accepted contracts.

## 2026-09-16 — Stock economics adapter foundation

Track A now has a deterministic underlying-forecast-to-stock-economics adapter under frozen contract `68f4b7ca0e4f86f07bf20afa1c7e6e5aa9708c081db44cc3c18f8123e711f924` (`atlas-stock-economics-adapter-v1`). It consumes the accepted `atlas-underlying-move-time-forecast-v1` object and produces the `STOCK` `EconomicCandidate` already consumed by the universal trade-expression/actionability gate. Unavailable or neutral forecasts do not create a stock candidate.

The adapter deliberately keeps every economic assumption explicit. Position notional and capital reserved are separate inputs; no leverage, margin or collateral rule is inferred. Entry/exit slippage, round-trip commissions/fees, horizon borrow cost and horizon financing cost are supplied as explicit nonnegative inputs. Expected gross P&L is the direction-adjusted mean signed underlying return times position notional; expected net value subtracts all-in expression cost; expected return on capital divides net value by explicitly reserved capital. Forecast MFE/MAE scale expected gain/loss evidence. Net probability of profit is an explicit post-cost scenario input and cannot exceed the forecast's gross directional sign probability. The candidate preference score is expected return on capital, so negative economics remain negative rather than being clamped or rescued.

Bearish stock construction also carries an explicit shortability input. If the stock is not shortable, the economic candidate is preserved with `executable=false` so the downstream gate can explain the rejection. The adapter performs no provider/broker reads or writes, chooses no order quantity, creates no order, and grants no PAPER, LIVE, option-trading, confluence or promotion authority.

## 2026-09-16 — Deterministic simulation decision record

Track A now composes the accepted product-side decision layers into one immutable simulation record under frozen contract `62dceacde38687828e610c096d8c0a39479d5bc65b26b56aed2bf4164d8c8af8` (`atlas-simulation-decision-record-v1`). The record binds the full underlying move/time forecast, original stock-economics assumptions, calculated stock economics, exact universal `ActionabilityPolicy`, selected trade-expression mode, normalized option economic candidates when supplied, gate evaluations, final stock/option/abstain decision and reason-code lineage. It records the forecast instance fingerprint plus the accepted forecast, stock-economics and trade-expression contract fingerprints so a simulator result can be traced to the exact decision inputs that produced it.

Decision time is an explicit timezone-aware input and cannot precede forecast creation. Option candidate input order is normalized before evaluation and fingerprinting, making replay independent of caller ordering. Ignored instruments are not erased: for example, `OPTIONS_ONLY` retains the stock economics but explicitly records that the stock gate was not evaluated by mode, while `STOCKS_ONLY` retains supplied option candidates with equivalent not-evaluated lineage. The final record fingerprint changes when evidence, stock assumptions, actionability policy, mode, option candidates or decision timestamp changes.

This record is a simulation/control-plane artifact only. It performs no provider or broker access, creates no order, and grants no PAPER, LIVE, promotion or confluence authority. Option candidates can now be produced by the separately versioned `atlas-option-scenario-economics-adapter-v1` and supplied to this unchanged decision-record contract. Historical option P&L remains unclaimed.

## 2026-09-16 — Deterministic simulation account-state foundation

Track A now has the first explicit product-side account state under frozen contract
`2460956a47dfa3f73c157b5e2f60aa710b10dabb0c1a7115309056d06c1a588b`
(`atlas-simulation-account-state-v1`). It consumes accepted
`atlas-simulation-decision-record-v1` objects and models stock-only capital
reservation and opportunity competition without pretending that a reservation is an
execution fill.

The v1 state tracks account equity, currently unreserved cash, reserved capital,
gross stock exposure, and active stock reservations keyed to the originating
decision-record fingerprint. A selected stock decision reserves the exact capital
preserved by the accepted stock-economics adapter; its explicit stock position
notional becomes gross exposure. Release returns that same capital and removes that
same exposure. Because this layer has no fill, mark-to-market, or realized-P&L
authority, equity is invariant in v1 and `cash + reserved_capital == equity` is a
fail-closed accounting invariant.

Every decision path remains auditable. ABSTAIN, insufficient-capital rejection, and
a selected option whose account capital/risk semantics are not yet accepted all
create deterministic ledger events without changing account amounts. Duplicate
decision application and duplicate release are idempotent. Multiple decisions
compete deterministically in decision-time order with the decision-record fingerprint
as the stable tie-breaker. Every event binds before/after state fingerprints, and
ledger replay must reproduce the exact final state or fail closed on altered lineage.

This package deliberately does not infer margin, leverage, option collateral,
position quantity, fills, P&L, mark-to-market, broker behavior, or account-level risk
rules that are not already accepted upstream. Provider/broker reads and writes,
order creation, fill simulation, PAPER, LIVE, promotion, and confluence authority
all remain false. Phase 13 remains the separate broker-neutral risk/planning gate;
the A34 research account replay remains historical research evidence rather than the
product simulation truth.

The separately versioned option scenario-economics adapter is now implemented
under frozen contract `798b05ab3867058865301c35a52491ee9a8cde82c6f1b019b8d27bae34e88178` (`atlas-option-scenario-economics-adapter-v1`). It may
produce option decision-support candidates, but option capital/risk semantics still
fail closed in the account simulator. The next Track A package is therefore an
explicit option capital/risk reservation contract; it must not reuse stock notional,
margin, or collateral assumptions. The Strategy Evidence Register remains unchanged
because this is product architecture rather than strategy evidence.


## 2026-09-16 — Option scenario-economics adapter foundation

Track A now has a separately versioned option scenario-economics adapter under
frozen contract `798b05ab3867058865301c35a52491ee9a8cde82c6f1b019b8d27bae34e88178` (`atlas-option-scenario-economics-adapter-v1`). It consumes
the accepted underlying move/time forecast plus `OptionCandidateEvidence` and emits
the same `OPTION` `EconomicCandidate` consumed by the universal actionability and
trade-expression layer. V1 is intentionally bounded to long, single-leg,
direction-aligned calls for bullish forecasts and puts for bearish forecasts;
unavailable/neutral forecasts and direction-mismatched contracts do not create a
candidate.

The adapter does not manufacture an option-return distribution from sparse Greeks.
Expected, favorable, and adverse terminal option premiums plus model probability of
profit are explicit outputs of a separately identified and SHA-256-fingerprinted
scenario model, and that model must bind the exact underlying-forecast instance
fingerprint. The full `OptionCandidateEvidence` snapshot is also SHA-256-fingerprinted
and bound into the economics result and candidate identity, so changes to delta, IV,
open interest, volume, eligibility or quote evidence cannot silently reuse an older
candidate. Scenario prices must satisfy `adverse <= expected <= favorable` and the
holding period cannot exceed contract DTE. Current midpoint is the valuation
reference; entry executes economically at the ask, so the entry half-spread is
explicit. Exit slippage, commissions, and fees are explicit nonnegative costs.
Expected gross P&L is `(expected_terminal_premium - current_mid) * multiplier *
contracts`; all-in expression cost adds entry spread plus explicit exit/cash costs;
net value and return on capital remain signed and are never clamped positive.

Completeness is separately auditable across option contract evidence, delta/gamma/
theta/vega, current IV plus percentile/skew/term context, quote/open-interest/volume
liquidity, event context, and rates/dividends. Incomplete context can remain visible
as an economic candidate but fails the existing universal option gate. Upstream
option-screen rejection, unacceptable in-horizon event risk, executability failure,
and risk-budget rejection also remain explicit. A supplied reference-model premium
above the executable ask marks only `MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY`; it is
not historical option-P&L truth or independent trading authority.

The option `capital_required_dollars` value is the economic denominator used to
compare return on capital, but for a long option it may never be below the explicit
ask-debit cash requirement (`ask * contract_multiplier * contracts`). This prevents
artificial ROC inflation before account admission. The value still grants **no
simulator option reservation/collateral semantics**. It also performs zero provider/broker reads or
writes, creates no order, claims no historical option P&L, and grants no PAPER,
LIVE, promotion, or confluence authority. Historical option qualification still
requires accepted point-in-time option-chain/quote/IV evidence rather than synthetic
translation from stock returns.

Immediate Track A continuation is the separately versioned option capital/risk
reservation layer. It must define long-option debit/max-loss cash reservation and
option-specific exposure/accounting without mapping stock gross-notional semantics
onto options. Fill/mark-to-market/outcome authority remains a later package. The
Strategy Evidence Register is intentionally unchanged by this product-only work.

## 2026-09-16 — Long-option capital/risk reservation terms

Track A now has a separately versioned broker-neutral long-option reservation-terms
contract under frozen fingerprint
`26835cbab3e551f0f7514e8537d823cb23d5db1f440362d20b1ba7493ff6aa64`
(`atlas-long-option-capital-risk-reservation-v1`). It binds an accepted selected
OPTION decision to the exact simulation-decision fingerprint, exact accepted option
economics result, exact full `OptionCandidateEvidence` fingerprint, exact underlying
forecast fingerprint, and selected candidate fingerprint. Quote-only similarity is
not enough: changing non-price evidence such as open interest invalidates the
reservation lineage.

V1 supports only long single-leg, direction-aligned calls and puts. Entry premium at
risk is the accepted executable ask debit (`ask * multiplier * contracts`). Reserved
capital is that debit plus an explicit nonnegative cash-fee reserve, max-loss cash is
exactly the reserved capital, and the already-selected option economic capital must
cover the entire reservation. Delta-equivalent underlying notional is recorded as a
separate signed/absolute option exposure measure and never mutates or reinterprets
the stock account state's gross-notional field.

This package creates immutable reservation **terms only**. It does not mutate
account state, reserve cash, create orders/fills, mark to market, realize P&L, read or
write a provider/broker, or grant PAPER, LIVE, promotion, or confluence authority.
The next Track A package is the separately versioned option-aware simulation
account-state extension: deterministic admission/reservation/release and replayable
ledger lineage using these exact terms while keeping stock gross exposure and option
delta-equivalent exposure separate. Fill, mark-to-market, realized-P&L, and broker
authority remain later packages. The Strategy Evidence Register is intentionally
unchanged because this is product architecture, not strategy evidence.

## 2026-09-16 — Stock-option simulation account-state v2

Track A now has a broker-neutral reservation-only account model for both stock and
accepted long-option expressions under frozen contract fingerprint
`1e9da000571d02eb8fe4d317d770fdef25fb35a527ad177d1a87a6794c9592e5`
(`atlas-simulation-account-state-v2-stock-option-reservations`). The accepted v1
stock-accounting arithmetic is preserved, while v2 strengthens stock lineage by
requiring the exact chosen-candidate fingerprint. Option admission additionally
requires the separately accepted long-option reservation terms and their exact
decision, candidate, forecast, economics, and option-evidence lineage.

The state uses one unreserved-cash pool but never conflates instrument economics.
Stock reserved capital and stock gross notional remain separate from option reserved
capital, signed/absolute option delta-equivalent notional, option max-loss cash, and
option premium at risk. Reservation-only equity remains invariant and every state
must satisfy `cash + stock_reserved_capital + option_reserved_capital == equity`.
Missing option terms and insufficient unreserved cash fail closed. Releasing a stock
or option reservation restores exactly the reserved cash and exposure fields; it does
not invent a fill, gain/loss, mark, margin, collateral, or leverage event.

The mixed stock/option ledger is deterministic, chronological, idempotent,
fingerprint-linked, and replayable. Reservation and release events preserve exact
decision and, for options, reservation-terms/economics lineage. Stock gross notional
never includes option exposure, and option delta-equivalent exposure is never
reinterpreted as stock notional. No provider/broker reads or writes, order creation,
fill simulation, mark-to-market, realized P&L, PAPER, LIVE, promotion, or confluence
authority is granted.

## 2026-09-16 — Broker-neutral simulated entry-fill evidence

Track A now has a deterministic complete-entry fill-evidence boundary under contract
fingerprint `e271ba5c66fe9bc41b7f81945a1ef8152a2eeae091b27f6efd4859bacd2d8668`
(`atlas-simulated-entry-fill-evidence-v1`). It consumes an exact active account-state
v2 reservation, the exact simulation decision record and explicit source-bound fill
price/timestamp/fee evidence. The package records evidence only: it does not release a
reservation, mutate the account, create an open position, mark to market, realize P&L,
read/write a provider or broker, create an order, or grant PAPER/LIVE/promotion/
confluence authority.

Stock fills preserve the reservation's accepted economic gross notional and derive
complete simulated share quantity from explicit fill price; fractional simulation
quantity is allowed. Stock cash funding, margin, collateral, leverage and short-sale
proceeds remain deliberately unresolved because accepted stock economic capital can
differ from gross notional. Option fills require the exact accepted long-option
reservation terms: contract count and multiplier remain frozen; premium debit cannot
exceed the reserved ask debit; entry fees cannot exceed the separate fee reserve;
total cash debit cannot exceed reserved capital; and any unspent reserve is explicit.

Explicit funding/collateral semantics are now frozen under contract `f76d77ebbf138924a22813773ad27276b0fa71691ddff1d21040171c7b6d3821`
before any fill may become an open position. Fully cash-funded bullish stock longs may
use their existing reservation plus proven unreserved cash; stock shorts remain
unsupported until a separate short-collateral/proceeds model is accepted. Long-option
debit funding reuses the exact accepted fill evidence. The next bounded Track A package
is deterministic reservation/fill/funding -> open-position and cost-basis account
state. The Strategy Evidence Register is intentionally unchanged because this package
changes product simulation architecture only.

