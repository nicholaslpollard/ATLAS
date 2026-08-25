# Phase 23 — Operational Current Analysis Cycle

**Status: ACTIVE / DEFINITION LOCKED**

Upstream baseline: `dd0d6838d76a15edde0783f471ad7e212453cd94` (post-Phase22 synchronized `main`).

Phase23 closes the smallest operational gap exposed after accepted Phase22: ATLAS has accepted production primitives for market-data acquisition, canonicalization, features, universe, discovery, regimes, ML probabilities, deterministic strategy routing, promoted research, Phase13 planning/risk, Phase14 AI audit, and Phase22 PAPER execution, but there is no one routine operator path that advances a **new finalized market session** through the analytical chain.

Phase23 creates that analytical-cycle binding. It stops before PAPER order execution. Phase22 remains the only routine PAPER operator entrypoint.

## 1. Purpose

Provide one deterministic, auditable operator workflow for an explicit finalized `as_of` session:

`provider-backed finalized data/reference refresh -> canonical lake -> 1d/4h/1h features -> point-in-time universe -> discovery foundation/scoring/state -> market/sector + ticker regimes -> accepted ML probabilities + frozen strategy-support current evaluation -> promoted-only deep research -> context/news/options/geometry/portfolio risk -> independent AI audit/alert artifacts -> Phase22-ready accepted input`

The cycle must preserve legitimate zero-candidate and zero-execution-case outcomes. It must never weaken strategy support, discovery thresholds, risk rules, or AI boundaries merely to create a trade.

## 2. Why this phase is required

Repository audit after Phase22 found:

- finalized Massive acquisition/materialization exists through `HistoricalBuildService` / `build_historical_lake.py`;
- point-in-time reference sync exists through `InstrumentRegistryStore` / `sync_instrument_reference.py`;
- feature materialization exists through `HistoricalFeatureMaterializer` / `materialize_features.py`;
- universe, discovery, market/sector regime, and ticker-regime builders already exist;
- Phase11–14 each have acceptance/closeout commands, but not a routine current-cycle coordinator;
- Phase20 orchestration is intentionally provider-free and **must not** be expanded to provider work;
- Phase22 faithfully consumes accepted Phase15 input but cannot create missing upstream analytical cases;
- the current Phase11 closeout recomputes the expensive historical support study each run even though support decisions are accepted/frozen; routine operation should verify and reuse that accepted support rather than restudy history every cycle;
- Phase13 uses a broker-neutral portfolio snapshot for admissibility. Routine execution-ready planning therefore needs an explicit read-only portfolio-evidence binding rather than guessing account state.

## 3. Locked authority boundary

### Allowed external activity

Only when explicitly authorized for the exact Phase23 run scope:

1. **Massive market/reference reads** required to obtain finalized daily/minute aggregate files and the point-in-time reference snapshot for the requested session.
2. **Massive research reads** for Phase13 news and options context, and only for accepted promoted Phase12 cases.
3. **Selected PAPER broker read-only reconciliation** needed to construct a broker-neutral Phase13 portfolio snapshot. Webull is default/primary; Alpaca is explicit manual selection only. No automatic fallback.
4. **Accepted Phase14 AI review calls** only for deterministic Phase13 cases already marked `phase14_review_ready=true`.

These permissions do not imply provider mutation authority, PAPER order-submit authority, scheduler authority, browser authority, or LIVE authority.

### Forbidden

- broker order submit/replace/cancel/close/flatten;
- Phase21 PAPER-submit authority acquisition;
- direct invocation of Phase22 `execute`;
- LIVE execution;
- automatic cross-broker failover;
- browser execution authority;
- autonomous scheduler/daemon execution;
- PostgreSQL runtime promotion;
- arbitrary ticker/quantity/price/geometry injection;
- strategy-support reclassification from new historical research;
- model retraining or accepted production-model replacement;
- weakening discovery/promotion/risk thresholds to manufacture candidates;
- registering provider-read or broker-read stages inside the accepted Phase20 provider-free registry.

## 4. Operator contract

Phase23 will expose one routine CLI with two modes:

`python scripts/run_phase23_analysis.py prepare --as-of YYYY-MM-DD [--broker webull|alpaca]`

`prepare` is strictly local/provider-free. It must:

- require an explicit exchange session rather than silently choosing an incomplete current day;
- inspect local canonical/reference/feature/universe/discovery/regime/downstream artifact coverage;
- compute the deterministic run scope and exact required external-read classes;
- report which stages are already current and which are missing/stale;
- perform **zero external provider/broker/AI calls** and zero broker/order writes;
- emit no mutation authority.

`python scripts/run_phase23_analysis.py execute --as-of YYYY-MM-DD [--broker webull|alpaca]`

For any missing work requiring external access, `execute` must require exact interactive run-scoped confirmation. There will be no command-line confirmation argument. A stale/mismatched preparation or changed run scope fails closed.

If all required upstream data/evidence is already local and current, execution may proceed locally without acquiring unnecessary external-read authority.

## 5. Finalized-session semantics

Phase23 operates on an explicit finalized exchange session. It must not use provisional intraday observations as finalized canonical facts.

- Daily and minute Massive flat-file sources remain the accepted post-2021 finalized source path.
- Canonical daily/minute materialization remains Phase2/3 implementation authority.
- Derived 1h/4h bars/features remain built only from accepted underlying intraday data; no synthetic pre-2021 intraday is introduced.
- Existing historical sessions are reused/idempotently skipped unless source/manifest evidence proves replay is required.
- Provider unavailability or entitlement gaps fail closed for the requested session rather than silently selecting a different date.

Phase5 streaming/live market state is not promoted to finalized analytical truth by Phase23. It remains useful for live-state observability/execution freshness under its accepted contracts.

## 6. Frozen model and strategy support

Phase23 does not rerun the Phase11 historical strategy study during routine cycles.

The accepted Phase11 strategy-support result remains frozen until a separately accepted strategy-evaluation phase changes it:

- SUPPORTED: 0;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Routine current evaluation must:

- verify the accepted historical-study/strategy-registry/model lineage and exact support mapping;
- reuse the accepted support evidence;
- evaluate only current discovery/regime/feature/ML conditions;
- preserve the rule that only historically `SUPPORTED` strategies can promote candidates;
- preserve zero promotions when the accepted support map yields zero eligible strategies.

The accepted production ML model remains `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`; raw `p_down/p_neutral/p_up` remain evidence only.

## 7. Downstream research/risk/AI binding

When current Phase11 promotions are zero:

- Phase12 closes as promoted-only no-op and does not access expensive analogue history;
- Phase13 performs no news/options/portfolio reads;
- Phase14 performs no AI call;
- the analytical cycle may still pass with zero Phase22-ready cases.

When promotions exist in a future accepted strategy-support state:

- Phase12 runs only for promoted candidates;
- Phase13 may perform bounded Massive news/options reads and must use current broker-neutral portfolio evidence for risk admission;
- missing portfolio/identity/correlation evidence remains `UNAVAILABLE`, never guessed;
- only `phase14_review_ready=true` cases reach Phase14;
- Phase14 remains an independent audit and cannot create or change deterministic trade authority;
- Phase23 ends with validated analytical/alert artifacts. PAPER execution still requires a separate Phase22 operator action and Phase21 exact submit authority.

## 8. Broker-neutral portfolio evidence

Phase23 may add a narrow adapter that translates selected PAPER-broker **read-only** account/position reconciliation into the existing `PortfolioSnapshot` contract.

Requirements:

- selected broker exact; Webull default, Alpaca only when manually specified;
- no automatic fallback;
- read-only account/position/open-order reconciliation before snapshot generation;
- exact instrument identity mapping or explicit `UNAVAILABLE`; ticker text alone cannot establish historical identity;
- sanitized local snapshot with no raw account ID, credential, token, signature, or provider secret;
- current timestamp/equity/cash/gross market value/positions and deterministic source fingerprint;
- zero broker mutations and zero order writes;
- unknown reconciliation state fails closed.

## 9. Run-state and evidence model

Phase23 is separate from Phase20's provider-free stage registry. It may reuse generic deterministic hashing/atomic-write/lease patterns, but it must not alter Phase20's accepted policy to make provider stages legal.

Each Phase23 run must have:

- explicit `as_of` session;
- selected broker;
- deterministic scope/run fingerprint;
- stage ledger with source/output hashes and status;
- atomic local manifest and sanitized append journal;
- restart/resume only for stages whose effects are known and idempotent;
- no blind retry of uncertain external operations;
- archived run-scoped copies/hashes of Phase11–14 handoff/acceptance artifacts so later cycles do not erase provenance;
- final disposition recording candidate/research/case/review/Phase22-ready counts.

