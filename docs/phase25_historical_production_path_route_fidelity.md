# Phase 25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence

**Status: ACTIVE / GATE 2 ACCEPTED / GATE 3 ACQUISITION PREREGISTRATION**

Upstream authority: Phase24 accepted merge `15b77321d4815f9f52fe74d47ba32fee8127526a`; synchronized `main` handoff `71063b510953aca87b253f5b3b0d42954a6abf0a`.

## Purpose

Phase24 established that simple daily rule tightening does not earn robust support under the stronger preregistered evidence framework. It also exposed a population-fidelity mismatch: historical Phase11/24 strategy studies evaluate broad daily rows with broad market-regime routing, while production strategy promotion is reached only after PIT universe routing, multi-timeframe discovery, discovery-state hysteresis, WARM/HOT directional qualification, and market/ticker route compatibility.

Phase25 asks a narrower question before inventing new strategies:

**Does strategy evidence materially change when the historical population is reconstructed to match the production candidate path?**

The initial experiment holds incumbent strategy rules and the three-session forward-return outcome fixed. The independent variable is the historical population/routing path.

## Authority boundary

Phase25 Gates0-3 are local analytical/planning research only.

Allowed:

- read accepted local canonical/reference/universe/feature/discovery/regime/identity artifacts;
- inventory their PIT coverage and lineage;
- measure provider-native ticker first-seen/reference/identity coverage;
- prove discovery-population equivalence between a full PIT reference snapshot and its active-only subset on already materialized local evidence;
- preregister the exact missing-session acquisition scope and source/query/completeness requirements;
- write local Phase25 research/validation artifacts.

Forbidden unless a later separately reviewed gate explicitly changes the contract:

- provider reads or writes;
- broker reads or writes;
- order submit/replace/cancel/close/flatten;
- Phase21 PAPER submit authority;
- Phase22 execute;
- LIVE;
- automatic broker failover;
- browser execution authority;
- scheduler/daemon authority;
- PostgreSQL runtime promotion;
- production ML retraining/replacement;
- Phase11 support replacement;
- strategy-rule or outcome-definition changes in the initial route-fidelity experiment;
- fabrication of unavailable pre-origin intraday/ticker context;
- carrying later reference metadata backward and treating it as an authoritative PIT fact;
- granting support authority to a research-only historical universe proxy.

## Historical origin lock

Route-fidelity replay may begin no earlier than **2021-08-16**, the accepted ticker/intraday history origin.

Pre-2021 1h/4h or ticker-regime context may not be synthesized from daily history.

Market/sector regime policy legitimately uses daily history beginning 2016-01-04. Gate0 therefore inventories the cumulative daily-feature lineage needed by the accepted split-origin market-state engine separately from the 2021 ticker/intraday replay origin.

## Production path to reproduce

The target historical population is the deterministic production path, as far as accepted PIT evidence permits:

`PIT universe -> discovery foundation -> 1d/4h/1h discovery scoring -> discovery hysteresis -> WARM/HOT directional qualification -> market/ticker strategy route -> incumbent rule firing`

Sector remains `UNAVAILABLE`/nonblocking unless an authoritative PIT ticker-to-sector mapping is separately accepted. Phase25 may not invent one.

## Gate 0 — provider-free feasibility inventory

Gate0 performs **no historical strategy-return evaluation** and no replay mutation. It only determines whether the local accepted lake can support an exact replay.

For every XNYS session from 2021-08-16 through an explicit `--through` date it inventories canonical/derived bars, features/manifests, reference/universe artifacts, discovery artifacts, market/ticker regime artifacts, global identity inputs, and cumulative market daily-feature lineage.

### Accepted Gate0 target evidence — through 2026-08-21

Exact implementation head: `ce72ce8ee9b8828c07b9059bee0ff90948e8e48f`.

Cross-platform code gate: GitHub Actions run `32807555482`, Ubuntu and Windows both success, including the Phase25 Gate0 validator and full repository regression suite.

Target-machine report:

