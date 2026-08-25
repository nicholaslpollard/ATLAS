# Phase 25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence

**Status: ACTIVE / GATE 2 ACTIVE-ONLY PIT EQUIVALENCE**

Upstream authority: Phase24 accepted merge `15b77321d4815f9f52fe74d47ba32fee8127526a`; synchronized `main` handoff `71063b510953aca87b253f5b3b0d42954a6abf0a`.

## Purpose

Phase24 established that simple daily rule tightening does not earn robust support under the stronger preregistered evidence framework. It also exposed a population-fidelity mismatch: historical Phase11/24 strategy studies evaluate broad daily rows with broad market-regime routing, while production strategy promotion is reached only after PIT universe routing, multi-timeframe discovery, discovery-state hysteresis, WARM/HOT directional qualification, and market/ticker route compatibility.

Phase25 asks a narrower question before inventing new strategies:

**Does strategy evidence materially change when the historical population is reconstructed to match the production candidate path?**

The initial experiment holds incumbent strategy rules and the three-session forward-return outcome fixed. The independent variable is the historical population/routing path.

## Authority boundary

Phase25 Gates0-2 are local analytical research only.

Allowed:

- read accepted local canonical/reference/universe/feature/discovery/regime/identity artifacts;
- inventory their PIT coverage and lineage;
- measure provider-native ticker first-seen/reference/identity coverage;
- prove discovery-population equivalence between a full PIT reference snapshot and its active-only subset on already materialized local evidence;
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

For every XNYS session from 2021-08-16 through an explicit `--through` date it inventories:

- canonical 1d bar partition;
- derived 4h and 1h bar partitions;
- 1d/4h/1h feature partitions;
- 1d/4h/1h feature manifests;
- reference snapshot + manifest;
- universe snapshot + manifest;
- existing discovery foundation/score/state artifacts and manifests;
- existing market/sector regime state + manifest;
- existing ticker-regime state + manifest.

It also checks global identity inputs used by ticker-regime replay and the cumulative daily-feature-manifest lineage required by the split-origin market/sector engine.

Gate0 must distinguish:

- materialized replay input;
- universe input reconstructable locally from an exact PIT reference snapshot;
- missing prerequisite requiring later local reconstruction work;
- missing authoritative source that blocks exact replay.

It must not call Massive or any broker to fill a gap.

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

Accepted interpretation: the market-data/feature/regime-history foundation is complete. The exact-replay blocker is PIT reference/universe lineage, not missing price or feature history. Gate1 therefore narrows the problem before any provider authority is considered.

## Gate 1 — provider-free PIT reference / identity scope proof

Gate1 remains **provider-free, return-free, and non-authoritative**. It binds to the passing Gate0 report and reads only local canonical daily bars, local reference snapshots, ticker observations, authoritative ticker intervals, and the instrument registry.

It inventories the historical gap at provider-native ticker level:

- distinct canonical symbols and symbol-session count in replay scope;
- each symbol's first and last observed trading session;
- exact first-seen reference observations;
- prior-or-same reference observations;
- future-only local reference observations;
- symbols never observed in any local reference snapshot;
- distinct instrument identities associated with an exact provider ticker;
- authoritative ticker-validity-interval coverage at the symbol's first-seen session;
- local ticker-observation identity multiplicity;
- consistency of the static classification fields (`market`, `locale`, `primary_exchange`, `security_type`) across available local observations;
- number and concentration of first-seen dates that lack an exact reference anchor.

Future-only reference observations may be measured but never treated as PIT authority.

A symbol whose local observations bracket its first-seen date and agree on static metadata may be labeled a **bounded invariant metadata proxy candidate**. That label has zero Phase7, Phase11, promotion, PAPER, or LIVE authority. It is only evidence for deciding whether a later screening-only proxy experiment is worth preregistering.

Gate1 explicitly preserves:

- exact provider ticker case;
- ambiguity quarantine rather than identity guessing;
- no provider calls;
- no strategy return reads;
- no protected evidence reads;
- no support replacement;
- no backward-carry authority from a later reference snapshot;
- exact PIT reference as the requirement for any claim of authoritative Phase7 historical replay.

### Accepted Gate1 target evidence — through 2026-08-21

Initial target run on head `904a5b484dac02ee26338d62ef78f1c5c6e0b112` correctly blocked on a Gate0-report field-name mismatch. The accepted Gate0 report stores its policy hash in `policy_fingerprint`; Gate1 had looked for a nonexistent alias. The repair changed only that binding plus a regression test/static guard.

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

