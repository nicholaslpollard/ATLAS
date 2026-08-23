# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the redesign/rebuild path for the existing Chart Monitor; the legacy system is preserved rather than deleted while ATLAS matures.

## Start here

For any new development session or future chat, read these living documents in order:

1. **[`docs/current_status.md`](docs/current_status.md)** — detailed current handoff, accepted evidence, broker authority, and exact next checkpoint.
2. **[`docs/roadmap.md`](docs/roadmap.md)** — architecture lock, non-negotiable rules, accepted phase responsibilities, validation protocol, and authority boundaries.
3. This README — project orientation and concise current state.

Merged pull requests are the detailed acceptance/evidence ledger. Files named `README_PHASE_*`, `README_ATLAS_*`, old phase status documents, and fix notes are **historical records**, not the current roadmap.

## Core architecture

`market/reference data -> Parquet data lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> strategy routing/evaluation -> candidate promotion -> historical analogue + Monte Carlo/scenario research -> news/events/sentiment -> instrument selection -> entry/stop/target/horizon -> portfolio/risk -> consolidated deterministic case -> independent AI audit -> alert/paper/shadow/live execution -> outcome/performance learning -> browser control plane`

Key architectural roles:

- **Parquet**: durable analytical/historical lake.
- **DuckDB**: local analytical/query engine.
- **PostgreSQL**: target for persistent operational state that does not belong in the analytical lake.
- **Conventional ML**: produces `p_down`, `p_neutral`, `p_up` probability evidence; argmax is diagnostic only.
- **Strategies/router**: determine setup/routing semantics; regime logic stays outside strategy implementations.
- **Deep research**: analogue/Monte Carlo/scenario/options/context work is promoted-candidate only.
- **AI**: independent audit/reviewer; it is not the predictive model and is not execution authority.
- **Execution**: broker-neutral contracts with reconciliation, fresh-quote/risk checks, protective geometry, idempotency, and fail-closed uncertainty handling.
- **Browser**: control plane and monitoring surface, never an independent source of trading authority.

## Current accepted state — 2026-08-23

**Phases 1-17 are accepted and merged.** The accepted stack now includes:

- foundation/configuration/canonical contracts;
- restartable Massive provider ingestion;
- canonical/session-aware market history;
- security-safe instrument identity and historical lake;
- provisional live market state and finalized reconciliation;
- 33-feature deterministic feature engine;
- point-in-time universe registry;
- broad-market discovery and persisted state;
- market/sector/ticker regime hierarchy;
- conventional ML probability/evaluation layer;
- controlled Alpaca raw-SIP historical extension back to 2016;
- strategy evaluation and external regime routing;
- promoted-only analogue/scenario research;
- deterministic context/instrument/geometry/portfolio risk;
- independent AI audit and artifact alerting;
- broker-neutral shadow/paper execution contracts and outcome learning;
- cumulative data/lineage integrity acceptance;
- browser control plane and operational recovery/audit semantics;
- real Webull sandbox + Alpaca paper **read-only** provider reconciliation.

### Accepted historical source boundary

- Alpaca raw SIP daily: **2016-01-04 through 2021-08-13**.
- Massive production authority: **2021-08-16 onward**.
- Pre-2021 intraday bars are **not** synthesized from daily history.
- Historical population and identity are point-in-time/observation driven; literal ticker text never proves continuity.

### Accepted production ML model

The authoritative Phase 10 model remains:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB specification `hgb_leaf15_iter100`;
- 33 point-in-time quantitative predictors;
- raw three-class probability output;
- no post-hoc calibration;
- protected final holdout 2026-05-12 through 2026-08-11;
- final holdout log loss 0.948693, Brier 0.560422, macro OVR AUC 0.570016;
- exact deterministic probability replay.

Longer-history C evidence remains a separately versioned challenger/research result. It does **not** silently replace production model authority.

### Strategy/research state

Phase 11 accepted eight deterministic strategy variants with historical support classification:

- SUPPORTED: 0;
- MIXED: 3;
- UNSUPPORTED: 5.

Therefore the accepted 2026-08-14 path produced zero promoted candidates. Downstream Phases 12-15 correctly support strict zero-case/no-op closeout behavior rather than weakening thresholds to manufacture trades.

### Broker state and authority

- **Webull** is the planned primary execution broker.
- **Alpaca** is the manually selectable secondary/fallback broker.
- Automatic cross-broker failover is disabled.
- Broker switching is explicit and reconciliation-gated.
- Phase 17 accepted read-only access to real Webull sandbox and Alpaca paper accounts.
- Both brokers reconciled `AVAILABLE` with zero open orders and zero positions in the accepted Phase 17 target-machine run.
- Phase 17 performed **0 provider mutation endpoint invocations, 0 provider writes, and 0 live writes**.
- Full Phase 17 target-machine regression: **874 passed in 24.83s**; Windows and Ubuntu CI also passed.

## Current authority boundary

The exact next checkpoint is:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

Phase 17 success does **not** grant provider-mutation authority. Until explicit authorization is given, ATLAS may not perform real provider:

- order submission;
- order replacement;
- order cancellation;
- flatten/close writes;
- broker-switch cleanup writes.

Live execution remains disabled. Automatic broker failover remains disabled. Any future paper-provider mutation acceptance must remain separate from any later live-money promotion.

## Non-negotiable safety/data rules

- Preserve exact provider-native ticker text/case.
- Never infer identity continuity from ticker text alone.
- Use point-in-time historical populations; never project current survivor state backward.
- Quarantine/exclude ambiguity rather than guessing.
- Keep acquisition/replay restartable, idempotent, and duplicate-safe.
- Require lineage and independent validation at data/model/authority transitions.
- Do not fabricate unavailable intraday history.
- ML probability output is evidence, not a trade signal.
- AI may audit/challenge but cannot rewrite deterministic evidence or authorize execution.
- Valid trade geometry is mandatory: `LONG stop < entry < target`; `SHORT stop > entry > target`.
- Unknown broker/provider state fails closed.
- Live money is never the first validation environment: paper -> shadow/observation -> controlled live.

## Development workflow

ATLAS uses an accelerated evidence-boundary workflow. A normal work package should combine:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status update`

Use focused tests while coding, then full regression and cross-platform CI at the batch boundary. Independent validators remain required where data/model/broker authority changes. When target-machine evidence is needed, prefer one complete PowerShell block instead of repeated micro-steps.

Documentation synchronization is part of every meaningful change. `README.md`, `docs/roadmap.md`, `docs/current_status.md`, and the active PR acceptance ledger must be updated whenever their state changes.

## Repository/documentation conventions

- `main` contains accepted work.
- Substantial phases/authority-changing work use focused branches/PRs.
- Merged phase branches are deleted after closeout unless there is a concrete reason to retain them.
- Real `.env` remains local and ignored; `.env.example` is template-only and must contain no real credentials.
- Historical phase/fix READMEs remain frozen for provenance and should not be used as current status.

For the complete current handoff, continue with **[`docs/current_status.md`](docs/current_status.md)**. For architecture and future authority rules, use **[`docs/roadmap.md`](docs/roadmap.md)**.