- replay origin: 2021-08-16;
- through session: 2026-08-21;
- replay sessions: 1,260;
- cumulative market daily lineage sessions from 2016-01-04: 2,674;
- canonical 1d: 1,260 / 1,260;
- derived 4h: 1,260 / 1,260;
- derived 1h: 1,260 / 1,260;
- features 1d / 4h / 1h: 1,260 / 1,260 each;
- feature-manifest triplets: 1,260 / 1,260;
- cumulative market daily feature lineage: 2,674 / 2,674;
- identity input files present: true;
- exact reference snapshot + manifest pairs: 7 / 1,260;
- exact universe snapshot + manifest pairs: 7 / 1,260;
- materialized discovery: 6 / 1,260;
- materialized market-regime pairs: 2 / 1,260;
- materialized ticker-regime pairs: 2 / 1,260;
- exact route-fidelity available/replayable sessions under conservative Gate0 rules: 7 / 1,260;
- 1,253 sessions have neither a materialized PIT universe nor an exact same-session PIT reference snapshot;
- protected strategy evidence reads: 0;
- provider reads/writes: 0 / 0;
- broker reads/writes: 0 / 0;
- order/PAPER/LIVE writes: 0 / 0 / 0;
- Phase11 support writes: 0;
- Gate0 pass: true.

Accepted interpretation: the market-data/feature/regime-history foundation is complete. The exact-replay blocker is PIT reference/universe lineage, not missing price or feature history.

## Gate 1 — provider-free PIT reference / identity scope proof

Gate1 remains **provider-free, return-free, and non-authoritative**. It binds to the passing Gate0 report and reads only local canonical daily bars, local reference snapshots, ticker observations, authoritative ticker intervals, and the instrument registry.

Future-only reference observations may be measured but never treated as PIT authority. A bounded invariant metadata proxy label has zero Phase7, Phase11, promotion, PAPER, or LIVE authority.

### Accepted Gate1 target evidence — through 2026-08-21

Initial target run on head `904a5b484dac02ee26338d62ef78f1c5c6e0b112` correctly blocked on a Gate0-report field-name mismatch. The repair changed only that binding plus a regression test/static guard.

Exact repaired Gate1 head: `9693b96f6bce5f038c5470189679580df0151a08`.

Cross-platform repair gate: GitHub Actions run `32808977264`, Ubuntu and Windows both success, including every validator through Phase25 Gate1 and the full repository regression suite.

Frozen accepted policy fingerprints:

- Gate0: `994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604`;
- Gate1: `1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207`.

Target-machine report:

- canonical distinct symbols: 20,722;
- canonical symbol-session rows: 13,918,673;
- local PIT reference snapshot dates: 7;
- exact first-seen reference symbols: 9,393;
- symbols without exact first-seen reference: 11,329;
- distinct first-seen gap dates: 1,232;
- prior-reference-only symbols: 389;
- future-only reference symbols: 8,449;
- no-local-reference symbols: 91;
- ambiguous local identity symbols: 2,400;
- authoritative ticker interval covers first-seen: 1,029;
- bounded invariant metadata proxy candidates: 9,398;
- largest first-seen gap: 2021-08-16 with 1,293 symbols;
- protected strategy evidence reads: 0;
- provider reads/writes: 0 / 0;
- broker reads/writes: 0 / 0;
- order/PAPER/LIVE writes: 0 / 0 / 0;
- Phase11 support writes: 0;
- Gate1 pass: true.

Accepted interpretation: the reference gap is broad rather than concentrated. A first-seen-only patch would still not prove session-by-session Phase7 eligibility because `active`, `delisted_utc`, exchange, security type, locale, market, and identity quality are PIT inputs. Future-only metadata remains non-authoritative.

## Gate 2 — provider-free active-only PIT discovery equivalence

Gate2 tests whether a full same-session PIT reference snapshot and its **active-only subset** produce exactly the same discovery population.

For every locally materialized reference date from the accepted Gate1 report, Gate2:

