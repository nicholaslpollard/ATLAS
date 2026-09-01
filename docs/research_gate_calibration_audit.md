# Research Gate Calibration and End-to-End System Audit

**Scope:** prospective research-gate reachability, population coverage, strategy-path reachability, and authority-boundary audit.  
**Historical-result rule:** no frozen Phase26–32 result is rescued, retuned, weakened, or reclassified by this audit.  
**Protected-data rule:** the master protected outcome window `2026-05-12..2026-08-11` remains unopened by this audit.  
**Trading-authority rule:** this audit grants no new PAPER or LIVE authority.

## 1. Executive conclusion

ATLAS is **not globally stuck closed**.

The actual Phase26 selection machinery can reject a null synthetic population, can promote a realistic planted positive population, and can promote a stronger planted population consistently. The downstream deterministic/risk/execution stack also has positive paths: a completed research case can produce valid geometry and admissible portfolio risk, Phase14 can review the immutable case without creating an order, Phase15 can construct an execution intent from a valid case, and Phase21 can authorize exactly one PAPER submission for either Webull or Alpaca when the explicit authority contract is satisfied.

The current absence of supported alpha therefore cannot be explained by one universal `always reject` predicate.

The audit did identify a different and important problem class: some recent event/source experiments reached very small populations or exhausted source capacity before their frozen minimums could be met. Future experiments must prove gate arithmetic, source capacity, population scope, and positive-path power **before** the scientific contract is frozen and before outcomes are opened.

## 2. Phase26 positive-path calibration

The calibration code calls the real Phase26 `tranche_metrics`, `selection_checks`, and Holm-Bonferroni implementation.

Frozen Phase26 multiplicity arithmetic:

- candidate count: **24**;
- family alpha: **0.05**;
- strictest Holm threshold: `0.05 / 24 = 0.0020833333...`;
- bootstrap replicates: **2,000**;
- smallest attainable empirical p-value: `1 / 2001 = 0.0004997501...`.

The empirical p-value resolution is therefore fine enough to satisfy the strictest multiplicity threshold. The gate is arithmetically reachable.

Synthetic calibration across deterministic seeds produced:

- null planted edge: **0 / 8 promotions**;
- moderate planted gross edge `0.0035` with volatility `0.012`: **4 / 8 promotions**;
- strong planted gross edge `0.0060` with volatility `0.008`: **8 / 8 promotions**.

The moderate trials failed for real robustness reasons such as fold consistency, stress profitability, primary lower confidence bound, or year robustness. This is evidence of selectivity, not an impossible gate.

The calibration also proves that ATLAS can recognize truly impossible designs:

- empirical p-value resolution too coarse for multiplicity -> `UNPASSABLE_ARITHMETIC`;
- a complete declared source upper bound below frozen sample minima -> `CAPACITY_UNREACHABLE`;
- a bounded probe below the minimum -> `REACHABLE_CAPACITY_UNPROVEN`, not falsely labeled impossible.

## 3. Research-population coverage

`packages/backtesting/research_population_coverage.py` requires future research to distinguish:

- complete point-in-time eligible market universe;
- complete natural-event source;
- filtered downstream population;
- feasibility/probe-only evidence;
- derived outputs whose grain is not directly comparable to the prior stage.

Severe narrowing is diagnostic rather than automatically disqualifying. It must be visible and causally explained before a negative result is interpreted as evidence that the mechanism has no alpha.

The retained Phase25 production-path reconstruction demonstrates broad technical coverage:

- **1,260 / 1,260** replay sessions;
- approximately **8.92 million** reconstructed discovery-state stock/session rows;
- **23,177** WARM/HOT directional candidates;
- **17,285** market-compatible candidates;
- **15,283** fully route-eligible candidates;
- **10,521** candidates firing at least one incumbent strategy;
- **24,753** development strategy-signal rows at the candidate-by-strategy grain.

Thus the core technical strategies were not tested on a small arbitrary stock sample.

The same audit exposes event-driven compression that deserves explicit explanation. Phase30, for example, had over **1.01 million** development predictor rows across **16,749** tickers but only **3,057** joined development observations. Phase31 went from roughly **2.99 million** authoritative Form-4 transactions to **5,400** predictor events. These may be legitimate mechanism filters, but future experiments must persist deterministic exclusion counts rather than hide the funnel.

See `docs/research_population_coverage_audit.md` for the retained phase-by-phase population review.