Accepted interpretation: the reference gap is broad rather than concentrated. A first-seen-only patch would still not prove session-by-session Phase7 eligibility because `active`, `delisted_utc`, exchange, security type, locale, market, and identity quality are PIT inputs. Future-only metadata remains non-authoritative. Phase25 therefore does not carry 2026 metadata backward and does not treat the 9,398 proxy candidates as support evidence.

## Gate 2 — provider-free active-only PIT discovery equivalence

Gate2 tests a narrower optimization before any historical reference acquisition is authorized.

The locked Phase7 discovery policy always excludes `reference_active=False` instruments. In the no-override Phase25 historical research path, `UniverseManager` routes discovery from active rows; inactive-only instruments become exclusions and multiple active rows remain ambiguous/fail closed.

Gate2 therefore tests whether a full same-session PIT reference snapshot and its **active-only subset** produce exactly the same discovery population.

For every locally materialized reference date from the accepted Gate1 report, Gate2 must:

1. require the existing reference manifest to be a full `include_inactive=true` snapshot;
2. bind the materialized universe manifest to that exact reference snapshot SHA and the locked universe-eligibility policy fingerprint;
3. compute the discovery population from the full reference rows using the discovery-relevant `UniverseManager` semantics with no position/watchlist/custom overrides;
4. compute the same population again from only rows where `active=true`;
5. read the accepted materialized Phase7 universe and select `discovery_eligible=true` members;
6. compare exact provider-native identity/eligibility metadata across all three populations;
7. fail closed on any mismatch, identity-quality conflict, missing artifact, stale source binding, or non-full proof snapshot.

The compared member identity includes:

- `instrument_id`;
- provider-native `ticker` case;
- identity quality;
- name;
- market;
- locale;
- primary exchange;
- security type;
- reference-active state;
- delisted timestamp.

Gate2 also reports the observed row reduction from removing inactive reference rows. This is a sizing diagnostic only.

**Gate2 does not grant provider-read authority.** It does not fetch Massive data, evaluate strategy returns, read protected evidence, rebuild support, or alter universe/discovery production artifacts.

### Gate2 decision rule

If every tested date has zero mismatch for:

- full reference vs active-only reference; and
- active-only reference vs accepted materialized Phase7 discovery,

then Gate2 may recommend:

`GATE3_PREREGISTER_ACTIVE_ONLY_EXACT_PIT_ACQUISITION`

That recommendation means only that a later separately reviewed provider-read gate may acquire exact same-session Massive `active=true` PIT snapshots for historical discovery replay. It does not itself authorize the reads.

If any tested date differs, Gate2 must recommend:

`GATE3_ACTIVE_ONLY_EQUIVALENCE_NOT_PROVEN`

and Phase25 may not use the reduced source shape as an authoritative replay source.

## Gate 0-2 acceptance criteria

- provider-free and broker-free by construction;
- exact exchange-session enumeration where applicable;
- no date before 2021-08-16 enters ticker/intraday replay scope;
- market daily-history origin remains 2016-01-04;
- no strategy returns or protected evidence are read;
- no support/promotion artifact is modified;
- missing prerequisites are reported rather than fabricated;
- future-only metadata never becomes PIT authority;
- provider-native ticker case is preserved;
- Gate0 and Gate1 accepted policy fingerprints remain unchanged by later Phase25 additions;
- Gate2 source equivalence requires accepted materialized Phase7 universe evidence, not only a theoretical code argument;
- focused tests and static validators pass;
- Ubuntu and Windows CI pass;
- target-machine inventories/proofs are used only after code-side validation because local analytical artifacts are not stored in GitHub.

## Later gates — provisional sequence

If Gate2 proves active-only discovery equivalence, Gate3 may preregister a **resumable exact PIT reference acquisition** using Massive same-session `active=true` reference data for only the missing replay sessions. Provider-read authority, retry semantics, checkpoints, rate-limit behavior, and post-acquisition validation must be locked separately before execution.

If Gate2 does not prove equivalence, Gate3 must either use the full active+inactive source shape or close the exact replay path as impractical; it may not silently downgrade to future metadata.

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

Phase25 is not a new-strategy-generation phase, model replacement phase, broker/execution phase, GUI phase, scheduler phase, PostgreSQL phase, or LIVE phase. Gates0-2 are also not provider-acquisition phases.