1. requires the existing reference manifest to be a full `include_inactive=true` snapshot;
2. binds the materialized universe manifest to that exact reference snapshot SHA and the locked universe-eligibility policy fingerprint;
3. computes the discovery population from the full reference rows using discovery-relevant `UniverseManager` semantics with no position/watchlist/custom overrides;
4. computes the same population again from only rows where `active=true`;
5. reads the accepted materialized Phase7 universe and selects `discovery_eligible=true` members;
6. compares exact provider-native identity/eligibility metadata across all three populations;
7. fails closed on any mismatch, identity-quality conflict, missing artifact, stale source binding, or non-full proof snapshot.

The compared member identity includes `instrument_id`, provider-native ticker case, identity quality, name, market, locale, primary exchange, security type, reference-active state, and delisted timestamp.

**Gate2 does not grant provider-read authority.** It does not fetch Massive data, evaluate strategy returns, read protected evidence, rebuild support, or alter universe/discovery production artifacts.

### Accepted Gate2 target evidence — through 2026-08-21

Exact implementation/spec head: `546fdc000db754c47fcbcf9cdccb3d6d94f1cace`.

Frozen accepted Gate2 policy fingerprint:

`417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083`

Exact-head GitHub Actions run `32809757087` passed on Ubuntu and Windows, including every validator through Phase25 Gate2 and the full repository regression suite.

Target-machine proof:

- PIT dates tested: 7;
- full reference rows: 246,631;
- active reference rows: 89,755;
- inactive rows removed: 156,876;
- observed active-only row reduction: **63.61%**;
- 2021-08-16 discovery members: full 9,403 / active-only 9,403 / materialized 9,403;
- 2026-08-14 discovery members: 12,066 / 12,066 / 12,066;
- 2026-08-17: 12,071 / 12,071 / 12,071;
- 2026-08-18: 12,078 / 12,078 / 12,078;
- 2026-08-19: 12,085 / 12,085 / 12,085;
- 2026-08-20: 12,088 / 12,088 / 12,088;
- 2026-08-21: 12,092 / 12,092 / 12,092;
- full-vs-active-only mismatch count: zero on every date;
- active-only-vs-materialized mismatch count: zero on every date;
- all dates equivalent: true;
- provider reads/writes: 0 / 0;
- broker reads/writes: 0 / 0;
- order/PAPER/LIVE writes: 0 / 0 / 0;
- Phase11 support writes: 0;
- Gate2 pass: true.

Accepted interpretation: inactive reference rows are unnecessary for **discovery-only** historical replay under the locked no-override Phase25 experiment. The reduced exact source shape is therefore eligible for a separately preregistered acquisition plan. Gate2 itself grants no read authority.

## Gate 3 — provider-free exact active-only PIT acquisition preregistration

Gate3 freezes the acquisition plan before any Massive historical read is possible.

Gate3 is **provider-free**. It may inspect local Gate2 evidence, exact XNYS sessions, and existing reference snapshot/manifest pairs, but it may not instantiate a provider client or perform any external call.

### Locked acquisition source shape

For each missing replay session, the only preregistered provider query is:

`GET /v3/reference/tickers`

with:

- `market=stocks`;
- `date=<EXACT_SESSION_DATE>`;
- `active=true`;
- `order=asc`;
- `sort=ticker`;
- `limit=1000`;
- pagination followed only through the same provider host until `next_url` is absent;
- provider-native ticker case preserved;
- newly acquired reference manifests use `include_inactive=false`.

Gate3 does not permit ticker-level ad hoc queries, later-date carryback, full active+inactive acquisition, arbitrary date ranges, current-state substitution, or source widening.

### Existing local evidence and resume policy

Gate3 enumerates every exact exchange session from 2021-08-16 through the explicit `--through` session.

For each session:

- a valid existing reference snapshot + matching valid manifest is preserved and requires no provider call;
- a session with neither artifact becomes an `ACQUIRE_ACTIVE_ONLY_EXACT_PIT` target;
- a session with only one side of the pair is a fail-closed partial state and blocks the plan until reconciled;
- existing valid full snapshots are not replaced merely to make storage uniform;
- force replacement is forbidden;
- a later acquisition runner may resume only from independently validated snapshot/manifest pairs.

