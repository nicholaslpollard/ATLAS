# Phase 25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence

**Status: ACTIVE / GATES 0-4 ACCEPTED / GATE 5 RESUMABLE BULK ACQUISITION IMPLEMENTATION**

Upstream authority: Phase24 accepted merge `15b77321d4815f9f52fe74d47ba32fee8127526a`; synchronized `main` handoff `71063b510953aca87b253f5b3b0d42954a6abf0a`.

## Purpose

Phase24 established that tightening the existing simple daily strategy rules did not earn robust replacement support. It also exposed a population-fidelity mismatch: historical Phase11/24 strategy studies evaluate broad daily rows with broad market-regime routing, while production promotion is reached only after PIT universe routing, multi-timeframe discovery, discovery-state hysteresis, WARM/HOT direction, and market/ticker route compatibility.

Phase25 asks:

**Does strategy evidence materially change when the historical population is reconstructed to match the production candidate path?**

The initial experiment holds incumbent strategy rules and the three-session forward-return outcome fixed. The independent variable is the historical population/routing path.

## Historical origin and authority lock

- route-fidelity replay begins no earlier than **2021-08-16**;
- pre-2021 1h/4h or ticker-regime context may not be synthesized;
- market/sector daily regime history may legitimately begin at **2016-01-04**;
- sector remains `UNAVAILABLE`/nonblocking unless authoritative PIT sector mapping is separately accepted;
- future metadata cannot be carried backward as authoritative PIT fact;
- provider-native ticker case is preserved;
- missing, partial, stale, or ambiguous state fails closed.

Target production path:

`PIT universe -> discovery foundation -> 1d/4h/1h discovery scoring -> discovery hysteresis -> WARM/HOT directional qualification -> market/ticker strategy route -> incumbent rule firing`

Gates0-3 permit no provider reads or writes. They also permit no broker reads/writes, order writes, PAPER submits, LIVE writes, Phase11 support changes, protected-strategy evidence reads, strategy-rule changes, or outcome-definition changes.

Gate4 was the first Phase25 provider-read boundary, limited to one exact entitlement-probe session. Gate5 may read only the remaining frozen active-only PIT reference sessions. Provider writes, broker/order mutations, PAPER/LIVE execution, support changes, and protected strategy evidence remain separately forbidden.

---

## Gate 0 — provider-free feasibility inventory — ACCEPTED

Exact implementation head: `ce72ce8ee9b8828c07b9059bee0ff90948e8e48f`.

Cross-platform code gate: GitHub Actions run `32807555482`, Ubuntu and Windows both success, including Gate0 validation and the full repository regression suite.

Accepted target evidence through 2026-08-21:

- replay sessions: **1,260**;
- cumulative market daily lineage sessions from 2016-01-04: **2,674**;
- canonical 1d: 1,260 / 1,260;
- derived 4h: 1,260 / 1,260;
- derived 1h: 1,260 / 1,260;
- features 1d/4h/1h: 1,260 / 1,260 each;
- feature-manifest triplets: 1,260 / 1,260;
- cumulative market daily feature lineage: 2,674 / 2,674;
- identity inputs complete: true;
- exact PIT reference pairs: **7 / 1,260**;
- exact PIT universe pairs: **7 / 1,260**;
- exact route-fidelity locally available/replayable: **7 / 1,260**;
- sessions blocked by missing exact PIT reference/universe evidence: **1,253**;
- provider/broker/order/PAPER/LIVE/support/protected-evidence activity: all zero;
- Pass: true.

Accepted interpretation: market-data, feature, and regime-history lineage are complete. PIT reference/universe lineage is the exact-replay blocker.

---

## Gate 1 — provider-free PIT reference / identity scope proof — ACCEPTED

Initial target head `904a5b484dac02ee26338d62ef78f1c5c6e0b112` exposed a Gate0 report-field binding bug. The repair changed only the binding plus regression/static guards.

Exact repaired head: `9693b96f6bce5f038c5470189679580df0151a08`.