External reads may be retried only under bounded read-safe policy. Broker/AI ambiguity must be surfaced explicitly; no mutation retry semantics are introduced.

## 10. Implementation package

Phase23 implementation should be one coherent batch containing:

1. Phase23 policy + deterministic scope/challenge contracts;
2. provider-free preparation/inventory;
3. finalized-data/reference refresh coordinator using existing services;
4. incremental 1d/4h/1h feature advancement;
5. existing universe/discovery/regime builders;
6. efficient current Phase11 materialization that reuses frozen accepted support rather than rerunning historical study;
7. Phase12/13/14 current-cycle binding and run-scoped artifact archive;
8. selected-broker read-only `PortfolioSnapshot` bridge if/when Phase13 cases require it;
9. CLI `prepare|execute` with interactive exact confirmation for required external reads;
10. independent Phase23 validator;
11. focused unit/integration tests with fake providers/brokers/AI;
12. Ubuntu/Windows full CI;
13. target-machine `prepare` first, followed by one explicitly authorized read-only current-cycle run only after software/CI validation.

## 11. Validation requirements

Independent validation must prove at minimum:

- deterministic Phase23 policy fingerprint;
- explicit finalized `as_of` required;
- provider-free `prepare` initializes no provider/broker/AI client;
- external-read challenge is deterministic and run-scoped;
- no command-line confirmation argument;
- no broker/order mutation calls in Phase23;
- Phase21/22 execution authority is not imported/acquired/invoked by the Phase23 analytical coordinator;
- Phase20 external mutation/read-stage policy remains unchanged/provider-free;
- frozen accepted Phase11 support mapping is exact and historical study is not rerun in routine mode;
- accepted Phase10 model identity/fingerprint remains exact;
- zero-promotion path skips Phase12 expensive history, Phase13 provider/portfolio reads, and Phase14 AI calls;
- nonzero fake-case path preserves promoted-only research, deterministic Phase13 admission, and Phase14 audit-only behavior;
- broker portfolio bridge is read-only, identity-safe, sanitized, and fail-closed;
- archived run evidence is hash-bound and restart-safe;
- provider/broker/AI counts are explicit;
- broker writes/order writes/PAPER submits/LIVE writes remain zero during Phase23 validation.

## 12. Target-machine boundary

Repository CI/fakes must perform zero real provider/broker/AI calls.

After exact-head cross-platform CI is green:

1. run `prepare` on the target machine for an explicit finalized session; this must remain provider-free;
2. inspect the deterministic missing-work/external-read plan;
3. only then perform one explicitly authorized Phase23 read-only current analytical cycle;
4. record provider-read counts, local artifact lineage, candidate/research/case/review counts, and final Phase22-ready count;
5. if the accepted strategy support still yields zero promotions, accept that zero-case outcome rather than changing thresholds;
6. do not invoke Phase22 PAPER execution merely as a Phase23 acceptance requirement.

## 13. Non-goals

Phase23 does not:

- improve or replace the production model;
- redesign strategy rules or support thresholds;
- promote MIXED strategies to SUPPORTED;
- introduce new strategies merely to create signals;
- add autonomous scheduling;
- promote PostgreSQL;
- give the browser trading authority;
- submit/cancel/replace/flatten orders;
- enable LIVE;
- enable automatic broker failover;
- prove profitability.

## 14. Exit criteria

Phase23 may be ACCEPTED only when:

- one routine current-cycle operator path exists and uses accepted implementations rather than parallel replacements;
- provider-free preparation is independently proven;
- exact read-only external authority is default-deny and run-scoped;
- current data/reference/features/universe/discovery/regimes advance deterministically for the requested session;
- accepted ML/strategy support is reused without historical restudy;
- downstream research/risk/AI is correctly conditional on promoted/review-ready cases;
- broker-neutral portfolio evidence, when required, comes from reconciled read-only selected-broker state or remains unavailable;
- run evidence is archived/hash-bound;
- full Ubuntu/Windows CI is green;
- required target-machine read-only evidence is recorded;
- documentation is synchronized;
- no broker/order/LIVE mutation occurred.

After Phase23, routine analytical cycles should be able to feed Phase22 naturally. A later phase may address scheduler automation only after this explicit operator cycle is operationally accepted.