### Preregistered Gate4 execution requirements

Gate3 does not grant provider-read authority. A later Gate4 must separately implement and validate all of the following before any historical call:

1. exact run-scoped interactive read confirmation;
2. an **earliest-missing-session entitlement probe first**;
3. immediate abort of the bulk acquisition if that probe is inaccessible or invalid;
4. exact-session active-only queries only;
5. atomic per-session persistence;
6. positive-row validation;
7. all newly acquired rows must be `active=true`;
8. exact session date and locked reference/identity contracts in each manifest;
9. no overwrite of accepted existing pairs;
10. resumability only from validated pairs;
11. no blind retry after an unreconciled partial local session;
12. no broker/order/PAPER/LIVE/support/protected-strategy authority.

The entitlement probe is necessary because provider credentials existing locally do not by themselves prove that the account's historical-reference entitlement reaches the earliest missing 2021 session.

### Request-volume sizing

Gate3 uses the seven accepted Gate2 active-row counts only as a non-authoritative sizing diagnostic. With provider page size locked at 1,000, those dates require approximately 10–13 pages per session. If the target plan contains 1,253 missing sessions, the expected order of magnitude is therefore approximately **12,530–16,289 provider page requests**.

This estimate does not widen authority, establish entitlement, or permit Gate3 to call the provider.

### Gate3 decision rule

If Gate2 remains passing, every replay session has either a valid existing pair or a cleanly missing pair, the exact missing-session list is frozen, and all Gate3 authority counters remain zero, Gate3 recommends:

`GATE4_IMPLEMENT_EXPLICIT_RUN_SCOPED_ACTIVE_ONLY_MASSIVE_READ_AUTHORITY`

If the plan encounters a partial/stale reference pair, it blocks rather than overwriting it.

**Gate3 does not grant provider-read authority.**

## Gate 0-3 acceptance criteria

- Gates0-3 are provider-free and broker-free;
- exact exchange-session enumeration where applicable;
- no date before 2021-08-16 enters ticker/intraday replay scope;
- market daily-history origin remains 2016-01-04;
- no strategy returns or protected evidence are read;
- no support/promotion artifact is modified;
- missing prerequisites are reported rather than fabricated;
- future-only metadata never becomes PIT authority;
- provider-native ticker case is preserved;
- accepted Gate0, Gate1, and Gate2 policy fingerprints remain unchanged by Gate3;
- Gate2 source equivalence is based on accepted materialized Phase7 universe evidence;
- Gate3 exact query shape, missing-session list, resume behavior, entitlement probe, and no-overwrite semantics are preregistered before provider authority;
- focused tests and static validators pass;
- Ubuntu and Windows CI pass;
- target-machine inventories/proofs/plans are used only after code-side validation because local analytical artifacts are not stored in GitHub.

## Later gates — provisional sequence

After Gate3 target evidence is accepted, Gate4 may implement the separate explicit Massive read-authority boundary for the frozen active-only acquisition plan. Gate4 may not change the session list, query shape, page limit, active filter, source semantics, or overwrite policy merely to make acquisition easier.

After successful acquisition, a separate validation/reconstruction gate must prove every exact PIT reference pair before rebuilding Phase7 universes and the downstream historical production path.

Only after the historical population itself is accepted may a later gate compare an attribution ladder while holding rules/outcomes fixed:

1. broad historical population;
2. PIT-universe eligible;
3. discovery-qualified;
4. WARM/HOT directional;
5. market-routed;
6. ticker-routed;
7. incumbent-rule fired.

Any future support-replacement decision requires a separately preregistered evidence gate after the route-fidelity population itself is independently accepted. Phase25 does not inherit permission to lower Phase24 thresholds or reopen protected evidence merely because the population changes.

## Non-goals

Phase25 is not a new-strategy-generation phase, model replacement phase, broker/execution phase, GUI phase, scheduler phase, PostgreSQL phase, or LIVE phase. Gates0-3 are not provider-acquisition phases.
