# Phase 25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence

**Status: ACTIVE / GATES 0-3 ACCEPTED / GATE 4 ENTITLEMENT PROBE IMPLEMENTATION**

Upstream authority: Phase24 accepted merge `15b77321d4815f9f52fe74d47ba32fee8127526a`; synchronized `main` handoff `71063b510953aca87b253f5b3b0d42954a6abf0a`.

## Purpose

Phase24 established that tightening the existing simple daily strategy rules did not earn robust replacement support. It also exposed a population-fidelity mismatch: historical Phase11/24 strategy studies evaluate broad daily rows with broad market-regime routing, while production promotion is reached only after PIT universe routing, multi-timeframe discovery, discovery-state hysteresis, WARM/HOT direction, and market/ticker route compatibility.

Phase25 therefore asks a narrower question before inventing new strategy families:

**Does strategy evidence materially change when the historical population is reconstructed to match the production candidate path?**

The initial experiment holds incumbent strategy rules and the three-session forward-return outcome fixed. The independent variable is the historical population/routing path.

## Historical origin lock

- route-fidelity replay begins no earlier than **2021-08-16**;
- pre-2021 1h/4h or ticker-regime context may not be synthesized;
- market/sector daily regime history may legitimately begin at **2016-01-04**;
- sector remains `UNAVAILABLE`/nonblocking unless authoritative PIT sector mapping is separately accepted.

Target production path:

`PIT universe -> discovery foundation -> 1d/4h/1h discovery scoring -> discovery hysteresis -> WARM/HOT directional qualification -> market/ticker strategy route -> incumbent rule firing`

## Authority boundary

Gates0-3 are provider-free local research/planning gates.

Gate4 is the first Phase25 provider-read gate, but its authority is intentionally narrow:

- exact interactive run-scoped authorization is required;
- only the frozen **earliest missing session** may be queried;
- only exact same-session Massive `/v3/reference/tickers` data with `market=stocks`, `active=true`, `order=asc`, `sort=ticker`, `limit=1000` may be read;
- only one entitlement-probe session may be persisted;
- bulk acquisition remains forbidden;
- provider writes remain forbidden;
- broker reads/writes, order writes, PAPER submits, LIVE, Phase11 support writes, protected strategy evidence, strategy-rule changes, and outcome changes remain forbidden.

Provider-native ticker case must be preserved. Later metadata may never be carried backward as PIT authority. Missing or ambiguous state fails closed rather than being guessed.

---

## Gate 0 — provider-free feasibility inventory — ACCEPTED

Exact implementation head: `ce72ce8ee9b8828c07b9059bee0ff90948e8e48f`.

Cross-platform code gate: GitHub Actions run `32807555482`, Ubuntu and Windows both success, including Gate0 validation and the full repository regression suite.

Accepted target evidence through 2026-08-21:

- replay sessions: **1,260**;
- cumulative market daily lineage sessions from 2016-01-04: **2,674**;
- canonical 1d: 1,260/1,260;
- derived 4h: 1,260/1,260;
- derived 1h: 1,260/1,260;
- features 1d/4h/1h: 1,260/1,260 each;
- feature-manifest triplets: 1,260/1,260;
- cumulative market daily feature lineage: 2,674/2,674;
- identity inputs complete: true;
- exact PIT reference pairs: **7/1,260**;
- exact PIT universe pairs: **7/1,260**;
- exact route-fidelity locally available/replayable: **7/1,260**;
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

Accepted interpretation: the reference gap is broad. First-seen-only patching and backward-carry of later metadata are not authoritative enough for session-by-session Phase7 replay. Proxy candidates remain non-authoritative.

---

## Gate 2 — provider-free active-only PIT discovery equivalence — ACCEPTED

Gate2 tested whether full same-session reference data and only the `active=true` subset produce the same Phase7 discovery population under the locked no-override research path.

Exact implementation/spec head: `546fdc000db754c47fcbcf9cdccb3d6d94f1cace`.

Frozen Gate2 policy fingerprint:

`417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083`

Exact-head GitHub Actions run `32809757087`: Ubuntu and Windows success through Gate2 plus full regression.

Accepted target proof across all seven locally materialized PIT dates:

