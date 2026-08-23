# ATLAS Master Roadmap

**Living architecture and authority document. Last synchronized: 2026-08-23.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This roadmap is the project-level direction lock. Implementation may evolve when measured evidence requires it, but changes must preserve the architectural and safety boundaries below unless an explicit design decision replaces them.

Read with:

- [`current_status.md`](current_status.md) — current operational handoff and evidence ledger;
- [`phase18_operational_validation.md`](phase18_operational_validation.md) — exact active Phase 18 certification design;
- [`../README.md`](../README.md) — project orientation.

## 1. Mission

Build a broad-market discovery, quantitative analysis, decision-support, learning, and eventually automated-trading platform that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market data, instrument identity, features, and regimes;
3. discover promising candidates cheaply and quickly;
4. estimate outcome probabilities with conventional ML;
5. route candidates to deterministic strategies appropriate to current regime/context;
6. spend expensive research only on promoted candidates;
7. combine quantitative, historical-analogue, scenario/simulation, news/event/sentiment, instrument, and risk evidence into one case;
8. subject that deterministic case to an independent AI audit rather than letting AI replace the engine;
9. construct executable plans only after geometry, liquidity, portfolio, and broker-risk checks;
10. validate shadow/paper operation before any live-money promotion;
11. record outcomes so models, strategies, routing, and risk policies can be evaluated and improved;
12. expose the system through a browser control plane with transparent reasoning, broker/mode controls, candidates, alerts, positions, and operational health.

The legacy Chart Monitor is preserved. ATLAS is the redesign/rebuild path; legacy components are not deleted merely because ATLAS introduces replacements.

## 2. Target architecture

Primary flow:

`market/reference data -> Parquet data lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> strategy routing/evaluation -> candidate promotion -> historical analogue + Monte Carlo/scenario research -> news/events/sentiment -> instrument selection -> entry/stop/target/horizon -> portfolio/risk -> consolidated deterministic case -> independent AI audit -> alert/paper/shadow/live execution -> outcome/performance learning -> browser control plane`

Storage/state roles:

- **Parquet** — durable analytical/historical lake.
- **DuckDB** — local analytical/query engine.
- **PostgreSQL** — target persistent operational-state store for state that should not live in the analytical lake.
- Provider-native facts, canonical facts, derived features, regime/strategy state, model evidence, AI audit, and broker state remain explicitly separated.

Provider/broker roles:

- **Massive** — accepted primary market/reference-data provider in the production data path.
- **Webull** — planned primary execution broker; current accepted real operational target is Webull US sandbox.
- **Alpaca** — manually selectable secondary/fallback broker; current accepted real operational target is Alpaca paper.
- **IBKR** — optional future/data-fallback integration point; configuration placeholders do not imply accepted runtime authority.

## 3. Non-negotiable data and identity rules

- Preserve exact provider-native ticker text/case.
- Literal ticker text alone never proves identity continuity.
- Historical populations are observation-driven and point-in-time safe; current survivor state is never projected backward.
- Strong security-level identity evidence is preferred; when continuity is not provable, false split is safer than false merge.
- Ambiguous identity/lineage is quarantined or excluded rather than guessed.
- Long-running acquisition/replay is restartable, idempotent, checkpointed, and duplicate-safe.
- Provider/canonical/derived promotions require explicit lineage and independent validation.
- Finalized canonical facts remain authoritative over provisional live observations.
- Do not synthesize unavailable pre-2021 intraday bars from daily history.

Accepted historical source boundary:

- Alpaca raw SIP daily: **2016-01-04 through 2021-08-13**;
- Massive authority: **2021-08-16 onward**;
- no synthetic pre-2021 1h/4h history.

## 4. Discovery, regimes, strategy, and research rules

- Broad discovery remains cheap-first and instrument-agnostic.
- Default discovery eligibility is separate from position/watchlist/custom mandatory routing.
- Regimes are context/routing evidence, not hidden strategy logic.
- Strategy-to-regime routing belongs in the router/orchestration layer.
- Strategy implementations emit deterministic setup evidence and do not own broker/order authority.
- Missing authoritative sector/identity/history context stays unavailable rather than being guessed.
- Expensive analogue, scenario/Monte Carlo, options-chain, and deep-context work runs only after candidate promotion.
- Historical/analogue/scenario evidence does not independently create an order.

Accepted Phase 8 discovery thresholds remain:

- WATCH >= 0.35;
- WARM >= 0.50;
- HOT >= 0.60 plus direction/evidence/full-timeframe guards.

## 5. Machine-learning rules

The accepted production probability layer is conventional ML, not an LLM.

Accepted Phase 10 production model:

