# Phase 25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence

**Status: ACTIVE / GATE 0 FEASIBILITY INVENTORY**

Upstream authority: Phase24 accepted merge `15b77321d4815f9f52fe74d47ba32fee8127526a`; synchronized `main` handoff `71063b510953aca87b253f5b3b0d42954a6abf0a`.

## Purpose

Phase24 established that simple daily rule tightening does not earn robust support under the stronger preregistered evidence framework. It also exposed a population-fidelity mismatch: historical Phase11/24 strategy studies evaluate broad daily rows with broad market-regime routing, while production strategy promotion is reached only after PIT universe routing, multi-timeframe discovery, discovery-state hysteresis, WARM/HOT directional qualification, and market/ticker route compatibility.

Phase25 asks a narrower question before inventing new strategies:

**Does strategy evidence materially change when the historical population is reconstructed to match the production candidate path?**

The initial experiment holds incumbent strategy rules and the three-session forward-return outcome fixed. The independent variable is the historical population/routing path.

## Authority boundary

Phase25 Gate0 and route-fidelity replay are local analytical research only.

Allowed:

- read accepted local canonical/reference/universe/feature/discovery/regime/identity artifacts;
- inventory their PIT coverage and lineage;
- replay deterministic local universe/discovery/regime/routing semantics when a later gate explicitly permits it;
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
- fabrication of unavailable pre-origin intraday/ticker context.

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

## Gate 0 outputs

The report must include:

- exact session count and origin/through dates;
- artifact coverage counts by class;
- bounded previews of missing sessions;
- reference-backed universe reconstruction count;
- sessions with complete local production-path base inputs;
- contiguous complete/reconstructable replay ranges if any;
- cumulative market daily-manifest coverage;
- cumulative ticker 1d/4h/1h feature-manifest coverage;
- global identity-file availability;
- explicit blockers and recommended next action;
- zero provider/broker/order/PAPER/LIVE/support authority counters;
- deterministic policy/report fingerprint.

## Gate 0 acceptance criteria

- provider-free and broker-free by construction;
- exact exchange-session enumeration;
- no date before 2021-08-16 enters ticker/intraday replay scope;
- market daily-history origin remains 2016-01-04;
- no strategy returns or protected evidence are read;
- no support/promotion artifact is modified;
- missing prerequisites are reported rather than fabricated;
- focused tests and a static validator pass;
- Ubuntu and Windows CI pass;
- one target-machine inventory run is used only after code-side validation because local analytical artifacts are not stored in GitHub.

## Later gates — provisional sequence

Gate1, only after Gate0 evidence is accepted, may implement a deterministic historical replay dataset over a proven feasible interval. It should replay discovery state sequentially, preserve exact identity and missing-sector semantics, and independently validate lineage/population counts.

Gate2 may then compare an attribution ladder while holding rules/outcomes fixed:

1. broad historical population;
2. PIT-universe eligible;
3. discovery-qualified;
4. WARM/HOT directional;
5. market-routed;
6. ticker-routed;
7. incumbent-rule fired.

Any future support-replacement decision requires a separately preregistered evidence gate after the route-fidelity population itself is independently accepted. Phase25 does not inherit permission to lower Phase24 thresholds or reopen protected evidence merely because the population changes.

## Non-goals

Phase25 is not a new-strategy-generation phase, model replacement phase, provider acquisition phase, broker/execution phase, GUI phase, scheduler phase, PostgreSQL phase, or LIVE phase.
