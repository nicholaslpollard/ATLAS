# Phase 25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence

**Status: ACTIVE / GATE 1 PIT REFERENCE SCOPE PROOF**

Upstream authority: Phase24 accepted merge `15b77321d4815f9f52fe74d47ba32fee8127526a`; synchronized `main` handoff `71063b510953aca87b253f5b3b0d42954a6abf0a`.

## Purpose

Phase24 established that simple daily rule tightening does not earn robust support under the stronger preregistered evidence framework. It also exposed a population-fidelity mismatch: historical Phase11/24 strategy studies evaluate broad daily rows with broad market-regime routing, while production strategy promotion is reached only after PIT universe routing, multi-timeframe discovery, discovery-state hysteresis, WARM/HOT directional qualification, and market/ticker route compatibility.

Phase25 asks a narrower question before inventing new strategies:

**Does strategy evidence materially change when the historical population is reconstructed to match the production candidate path?**

The initial experiment holds incumbent strategy rules and the three-session forward-return outcome fixed. The independent variable is the historical population/routing path.

## Authority boundary

Phase25 Gate0 and Gate1 are local analytical research only.

Allowed:

- read accepted local canonical/reference/universe/feature/discovery/regime/identity artifacts;
- inventory their PIT coverage and lineage;
- measure provider-native ticker first-seen/reference/identity coverage;
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

### Gate1 decision output

Gate1 does **not** choose a provider backfill automatically. It produces the evidence needed for the next decision:

1. if exact first-seen/reference coverage is unexpectedly complete, proceed to exact local reconstruction design;
2. if the gap is concentrated, preregister the smallest exact reference acquisition scope that could close it;
3. if exact daily reference reconstruction is impractical but local invariant evidence covers a large core, separately preregister a **non-authoritative screening proxy validation** against the seven exact reference/universe sessions;
4. if neither path is defensible, Phase25 closes as exact route-fidelity replay infeasible with current sources.

## Gate 0 and Gate 1 acceptance criteria

- provider-free and broker-free by construction;
- exact exchange-session enumeration;
- no date before 2021-08-16 enters ticker/intraday replay scope;
- market daily-history origin remains 2016-01-04;
- no strategy returns or protected evidence are read;
- no support/promotion artifact is modified;
- missing prerequisites are reported rather than fabricated;
- future-only metadata never becomes PIT authority;
- provider-native ticker case is preserved;
- focused tests and static validators pass;
- Ubuntu and Windows CI pass;
- target-machine inventories are used only after code-side validation because local analytical artifacts are not stored in GitHub.

## Later gates — provisional sequence

A later gate, only after Gate1 evidence is accepted, may authorize either:

- a tightly scoped PIT reference acquisition/reconstruction path; or
- a clearly non-authoritative proxy-validation experiment whose output cannot replace support.

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

Phase25 is not a new-strategy-generation phase, model replacement phase, broker/execution phase, GUI phase, scheduler phase, PostgreSQL phase, or LIVE phase. Gate0/Gate1 are also not provider-acquisition phases.