- id: `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- specification: `hgb_leaf15_iter100`;
- predictors: 33 point-in-time quantitative features;
- outputs: raw `p_down`, `p_neutral`, `p_up`;
- post-hoc calibration: none;
- protected holdout: 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

Rules:

- ML argmax is diagnostic only, never a trade signal.
- Chronological walk-forward validation, purge/embargo, leakage control, immutable OOS predictions, and reproducibility remain mandatory.
- A new dataset/model never silently replaces the accepted production model.
- Challengers require separately versioned evidence and explicit acceptance.
- The longer-history C result remains challenger/research evidence, not production authority.

## 6. AI-review rules

- AI is an independent structured auditor, not the predictive model.
- Accepted dispositions are `APPROVE`, `CAUTIOUS`, `REJECT` as audit classifications.
- AI may challenge a deterministic case but may not rewrite historical facts, model probabilities, strategy evidence, direction, instrument, geometry, sizing, portfolio admission, or validation evidence.
- Engine evidence and AI audit remain separately visible.
- AI cannot create broker authority or place an order merely by approving a case.

## 7. Geometry and portfolio-risk rules

- LONG requires `stop < entry < target`.
- SHORT requires `stop > entry > target`.
- Invalid geometry cannot advance.
- Sizing, exposure, concentration, correlation, liquidity, and portfolio admission are deterministic and independently verifiable.
- Missing portfolio evidence is unavailable, not guessed.

Accepted Phase 13 envelope includes:

- risk per trade: **0.5% of equity**;
- single-name notional cap: **10% of equity**;
- gross-notional/open-position/correlation controls remain enforced where applicable.

## 8. Execution and broker rules

- Webull is primary; Alpaca is manually selectable secondary/fallback.
- Broker adapters remain replaceable without changing strategy logic.
- Automatic cross-broker failover is disabled.
- Broker changes are explicit and reconciliation-gated.
- Browser/control-plane actions cannot bypass broker/risk/reconciliation contracts.
- Fresh-quote translation, current risk, provider preflight, protective stop/target, deterministic client IDs, and idempotency are mandatory for normal paper execution.
- Unknown or uncertain provider state never authorizes another mutation without exact reconciliation.
- Cancel/close/flatten actions require explicit mutation authority.
- Live credentials/endpoints do not create live authority.
- Live money is never the first validation environment: **paper -> shadow/observation -> controlled live**.

## 9. Accepted phase ledger

### Phases 1–3 — foundation, ingestion, canonical storage

Established shared settings/secret handling, UTC/XNYS session conventions, canonical/data-quality contracts, restartable Massive flat-file ingestion, atomic manifests/checkpoints, and canonical/session-aware Parquet materialization.

### Phase 4 — instrument identity and historical lake

Accepted provider-native symbol case, point-in-time reference snapshots, security-safe identity, authoritative ticker-event continuity where available, ticker-reuse protection, anomaly reconciliation, and complete provider/canonical/derived historical-lake auditing.

### Phase 5 — live market state

Accepted explicit delayed/realtime Massive WebSocket modes, provisional live state, freshness/reconnect-gap accounting, journal/restart behavior, and finalized-data reconciliation. Live observations remain provisional.

### Phase 6 — feature engine

Accepted 33 deterministic point-in-time features, batch/incremental equivalence, recursive checkpoints, and permanent persistence for 1d/4h/1h. Accepted permanent lake through 2026-08-14 contained **154,188,221 rows** and passed deep lineage/continuation checks.

### Phase 7 — universe registry

Accepted security-safe point-in-time universe construction. Accepted 2026-08-14 routed discovery universe: **12,066 instruments**.

### Phase 8 — broad discovery

Accepted cheap-first health/activity/setup funnel. Accepted broad-ready population: **8,034 instruments**.

### Phase 9 — market/sector/ticker regime engine

Accepted market and sector-proxy context, optional authoritative SIC, stable-identity ticker regimes, persistence, risk state, and hierarchy validation. Accepted effective current ticker states: **7,338**.

### Phase 10 — conventional ML probability/evaluation

Accepted the HGB probability model above with full chronological/protected-holdout/reproducibility evidence.

### Historical extension

Accepted Alpaca raw SIP daily extension to 2016, source seam into Massive, observation-driven historical populations, identity segmentation, feature/regime replay, and versioned longer-history challenger evidence without replacing production ML authority.

### Phase 11 — strategy evaluation and regime routing

Accepted eight deterministic strategies with external routing. Historical support result:

- SUPPORTED: 0;
- MIXED: 3 — `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: 5.

Zero supported strategies correctly produced zero promoted candidates; thresholds were not weakened after seeing the result.

### Phase 12 — deep candidate research

Accepted promoted-only analogue/empirical scenario research and strict no-op semantics when no candidate is promoted.

### Phase 13 — context, instrument, geometry, portfolio risk

Accepted deterministic context, instrument, geometry, sizing/liquidity, exposure/concentration/correlation, and portfolio-risk planning. Equity remains v1 primary execution instrument; options cannot silently become primary without an accepted relative-value model.