Cross-platform repair gate: GitHub Actions run `32808977264`, Ubuntu and Windows both success through Gate1 plus the full regression suite.

Frozen policy fingerprints:

- Gate0: `994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604`;
- Gate1: `1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207`.

Accepted target evidence:

- canonical distinct symbols: **20,722**;
- canonical symbol-session rows: **13,918,673**;
- local PIT reference dates: 7;
- exact first-seen reference symbols: 9,393;
- symbols without exact first-seen reference: **11,329**;
- distinct first-seen gap dates: **1,232**;
- prior-reference-only symbols: 389;
- future-only reference symbols: **8,449**;
- no-local-reference symbols: 91;
- ambiguous local identity symbols: **2,400**;
- authoritative ticker interval covers first-seen: 1,029;
- bounded invariant metadata proxy candidates: 9,398;
- provider/broker/order/PAPER/LIVE/support/protected-evidence activity: all zero;
- Pass: true.

Future-only reference observations may be measured but never treated as PIT authority. Bounded invariant proxy candidates also have zero Phase7, support, promotion, PAPER, or LIVE authority.

Accepted interpretation: the reference gap is broad. First-seen-only patching and backward-carry of later metadata are not authoritative enough for session-by-session Phase7 replay.

---

## Gate 2 — provider-free active-only PIT discovery equivalence — ACCEPTED

Gate2 tested whether full same-session reference data and only the `active=true` subset produce the same Phase7 discovery population under the locked no-override research path.

Exact implementation/spec head: `546fdc000db754c47fcbcf9cdccb3d6d94f1cace`.

Frozen Gate2 policy fingerprint:

`417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083`

Exact-head GitHub Actions run `32809757087`: Ubuntu and Windows success through Gate2 plus full regression.

Accepted target proof across all seven locally materialized PIT dates:

- full reference rows: **246,631**;
- active reference rows: **89,755**;
- inactive rows removable: **156,876**;
- observed row reduction using active-only data: **63.61%**;
- full vs active-only discovery mismatch: zero on every date;
- active-only vs accepted materialized Phase7 mismatch: zero on every date;
- 2021-08-16 discovery members: 9,403 / 9,403 / 9,403;
- 2026-08-14: 12,066 / 12,066 / 12,066;
- 2026-08-17: 12,071 / 12,071 / 12,071;
- 2026-08-18: 12,078 / 12,078 / 12,078;
- 2026-08-19: 12,085 / 12,085 / 12,085;
- 2026-08-20: 12,088 / 12,088 / 12,088;
- 2026-08-21: 12,092 / 12,092 / 12,092;
- all dates equivalent: true;
- provider/broker/order/PAPER/LIVE/support/protected-evidence activity: all zero;
- Pass: true.

Gate2 does not grant provider-read authority. It only proves that exact active-only PIT reference data are sufficient for **discovery-only** historical replay under the locked experiment.

---

## Gate 3 — provider-free exact active-only PIT acquisition preregistration — ACCEPTED

Gate3 froze the exact missing-session plan and query shape before any historical reference call was allowed.

Exact implementation/spec head: `1fb2494e20cc2afea35de3c109055d56fa72abdf`.

Frozen Gate3 policy fingerprint:

`d0e49829132c0c8f2a09c078863ea4871fe36da1067b04c3f367e880a24080b6`

Exact-head GitHub Actions run `32850178349`: Ubuntu and Windows success through Gate3 plus full regression.

Accepted target-machine plan through 2026-08-21:

- replay sessions: **1,260**;
- existing valid PIT reference sessions: **7**;
- existing full active+inactive sessions: 7;
- existing active-only sessions: 0;
- exact active-only acquisition sessions: **1,253**;
- earliest entitlement probe session: **2021-08-17**;
- observed pages/session at `limit=1000`: **12–14**;
- projected logical provider page reads: **15,036–17,542**;
- locked query: `GET /v3/reference/tickers market=stocks active=true order=asc sort=ticker limit=1000 date=EXACT_SESSION_DATE`;
- active-only acquisition authority: false;
- provider/broker/order/PAPER/LIVE/support/protected-evidence activity: all zero;
- Pass: true.