- full reference rows: **246,631**;
- active rows: **89,755**;
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

Accepted interpretation: inactive reference rows are unnecessary for **discovery-only** historical replay under the locked experiment. Exact active-only PIT reference data may therefore be used by a separately authorized acquisition path.

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

Accepted interpretation: the acquisition scope is large but finite and exactly defined. Existing seven valid pairs are preserved. The remaining 1,253 sessions are frozen; no full active+inactive replacement or arbitrary source widening is allowed.

Gate3 specifically requires the earliest missing session to prove historical-reference entitlement before any bulk acquisition.

---

## Gate 4 — explicit earliest-session Massive entitlement probe — ACTIVE

Gate4 implements only the first provider-read boundary needed by the accepted Gate3 plan.

### Prepare

`prepare --through 2026-08-21` is provider-free. It must:

1. load and hash the exact accepted Gate3 plan;
2. confirm the Gate3 policy fingerprint and recommendation;
3. confirm the frozen first acquisition session is 2021-08-17;
4. confirm the target has neither snapshot nor manifest locally;
5. reject any partial or unexpectedly materialized target rather than overwrite it;
6. bind the exact query, through date, Gate3 SHA/source fingerprint, and external-read class into a run scope;
7. print the exact interactive confirmation string;
8. make zero external calls.

### Probe

The `probe` command may proceed only after the operator types the exact run-scoped confirmation.

It may then:

1. instantiate the accepted Massive REST/reference provider;
2. request **only 2021-08-17** using the Gate3 active-only query;
3. follow only same-host pagination using the accepted Massive REST client;
4. use the accepted bounded provider retry behavior;
5. require positive returned rows, nonblank provider-native tickers, and `active=true` on every returned row;
6. recheck that no concurrent local snapshot/manifest appeared before persistence;
7. persist exactly one active-only reference snapshot using the accepted instrument-registry store with `force=false`;
8. validate exact session date, reference contract, identity contract, positive counts, and all-active rows;
9. write a Gate4 research report;
10. run a separate provider-free independent validator over the persisted pair and exact Gate3 lineage.

### Gate4 hard prohibitions

Gate4 may not:

- query a second historical session;
- loop over the remaining acquisition list;
- perform bulk acquisition;
- change the frozen query shape;
- use ticker-specific ad hoc queries;
- overwrite an existing or partial reference pair;
- carry later metadata backward;
- read strategy returns or protected strategy evidence;
- alter Phase11 support;
- read/write a broker;
- submit/cancel/replace/close orders;
- submit PAPER orders;
- write LIVE state;
- invoke browser execution, scheduler authority, or PostgreSQL runtime promotion.

### Gate4 decision rule

A passing Gate4 target probe must prove:

- exact interactive authorization;
- exactly one provider probe session;
- positive logical provider page reads;
- positive persisted rows/instruments;
- zero inactive persisted rows;
- exact 2021-08-17 snapshot date;
- exact active-only manifest;
- exact snapshot/manifest SHA binding;
- independent validation pass;
- zero bulk acquisition sessions;
- zero provider writes;
- zero broker/order/PAPER/LIVE/support/protected-evidence authority.

Only after that target evidence is accepted may a later Gate5 implement a resumable bulk acquisition for the **remaining frozen sessions**. Gate5 must not silently rerun the entitlement probe or re-fetch already validated pairs.

---

## Phase25 acceptance invariants

- accepted Gate0-Gate3 policy fingerprints are immutable;
- Gate4 may add a new policy fingerprint but may not retroactively change prior evidence;
- exact exchange-session scope is required;
- provider-native ticker case is preserved;
- missing, partial, stale, or ambiguous state fails closed;
- no synthetic pre-origin intraday/ticker context;
- no support threshold weakening;
- zero candidate/promoted output remains valid if evidence does not support promotion;
- provider authority, support authority, execution authority, and LIVE authority remain separate gates.

## Later sequence

If Gate4 entitlement evidence passes, Gate5 may implement resumable acquisition of the remaining frozen active-only PIT sessions. A later independent validation/reconstruction gate must then prove every exact reference pair before rebuilding Phase7 universes, discovery, regimes, routing, and the historical production population.

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