### Phase 14 — independent AI audit and alerting

Accepted structured independent AI audit and Engine-vs-AI artifact alerting with no execution authority.

### Phase 15 — broker execution and outcome learning foundation

Accepted broker-neutral paper/shadow execution contracts, fresh quote/risk/preflight/reconciliation/protective orders/idempotency, Webull primary + Alpaca manual secondary, and descriptive outcome learning. Live was hard-disabled.

### Cumulative data/lineage audit

Accepted a read-only cross-layer integrity gate covering source/canonical/feature/regime/identity lineage before execution advancement.

### Phase 16 — browser control plane and production operations

Accepted status/action APIs, audit/idempotency, restart/recovery, broker-switch workflow, cleanup planning/confirmation, and loopback-first operation. Browser is not execution authority. Provider cleanup writes and live money remained disabled.

### Phase 17 — provider-readonly operational readiness

Accepted 2026-08-23 with real Webull sandbox and Alpaca paper reads:

- both brokers `AVAILABLE` and reconciled;
- zero open orders / zero positions;
- exactly two provider adapters initialized;
- provider mutation endpoint invocations: 0;
- provider writes: 0;
- live writes: 0;
- automatic failover disabled;
- live disabled;
- Phase 17 validator PASS;
- target-machine regression: **874 passed in 24.83s**;
- Windows/Ubuntu CI PASS.

Phase 17 grants read/reconciliation evidence only.

## 10. Active Phase 18 — Paper Provider Mutation Lifecycle Validation

Phase 18 is active on draft PR #18.

Branch:

`phase-18-paper-provider-mutation-lifecycle-validation`

Green code-bearing head:

`062efedfdc7537222c929f72ebf1f1bb57f903af`

Phase 18 policy contract:

`phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`

Policy fingerprint:

`9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`

Current repository-side CI evidence:

- Phase 18 validator PASS on Windows/Ubuntu;
- all prior validators PASS;
- Ubuntu: **908 passed in 17.80s**;
- Windows: **908 passed in 31.79s**;
- both jobs SUCCESS.

### 10.1 Authority split

Phase 18 deliberately has two authority levels:

1. **repository/CI preparation** — allowed now; code/tests/validators/docs may advance with no real broker writes;
2. **real target-machine paper-provider mutation** — remains separately gated by `PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`.

Real mutation requires:

- one selected broker;
- explicit mutation boolean/flag;
- exact confirmation text `AUTHORIZE_PAPER_PROVIDER_MUTATION`.

No credential, endpoint, environment setting, prior acceptance, or passing test may substitute for this gate.

### 10.2 Production semantic path vs operational certification path

Phase 18 fake-provider tests wrap the accepted Phase 15 engine to prove production execution semantics remain safe.

The first real provider certification intentionally uses a **separate validation-only operational order**, not fabricated Phase 13/14 trade lineage. This prevents a broker-plumbing test from polluting strategy/model/AI evidence.

Operational validation contract:

`phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket`

Locked order:

- paper/sandbox only;
- equity BUY only;
- exactly 1 share;
- LIMIT / DAY / no extended hours;
- entry 5% below fresh realtime bid;
- stop 2% below entry;
- target 2% above entry;
- max validation notional $1,000;
- accepted Phase 13 10% single-name and 0.5% loss-at-stop limits still apply.

### 10.3 Live quote authority

The operational plan requires an undelayed realtime regular-session Massive quote.

The accepted path is:

- `scripts/run_live_market_state.py` starts `LiveMarketService`;
- focused subscription: `Q.<ticker>`;
- `Phase15LiveQuoteResolver` reads live state and requires connection `SUBSCRIBED`, realtime, delay 0, no open transport gap, regular session, exact ticker, and FRESH quote.

Stopped stream state, delayed data, stale data, weekends, holidays, premarket, and after-hours are rejected. Phase 18 must wait for valid market conditions rather than weakening this rule.

### 10.4 Broker/risk/idempotency gates

Before preview/submit:

- selected broker reconciles;
- zero open orders;
- zero positions;
- account not trading-blocked;
- positive equity;
- enough buying power;
- Phase 13 risk envelope passes;
- exact deterministic validation client-order ID is proven absent;
- provider preflight accepts.

Only `BrokerOrderNotFound` is accepted as proof that a client ID does not exist; ambiguous query failures block mutation.

### 10.5 Mutation lifecycle

Expected successful certification:

`authorize -> reconcile -> risk/idempotency/preflight -> submit once -> exact client-ID reconcile -> cancel once if still open -> reconcile flat`

If fill/partial fill occurs, ATLAS does **not** auto-flatten. Separate explicit cleanup authority is required.

If submit/cancel is uncertain, ATLAS attempts read-only reconciliation if possible and stops. It never blindly retries, issues a second mutation, or fails over to Alpaca.