Gate3 does not grant provider-read authority. It freezes the exact acquisition source, exact XNYS session list, no-overwrite behavior, resumability requirements, and earliest-session entitlement probe requirement.

Accepted interpretation: the acquisition scope is large but finite and exactly defined. Existing valid pairs are preserved; no full active+inactive replacement, future-metadata substitution, or arbitrary source widening is allowed.

---

## Gate 4 — explicit earliest-session Massive entitlement probe — ACCEPTED

Exact accepted target/code head: `f4e90bc41222e8db25146e0214bf4bd437b3b103`.

Frozen Gate4 policy fingerprint:

`e8ef1b2f0d020e579e4c8fc92dfa256fea307ce96ed89cee02c4a812b8398d16`

Exact-head GitHub Actions run `32852041021`: Ubuntu and Windows success through Gate4 plus full regression.

Accepted provider-free prepare evidence:

- frozen acquisition sessions: **1,253**;
- earliest entitlement probe: **2021-08-17**;
- bulk acquisition disabled;
- disposition: `PREPARED_ZERO_EXTERNAL_CALLS`.

Accepted target-machine entitlement probe evidence:

- probe session: **2021-08-17**;
- provider probe sessions: **1**;
- **12 provider page reads**;
- persisted rows: **11,027**;
- persisted instruments: **11,027**;
- bulk acquisition sessions: 0;
- remaining frozen acquisition sessions: **1,252**;
- provider writes: 0;
- broker reads/writes: 0 / 0;
- order/PAPER/LIVE writes: 0 / 0 / 0;
- Phase11 support writes: 0;
- independent validation: pass;
- Pass: true.

Accepted interpretation: the account has entitlement to the exact historical active-only PIT reference source at the earliest required post-origin session, same-host pagination and bounded retry behavior work, and the accepted snapshot/identity persistence path produces valid active-only canonical evidence.

Gate4 may not be silently rerun or used as a bulk path. The accepted 2021-08-17 snapshot/manifest pair is immutable input to Gate5.

---

## Gate 5 — resumable frozen active-only PIT bulk acquisition — ACTIVE

Gate5 acquires only the **1,252 remaining frozen sessions** from the accepted Gate3 plan. It does not expand the source, dates, market, activity filter, page limit, or provider.

### Read-only authorization UX

For Gate5, the explicit CLI subcommand is itself the provider-read authorization:

`EXPLICIT_CLI_SUBCOMMAND`

The operator runs `acquire --through 2026-08-21`; **no pasted confirmation** or second interactive prompt is required for this read-only acquisition. Provider reads remain default-deny unless the explicit `acquire` code path is invoked and its exact Gate3/Gate4 lineage validates.

This convenience applies to the Gate5 read-only path only. It does not remove stronger confirmation requirements for provider mutations, broker/order mutations, PAPER/LIVE execution, destructive cleanup, or other irreversible authority boundaries.

### Frozen acquisition behavior

Gate5 must:

1. bind the exact accepted Gate3 plan SHA and Gate4 report/independent-validation SHAs;
2. verify the accepted 2021-08-17 probe pair has not changed;
3. exclude the probe via the exact frozen `acquisition_sessions[1:]` scope;
4. preserve all provider-native ticker case;
5. request `GET /v3/reference/tickers` with `market=stocks`, `active=true`, exact session `date`, ascending ticker sort, and `limit=1000`;
6. follow only same-host pagination through the accepted Massive REST client;
7. reuse bounded provider retries including 429 handling;
8. validate positive rows, nonblank tickers, and `active=true` before local persistence;
9. persist each completed session using the accepted reference/identity contracts with `include_inactive=false`;
10. never force-replace a valid pair;
11. skip only complete, independently valid active-only pairs on resume;
12. fail closed on unowned or unreconciled partial state;
13. use a Gate5 inflight marker to safely reconcile an owned snapshot-only interruption without re-reading the provider;
14. update local progress after every completed session;
15. defer the expensive instrument-registry rebuild until the frozen bulk scope is fully complete;
16. produce a final Gate5 report only when all **1,252 / 1,252** bulk sessions validate;
17. run a separate provider-free independent validator across every frozen acquisition session before Gate6 may proceed.

