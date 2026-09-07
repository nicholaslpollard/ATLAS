# ATLAS

**Autonomous Trading, Learning, and Analysis System**

**Current as of 2026-09-07 (UTC). This README and `docs/roadmap.md` are the only
living project documents. Every continuation chat must read both in full before
making recommendations or changes.**

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
2. Read [`docs/roadmap.md`](docs/roadmap.md) for the complete mission, evidence,
   practitioner-strategy catalog, testing design, gates, and ordered work.
3. Inspect code, tests, immutable phase evidence, and Git history only as needed to
   perform the active roadmap package. Those materials support the two living
   documents; they do not compete with them as current plans.
4. If the two living documents conflict, stop and reconcile both in the same change
   before proceeding.
5. Every repository-changing implementation package must update this README and
   `docs/roadmap.md` in the same commit before it is accepted or merged. The update
   must state the package goal, capability change, result/test evidence, exact
   authority or safety impact, unresolved limitations, and next work. A future chat
   must be able to reconstruct the current product and research state from these two
   living documents without depending on a prior conversation window.

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
- Alpaca SIP V2 is now the immediate data-foundation priority. Empirical sizing
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
- A separate daily reference-feature overlay now supplies the exact indicator
  transitions needed by those policies without changing the accepted 33-feature
  core. Intraday, premarket, and opening-session features remain deferred.
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
be silently reused as V2 input. Earlier source limitations do not authorize invented
intraday history; V2 minute semantics remain subject to the finite B34 audit.

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
deferred to its own finite research package. Native minute evidence is hash-verified,
but extended-hours completeness and intraday strategy readiness remain a separate
B34 gate before gap, opening-range, or premarket performance may be opened.

## How progress is reported

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
unresolved limitations, and next action. If implementation changes but the two
living documents do not, the package is incomplete and must not be treated as the
new handoff.

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
The protected holdout remains unconsumed as of this repository handoff; the
authorized local walk-forward command will change that status permanently and its
receipt becomes the authority for the workstation result. LIVE and automatic broker
failover remain disabled.

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