## 4. Prospective research-freeze contract

`packages/backtesting/research_gate_freeze.py` is a prospective-only pre-outcome safeguard. Historical experiments are never run back through it to change their accepted result.

A future alpha experiment may be frozen only when all of the following are true:

1. empirical p-value resolution can satisfy the strictest planned multiplicity threshold;
2. source-only capacity evidence proves the declared row/session/instrument minimums are attainable;
3. the complete eligible universe or complete natural-event source is explicitly represented by a valid population-coverage contract;
4. any severe source-to-signal attrition already observed has a frozen causal explanation;
5. transaction-cost assumptions and a positive **after-cost** economic effect target are explicit;
6. mechanism density is declared, so sparse event research is not forced to inherit dense-technical sample rules without justification;
7. the sample/effective-sample rationale is explicit;
8. at least eight deterministic positive-path calibration trials have been run and their detection rate meets the preregistered target;
9. protected outcome reads remain exactly zero before freeze.

Possible dispositions are:

- `READY_TO_FREEZE`;
- `BLOCKED_ARITHMETIC`;
- `BLOCKED_CAPACITY`;
- `BLOCKED_POPULATION_EVIDENCE`;
- `BLOCKED_POWER_PLAN`;
- `BLOCKED_PROTECTED_CONTAMINATION`.

This contract is intentionally designed to prevent both failure modes: a gate that can never say yes, and a weak gate that says yes to noise.

## 5. Historical negative/failure taxonomy

Future reporting must not collapse every unsuccessful experiment into the phrase `no alpha`.

Use these categories where applicable:

- `PERFORMANCE_NEGATIVE`: after-cost development evidence is not positive enough;
- `MULTIPLICITY_FAIL`: raw evidence exists but does not survive the preregistered family correction;
- `ROBUSTNESS_OR_CONCENTRATION_FAIL`: evidence does not persist across folds, years, regimes, instruments, or concentration limits;
- `DEVELOPMENT_CAPACITY_FAIL`: the development population cannot meet the frozen scientific minimums;
- `PROTECTED_CAPACITY_FAIL`: a development finalist exists but the protected source-only population cannot meet frozen protected minimums;
- `SOURCE_INTEGRITY_FAIL`: source semantics/integrity fail before outcome access;
- `PROCESS_OR_VALIDATOR_FAIL`: the experiment cannot be interpreted because the process/validator itself is defective;
- `IMPLEMENTATION_DEFECT_FIXED`: an implementation defect was identified and repaired before the final valid experiment was accepted.

Retained examples:

- **Phase26:** final accepted negative after a genuine impossible predicate was repaired before the valid run; no protected returns opened.
- **Phase27–29:** development evidence did not produce supported survivors; no protected outcome promotion occurred.
- **Phase30:** sparse news candidates included an interesting positive-looking 30-row reversal diagnostic, but the frozen sample/multiplicity/robustness requirements were not satisfied; historical result remains accepted negative.
- **Phase31:** insider candidates had meaningful sample counts but failed frozen diversity/sample/robustness requirements; result remains frozen.
- **Phase32:** a real development finalist, `solvency_distress_short`, reached a protected source-only population of **46 rows / 33 sessions / 40 instruments** against frozen minimums **50 / 20 / 20**; protected returns remained unopened. This is a protected-capacity result, not demonstrated negative protected performance.
- **FINRA short-interest:** source-only protected capacity was **257 rows / 26 sessions / 211 instruments** against minimums **300 / 16 / 200**; the process stopped before outcome interpretation.
- **SEC earnings innovation v1:** source-integrity contradictions reproduced on refetch and the frozen zero-tolerance source rule stopped the experiment before market outcomes were opened.

## 6. Strategy and downstream positive-path audit

### Strategy registry

The production strategy registry is substantive. It contains deterministic long/short trend, momentum, breakout/breakdown, and pullback families using the expected technical feature set. The research system is not merely testing placeholder strategy names.

### Research -> Phase13 deterministic case/risk

The Phase13 case engine sets `phase14_review_ready` when and only when:

`research_complete AND geometry AVAILABLE AND portfolio risk ADMISSIBLE`.

Existing unit tests prove positive long and short geometry paths and a positive portfolio-risk admission path. They also prove wrong geometry and excessive risk fail closed.

News is explicitly supporting-only and cannot manufacture or veto the research candidate. Options are supporting-only at this phase; equity remains primary until an options relative-value model is scientifically accepted.