### 10.6 Runner behavior

`scripts/run_phase18_operational_validation.py` requires explicit `--broker` and `--ticker`; there is no quantity parameter or default ticker.

Plan-only is the default and initializes no broker adapter, performs 0 broker/provider calls, and performs 0 writes. Wrong confirmation also blocks before broker initialization.

Full Phase 18 design and target-machine sequence: [`phase18_operational_validation.md`](phase18_operational_validation.md).

## 11. Current environment/configuration policy

`.env.example` is a tracked **non-secret template**. It may contain public provider endpoints, localhost/default connection values, and blank credential placeholders for accepted/planned integrations.

Current groups:

- `ATLAS_ENV`, `OPENAI_API_KEY`, `DATABASE_URL`;
- Massive API/S3 placeholders + `MASSIVE_ENDPOINT=https://files.massive.com`;
- Webull paper/sandbox + future live credential placeholders;
- Alpaca paper/live endpoints + blank credential placeholders;
- optional IBKR `127.0.0.1:4002` / client-ID default.

Rules:

- real `.env` remains local/ignored;
- API keys/secrets, passwords, raw account IDs, security codes, tokens, and session secrets are never committed;
- commented secret values are still secrets;
- live variable names/endpoints do not authorize live trading;
- IBKR placeholders do not imply accepted runtime integration;
- generated `webull_trade_sdk.log*` files remain ignored.

## 12. Accelerated delivery protocol

Quality gates remain; micro-step ceremony does not.

A normal batch should combine:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status update`

During a batch:

- run focused tests while coding;
- run full regression and Windows/Ubuntu CI at the evidence boundary;
- use independent validators for data/model/broker authority transitions;
- automate read-only diagnostics/preregistration rather than stopping for every micro-step;
- fail closed on ambiguity, missing lineage/data, broker uncertainty, uncertain writes, or invalid geometry;
- never invent post-hoc thresholds to force acceptance.

Ask the user for input only when local/external evidence is unavailable, validation changes a technical decision, an irreversible/authority-changing write is required, a broker/live-money transition is reached, or a genuine unresolved product/design choice remains.

## 13. Repository and documentation policy

- `main` contains accepted work.
- Substantial/authority-changing work uses focused branches/PRs.
- Target-machine + CI evidence is recorded in the PR before merge.
- Merged phase branches are deleted after closeout unless a concrete reason exists.
- Historical PR/commit evidence remains available after branch deletion.

Documentation is part of acceptance. At every meaningful change/boundary update as applicable:

1. root `README.md`;
2. this roadmap;
3. `docs/current_status.md`;
4. active PR body;
5. phase-specific living spec such as `docs/phase18_operational_validation.md`;
6. `.env.example`/configuration notes when configuration changes.

Historical phase/fix READMEs remain provenance, not living status documents.

## 14. Exact current authority boundary

Phase 18 repository/CI preparation is green, but **real provider mutation is not yet authorized**.

Checkpoint:

`PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION`

Until that checkpoint is explicitly crossed for a target-machine run:

- real provider submit remains disabled;
- replace/cancel remains disabled;
- flatten/close remains disabled;
- broker-switch cleanup mutation remains disabled;
- live execution remains disabled;
- automatic cross-broker failover remains disabled.

Because a fresh undelayed **regular-session** quote is mandatory, the first real Phase 18 certification must occur during a normal U.S. equity regular session. It must not be performed on a weekend simply by relaxing the quote gate.

## 15. Remaining Phase 18 closeout sequence

1. pull the exact Phase 18 branch on target machine;
2. run Phase 18 validator and local regression/targeted tests;
3. run Phase 17 read-only provider diagnostic again;
4. during regular market hours, run focused Massive realtime `Q.<ticker>` live state;
5. run the Phase 18 **plan-only** command and verify zero broker/provider calls/writes;
6. review the exact one-share validation order;
7. obtain explicit paper-provider mutation authorization;
8. certify **Webull sandbox first** because Webull is primary;
9. reconcile result;
10. if still open, cancel and prove flat state;
11. if any fill/partial fill occurs, stop for separate cleanup authorization;
12. never auto-fail over to Alpaca;
13. record sanitized target-machine evidence in PR/docs;
14. mark PR ready/merge only after acceptance;
15. delete merged Phase 18 branch after closeout.

## 16. Later roadmap

After accepted paper-provider mutation, continue with bounded evidence/authority steps rather than jumping to live money:

1. repeated shadow/paper operational observation and outcome capture;
2. failure/recovery/monitoring/operator hardening;
3. evaluation of fresh strategy/model/research performance;
4. only after sufficient evidence, design a separately preregistered controlled-live phase;
5. require separate explicit live-money authorization.

Successful sandbox mutation never implicitly authorizes trading real capital.
