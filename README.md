# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform. It is the redesign/rebuild path for the existing Chart Monitor; the legacy system is preserved rather than deleted while ATLAS matures.

## Start here

For any new development session or future chat, read these living documents in order:

1. **[`docs/current_status.md`](docs/current_status.md)** — detailed current handoff, accepted evidence, broker authority, configuration state, and exact next checkpoint.
2. **[`docs/roadmap.md`](docs/roadmap.md)** — architecture lock, non-negotiable rules, accepted phase responsibilities, validation protocol, and authority boundaries.
3. This README — project orientation and concise current state.

Merged pull requests are the detailed acceptance/evidence ledger. Files named `README_PHASE_*`, `README_ATLAS_*`, old phase status documents, and fix notes are historical records, not the current roadmap.

## Core architecture

`market/reference data -> Parquet data lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> strategy routing/evaluation -> candidate promotion -> historical analogue + Monte Carlo/scenario research -> news/events/sentiment -> instrument selection -> entry/stop/target/horizon -> portfolio/risk -> consolidated deterministic case -> independent AI audit -> alert/paper/shadow/live execution -> outcome/performance learning -> browser control plane`

Key architectural roles:

- **Parquet**: durable analytical/historical lake.
- **DuckDB**: local analytical/query engine.
- **PostgreSQL**: target for persistent operational state that does not belong in the analytical lake.
- **Massive**: primary market/reference-data provider in the accepted production-data path.
- **Conventional ML**: produces `p_down`, `p_neutral`, `p_up` probability evidence; argmax is diagnostic only.
- **Strategies/router**: determine deterministic setup/routing semantics; regime logic stays outside strategy implementations.
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
- real Webull sandbox + Alpaca paper read-only provider reconciliation.

Phase 17 was accepted on target-machine evidence and merged into `main` after the Webull sandbox and Alpaca paper accounts both reconciled successfully with no provider mutation.

## Accepted historical source boundary

- Alpaca raw SIP daily: **2016-01-04 through 2021-08-13**.
- Massive production authority: **2021-08-16 onward**.
- Pre-2021 intraday bars are **not** synthesized from daily history.
- Historical population and identity are point-in-time/observation driven; literal ticker text never proves continuity.
- Provider-native ticker text/case is preserved.
- Unresolved continuity is quarantined/excluded rather than guessed.

## Accepted production ML model

The authoritative Phase 10 model remains:

- model id: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- specification: `hgb_leaf15_iter100`;
- 33 point-in-time quantitative predictors;
- raw three-class probability output `p_down`, `p_neutral`, `p_up`;
- no post-hoc calibration;
- protected final holdout: 2026-05-12 through 2026-08-11;
- holdout population: 63 sessions / 454,773 rows;
- final holdout log loss: 0.948693;
- final holdout Brier: 0.560422;
- macro OVR AUC: 0.570016;
- exact deterministic probability replay.

Longer-history C evidence remains a separately versioned challenger/research result. It does not silently replace production model authority.

## Strategy/research state

Phase 11 accepted eight deterministic strategy variants with historical support classification:

- SUPPORTED: 0;
- MIXED: 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: 5.

Therefore the accepted 2026-08-14 path produced zero promoted candidates. Downstream Phases 12-15 correctly support strict zero-case/no-op closeout behavior rather than weakening thresholds to manufacture trades.

## Broker architecture

### Webull

Webull is the planned primary execution broker for paper/sandbox operation and, only after a future separately accepted authority transition, controlled live operation.

Accepted Phase 17 state:

- official Webull US sandbox integration path is used for current provider testing;
- account selection is explicit and fail-closed when more than one account is readable;
- a Webull sandbox margin account was explicitly selected locally after five readable accounts were discovered;
- account/balance/open-order/position reads passed;
- accepted closeout state had 0 open orders and 0 positions;
- provider mutation was not authorized or exercised.

### Alpaca

Alpaca is the manually selectable secondary/fallback execution broker. The accepted integration uses paper trading for current operational validation.

Accepted Phase 17 state:

- Alpaca paper account reads/reconciliation passed;
- accepted closeout state had 0 open orders and 0 positions;
- automatic failover from Webull to Alpaca remains forbidden;
- provider mutation was not authorized or exercised.

### Broker switching

Broker switching is explicit only. The system must inspect orders/positions and reconcile broker state before switching. Any cancel/close/flatten action needed to make a broker safe requires the corresponding provider-mutation authority and explicit user action. Automatic cross-broker failover remains disabled.

## Phase 17 closeout evidence