### Phase14 AI audit

Phase14 consumes only review-ready deterministic cases. Its records explicitly state that the AI disposition is not a trade signal, the AI did not mutate the deterministic case, and the AI did not create an order.

This is an authority boundary, not an automatic trading veto.

### Phase15 execution construction

Existing Phase15 tests prove that a valid deterministic case can produce a long or short execution intent from a fresh real-time quote, preserve stop/target geometry, and build a protective bracket plan. Stale/delayed/wrong-symbol/non-regular quotes fail closed. LIVE remains intentionally disabled.

### Phase20 orchestration

The implemented Phase20 orchestrator is in `packages/jobs/orchestrator.py`. It is intentionally provider-free and broker-write-free SHADOW orchestration. Its tests prove deterministic scheduling, idempotent resume, bounded retry, dependency blocking, lease collision handling, interruption fail-closed behavior, and manifest conflict detection.

The zero-byte `apps/orchestrator/` shell is therefore an application-entrypoint/integration scaffold, not evidence that orchestration logic is absent. It should later be wired to the accepted package implementation or retired; this audit does not duplicate the orchestration logic into that shell.

### Phase21 centralized PAPER authority

Phase21 is the centralized PAPER mutation boundary. Existing tests prove a genuine positive authority path for **both Webull and Alpaca**:

- an exact broker-bound execution scope is constructed;
- explicit authority is issued only with the exact confirmation contract;
- `ExecutionEngine.attempt(...)` performs exactly one in-memory PAPER-provider submission in the positive test;
- missing, false, malformed, wrong-broker, wrong-environment, wrong-scope, wrong-policy, wrong-contract, or wrong-operation authority fails before submit;
- an idempotently existing order is reused without a second mutation;
- SHADOW remains write-free;
- LIVE remains blocked.

This proves that the downstream PAPER authority is reachable rather than an `always reject` dead end.

## 7. Current implementation gaps versus intentional blocks

**Implemented and substantively tested:** production-style discovery/routing research lineage, phase-specific research machinery, deterministic Phase13 case/risk, Phase14 AI audit boundary, Phase15 execution construction, Phase20 restart-safe SHADOW orchestration, Phase21 centralized PAPER authority, broker switching/reconciliation primitives, and control-plane foundations.

**Technical debt / partial scaffolding:** generic backtesting stubs (`engine.py`, `simulator.py`, `validation.py`, `walk_forward.py`), several decomposed risk stubs, some execution helper stubs, and the empty `apps/orchestrator/` entrypoint shell. These should be consolidated when the roadmap reaches production integration; they are not the reason alpha experiments failed.

**Intentional blocks:** LIVE execution remains disabled; automatic broker failover remains disabled; Phase33 signal-to-trade promotion remains blocked because supported alpha is currently zero.

## 8. Required future research cadence

For every new alpha mechanism, use:

`SOURCE FEASIBILITY`

-> `COMPLETE/BOUNDED CAPACITY ANALYSIS`

-> `POPULATION COVERAGE / ATTRITION EXPLANATION`

-> `ARITHMETIC + POSITIVE-PATH POWER CALIBRATION`

-> `FREEZE SCIENTIFIC CONTRACT`

-> `DEVELOPMENT OUTCOMES`

-> `MULTIPLICITY + ROBUSTNESS`

-> `FINALIST`

-> `FINALIST-ONLY PROTECTED SOURCE CAPACITY`

-> `PROTECTED OUTCOME` only if every prior condition passes.

Sample floors must be justified by mechanism density, dependence/effective sample size, desired economic edge, transaction costs, and target detection probability. A round number inherited from a dense technical experiment is not by itself a scientific justification for a sparse event experiment.

## 9. Final audit interpretation

The correct conclusion is **not** “ATLAS has tried everything and nothing works.”

The retained evidence is a mixture of genuine negative development results, robustness/multiplicity failures, sparse-sample limitations, protected-source capacity failures, and source-integrity failures. Several of the recent source failures stopped before outcome access and therefore say nothing about profitability.

The system should remain selective: discovery and SHADOW/research observations may be numerous, validated actionable alerts should be fewer, and PAPER/LIVE authority should be narrower still. What this audit protects against is a validator or population funnel that makes success impossible by construction.

Supported alpha remains **0** at audit close. Phase33 therefore remains intentionally blocked for now, but the route to a future supported strategy and authorized PAPER execution is demonstrably reachable.