### Gate5 performance lock

Gate5 deliberately does **not** call `InstrumentRegistryStore.sync_snapshot()` for every historical day because that method rebuilds the full derived registry after each snapshot. Gate5 reuses the accepted observation/snapshot format and atomic local write primitives, then runs one registry rebuild after all frozen sessions are complete. This is a performance optimization only; it does not change reference or identity semantics.

### Gate5 resumability

A failed network request before local persistence leaves the session missing and the same `acquire` command may resume later. A completed validated pair is never re-fetched. If an interruption occurs after a Gate5-owned snapshot is atomically promoted but before its manifest is written, the inflight marker permits provider-free validation and manifest reconstruction. Any state that cannot be proven as Gate5-owned and valid fails closed rather than being guessed or overwritten.

### Gate5 hard prohibitions

Gate5 may not:

- re-fetch 2021-08-17;
- fetch any date outside the frozen Gate3 acquisition list;
- use inactive reference rows;
- widen to another reference endpoint or provider;
- use `force=true`;
- read strategy returns or protected strategy evidence;
- change strategy rules, outcomes, Phase11 support, Phase24 thresholds, or promotion rules;
- read or mutate brokers;
- submit orders or PAPER trades;
- write LIVE state;
- invoke browser execution, scheduler authority, or PostgreSQL runtime promotion.

### Gate5 acceptance rule

Gate5 is accepted only if:

- every frozen acquisition session now has an exact reference snapshot/manifest pair;
- all Gate3 acquisition sessions are active-only and contain zero blank tickers;
- all manifest row/instrument counts match canonical data;
- the accepted Gate4 probe pair remains unchanged and was not re-fetched;
- the frozen bulk count is exactly 1,252 and remaining bulk count is zero;
- provider writes remain zero;
- broker/order/PAPER/LIVE/support/protected-evidence authority remains zero;
- the deferred registry rebuild completes;
- independent validation passes.

Only after Gate5 target evidence is accepted may Gate6 rebuild and independently validate the missing Phase7 PIT universe lineage.

---

## Phase25 acceptance invariants

- accepted Gate0-Gate4 policy fingerprints are immutable;
- Gate5 policy is isolated so it cannot retroactively change prior evidence;
- exact exchange-session scope is required;
- provider-native ticker case is preserved;
- missing, partial, stale, or ambiguous state fails closed;
- no synthetic pre-origin intraday/ticker context;
- no support threshold weakening;
- zero candidate/promoted output remains valid if evidence does not support promotion;
- provider authority, support authority, execution authority, and LIVE authority remain separate gates.

## Later sequence

After Gate5 bulk reference evidence passes, Gate6 must independently validate complete PIT reference lineage and rebuild Phase7 universe snapshots/manifests for missing sessions without provider access. Later gates then reconstruct discovery, regimes, routing, and the historical production population.

Only after that population is accepted may strategy evidence be compared along the attribution ladder while holding rules/outcomes fixed:

1. broad historical population;
2. PIT-universe eligible;
3. discovery-qualified;
4. WARM/HOT directional;
5. market-routed;
6. ticker-routed;
7. incumbent-rule fired.

Any future support replacement requires its own separately preregistered statistical evidence gate. Phase25 does not inherit permission to lower Phase24 thresholds or reopen protected evidence merely because the population changes.

## Non-goals

Phase25 is not a new-strategy-generation phase, ML replacement phase, execution phase, GUI phase, scheduler phase, PostgreSQL promotion phase, or LIVE phase.