Accepted target-machine result:

- Webull read path: account list, configured balance, open orders, positions all reached successfully;
- Alpaca paper: reconciled successfully;
- both broker rows: `AVAILABLE`, `reconciled=true`, `safe_to_switch_broker=true`;
- exactly 2 provider adapters initialized;
- provider mutation endpoint invocations: **0**;
- provider writes: **0**;
- live writes: **0**;
- Phase 16 accepted artifacts remained unchanged and hash-bound;
- Phase 17 validator: PASS;
- target-machine regression: **874 passed in 24.83s**;
- Windows CI: PASS;
- Ubuntu CI: PASS.

## Current authority boundary

The exact next checkpoint is:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

Phase 17 success does not grant provider-mutation authority. Until explicit authorization is given, ATLAS may not perform real provider:

- order submission;
- order replacement;
- order cancellation;
- flatten/close writes;
- broker-switch cleanup writes.

Live execution remains disabled. Automatic broker failover remains disabled. Any future paper-provider mutation acceptance must remain separate from any later live-money promotion.

## Environment/configuration template

The tracked `.env.example` is a non-secret template. It may contain public/local endpoint defaults and blank credential placeholders, including configuration planned for later phases. The presence of a live-variable name or endpoint in `.env.example` is **not authority to use live trading**.

Current template groups:

- application: `ATLAS_ENV`, `OPENAI_API_KEY`, `DATABASE_URL`;
- Massive primary market data: API/S3 credential placeholders and `MASSIVE_ENDPOINT=https://files.massive.com`;
- Webull primary broker: paper/sandbox and future live credential placeholders;
- Alpaca secondary broker: paper/live endpoints and blank credential placeholders;
- IBKR optional data fallback: local host/port/client-ID defaults.

Credential values, raw broker account IDs, security codes, passwords, and tokens must remain in the real local `.env` or other approved secret store and must never be committed to `.env.example`, source code, README files, PR descriptions, or logs.

The commented Alpaca security-code placeholder in `.env.example` is intentionally blank. A commented secret value is still a secret and must not be committed merely because the line starts with `#`.

Generated `webull_trade_sdk.log*` files are ignored.

## Non-negotiable safety/data rules

- Preserve exact provider-native ticker text/case.
- Never infer identity continuity from ticker text alone.
- Use point-in-time historical populations; never project current survivor state backward.
- Quarantine/exclude ambiguity rather than guessing.
- Keep acquisition/replay restartable, idempotent, checkpointed, and duplicate-safe.
- Require lineage and independent validation at data/model/authority transitions.
- Do not fabricate unavailable intraday history.
- Finalized canonical data remains authoritative over provisional live observations.
- ML probability output is evidence, not a trade signal.
- AI may audit/challenge but cannot rewrite deterministic evidence or authorize execution.
- Valid trade geometry is mandatory: `LONG stop < entry < target`; `SHORT stop > entry > target`.
- Unknown broker/provider state fails closed.
- Uncertain writes must reconcile exact state/client identifiers before another mutation is attempted.
- Live money is never the first validation environment: paper -> shadow/observation -> controlled live.

## Development workflow

ATLAS uses an accelerated evidence-boundary workflow. A normal work package should combine:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status update`

Use focused tests while coding, then full regression and cross-platform CI at the batch boundary. Independent validators remain required where data/model/broker authority changes. When target-machine evidence is needed, prefer one complete PowerShell block instead of repeated micro-steps.

User interaction is normally reserved for unavailable local/external evidence, a validation result that changes a technical decision, an irreversible/authority-changing write, a broker/live-money transition, or a genuinely unresolved product/design decision.

## Documentation policy

Documentation synchronization is part of every meaningful ATLAS change.

At each coherent work-package or phase boundary, update as applicable:

- root `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- the active PR acceptance/evidence ledger;
- configuration documentation/templates when configuration changes.

Historical phase/fix READMEs remain frozen provenance unless correcting a factual error in that historical record.

## Repository conventions

- `main` contains accepted work.
- Substantial phases/authority-changing work use focused branches/PRs.
- Acceptance evidence is recorded before merge.
- Merged phase branches are deleted after closeout unless there is a concrete reason to retain them.
- Real `.env` remains local and ignored.
- `.env.example` is tracked, non-secret, and may include endpoint/default configuration values.
- Historical phase/fix READMEs are evidence, not current instructions.

For the complete current handoff, continue with **[`docs/current_status.md`](docs/current_status.md)**. For architecture and authority rules, use **[`docs/roadmap.md`](docs/roadmap.md)**.
