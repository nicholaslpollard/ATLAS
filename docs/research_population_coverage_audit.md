# Research Population Coverage Audit

**Audit branch:** `research-gate-calibration-system-audit`  
**Purpose:** prove what population each ATLAS alpha experiment actually sees before interpreting a negative result as evidence of absent alpha.  
**Historical-result rule:** this audit does not alter, rescue, retune, or relabel any frozen Phase25–32 result and does not authorize protected-return reads.

## 1. Why this audit exists

A valid strategy can appear to have no edge if the research pipeline silently narrows a broad source universe to a tiny or unrepresentative subset before the strategy is evaluated. Conversely, event-driven research should not be forced to include stocks that never experienced the event under study.

ATLAS therefore needs an explicit source-to-signal population contract for every future alpha experiment.

The required distinction is:

- **broad technical/cross-sectional research:** begin from the complete point-in-time eligible market universe for the research scope;
- **natural event research:** begin from the complete admissible event source for the research scope, such as all qualifying Form 4, 8-K, news, earnings, or short-interest observations;
- **source-feasibility probes:** may establish source semantics/capacity evidence, but must remain labeled `PROBE_ONLY` and may not be presented as complete research coverage unless an independent upper-bound proof exists.

A severe population narrowing is not automatically a defect. It is a mandatory diagnostic that requires a causal explanation.

## 2. Machine-readable safeguard

`packages/backtesting/research_population_coverage.py` adds a reusable coverage contract with these source types:

- `FULL_ELIGIBLE_UNIVERSE`;
- `NATURAL_EVENT_SOURCE`;
- `FILTERED_POPULATION`;
- `PROBE_ONLY`;
- `DERIVED_NONCOMPARABLE`.

The validator requires population stages to state:

- exact row count;
- session count when meaningful;
- unique instrument count when meaningful;
- population grain;
- whether the stage is complete or partial;
- whether its rows are directly comparable to the prior stage;
- evidence source.

Same-grain filtered stages may not silently expand. A stage that changes grain, for example candidate rows to candidate×strategy rows, must declare itself noncomparable so a misleading retention percentage is not calculated.

The default severe-attrition diagnostic threshold is **5% row retention**. Falling below this threshold does not fail the scientific result by itself; it marks the transition for explicit explanation before a negative result is interpreted.

The research-gate calibration validator now also proves that:

1. a complete broad-universe funnel is recognized as complete;
2. severe narrowing is surfaced rather than hidden;
3. a probe cannot claim complete research coverage;
4. a same-grain filtered population cannot expand without invalidating the coverage contract.

## 3. Existing production-path evidence

### Phase25 production discovery/routing funnel

Phase25 is the strongest existing broad-universe lineage proof because it reconstructed production discovery chronologically across every exact replay session.

Accepted evidence:

- exact replay sessions: **1,260 / 1,260**;
- one accepted reference probe contained **11,027** point-in-time instruments on that session;
- cumulative effective discovery-state rows across the replay:
  - HOT: **16,517**;
  - WARM: **16,731**;
  - WATCH: **1,554,664**;
  - NORMAL: **7,331,390**;
  - total: **8,919,302** state rows;
- WARM/HOT directional population: **23,177** candidate rows;
- market-compatible candidates: **17,285**;
- fully route-eligible candidates: **15,283**;
- candidates with at least one incumbent strategy fire: **10,521**;
- development rule-fired signal rows: **24,753**.

The `24,753` signal rows are not directly comparable to the `10,521` candidate count because one candidate can fire more than one strategy. They are therefore a different grain.

Useful comparable retention diagnostics:

- WARM/HOT directional as a share of all reconstructed discovery-state rows: approximately **0.260%**;
- market-compatible from WARM/HOT directional: approximately **74.6%**;
- fully route-eligible from market-compatible: approximately **88.4%**;
- at least one incumbent fire from fully route-eligible: approximately **68.8%**.

The very large first narrowing is expected to be caused by the deliberate discovery funnel, but under the new audit contract it is still something ATLAS should show explicitly rather than leave implicit.

Sources: `docs/phase25_gate6_discovery_reconstruction.md`, `docs/phase25_gate7_route_context.md`, and `docs/phase25_remaining_evidence.md`.

### Phase26 production-path-native alpha library

Phase26 used the accepted Phase25 production-path-native context rather than a random stock sample.

Accepted target evidence:

- development usable observations: **21,483**;
- protected predictor observations: **1,096**;
- selection survivors: **0**;
- protected returns read: **0**.

This is broad production-path evidence, but the existing closeout does not summarize every source-to-signal unique-instrument/session count needed by the new coverage contract. The scientific result remains frozen and valid under its accepted contract; the missing funnel summary is an **observability improvement**, not permission to reinterpret Phase26.

Source: `docs/phase26_closeout.md`.

### Phase27 cross-sectional ranking

Accepted target evidence:

- development model rows: **18,111**;
- protected predictor rows: **920**;
- selection survivors: **0**;
- protected returns read: **0**.

Phase27 inherits its focal population from the production-path research lineage, but the closeout does not expose a complete eligible→model→signal instrument/session funnel. This is a retrospective observability gap only.

Source: `docs/phase27_closeout.md`.

### Phase28 cross-stock network alpha

Accepted target evidence:

- development network rows: **14,466**;
- protected network predictor rows: **741**;
- selection survivors: **0**;
- protected returns read: **0**.

As with Phase27, the closeout records the final analytical population but not every source-to-network attrition stage. This should be explicit in future cross-stock research.

Source: `docs/phase28_closeout.md`.

### Phase29 relative-value/statistical-arbitrage confirmation

Phase29 explicitly begins with the Phase26 production-path-native focal population and then requires a complete 62-close safe-history window plus enough complete peers for both frozen relative-value mechanisms.

The scientific contract clearly defines this complete-case narrowing, but the retained phase document does not itself summarize the final source→complete-case→tail counts in the same compact funnel form now required by this audit.

Audit classification: **coverage logic explicit; compact retained funnel observability incomplete**. Do not infer missing counts from preregistration text. If retained immutable target artifacts are available, the audit should reconstruct and report those counts without rerunning or changing the historical experiment.

Source: `docs/phase29_relative_value_statistical_arbitrage.md`.

## 4. Event-driven population evidence

### Phase30 public-news alpha

Phase30 has unusually clear source-population evidence:

- complete historical acquisition: **775,164 articles**;
- ticker links scanned: **1,917,356**;
- development predictor rows: **1,012,022** across **16,749 tickers**;
- protected predictor rows: **23,183** across **4,828 tickers**;
- joined development population: **3,057 rows**, **1,736 tickers**, **953 sessions**.

The development join retained only about **0.302%** of development predictor rows. This is a major funnel bottleneck and must be made explicit.

It is not automatically evidence of a bug: Phase30 intentionally required news events to intersect the production-path candidate population and then applied frozen session/direction/tail/reaction rules. But future event studies must break this transition down by exclusion reason so ATLAS can distinguish legitimate economic filtering from accidental coverage loss.

Frozen selection samples were:

- aligned continuation LONG: **171 rows / 112 sessions**;
- aligned continuation SHORT: **8 / 6**;
- counterreaction reversal LONG: **30 / 28**;
- counterreaction reversal SHORT: **1 / 1**.

This explains why a positive-looking 30-row reversal diagnostic could not establish support under the frozen 750-row/250-session gate. The historical Phase30 result remains `ACCEPTED_NEGATIVE`; the lesson is prospective gate/population design, not post-hoc rescue.

Source: `docs/phase30_event_driven_public_information_alpha.md`.

### Phase31 SEC Form-4 insider alpha

Phase31 also has a complete natural-event source:

- raw Form-4 transaction rows: **2,993,648**;
- authoritative rows after deterministic source-quality quarantine: **2,992,608**;
- quarantined rows: **1,040**;
- development predictor rows: **5,400**;
- usable outcome rows: **5,371**.

The frozen predictor population is only about **0.180%** of authoritative transaction rows. That may be fully justified by the preregistered transaction-type, role, value, timing, identity, and event-construction rules, but the new audit requires those exclusions to be quantified by reason rather than leaving the reduction implicit.

Once predictors existed, outcome-path availability was very high: **5,371 / 5,400 = 99.46%** usable.

Frozen candidate samples:

- open-market purchase LONG: **1,516 rows / 641 sessions / 230 tickers**;
- clustered open-market purchase LONG: **638 / 376 / 136**;
- open-market sale SHORT: **2,355 / 785 / 216**;
- clustered open-market sale SHORT: **1,281 / 645 / 131**.

All four failed the frozen 250-unique-ticker requirement; one also failed the 750-row requirement. The result remains frozen `ACCEPTED_NEGATIVE`.

Sources: `docs/phase31_full_historical_acquisition.md` and `docs/phase31_closeout.md`.

### Phase32 SEC 8-K material-event alpha

Phase32 reached a real development finalist, `solvency_distress_short`, proving that the development path was capable of promoting evidence.

The complete frozen protected source-only finalist population was:

- **46** event rows;
- **33** signal sessions;
- **40** unique instruments.

Frozen protected minimums were **50 / 20 / 20**. Thus the event-row requirement missed by only four rows while sessions and instruments passed. Protected returns remained unread.

This is not a performance-negative result. It is a source-capacity/sample-gate result and is exactly why future contracts must prove capacity before freezing the final minimums.

Source: `docs/phase32_closeout.md`.

## 5. Required funnel for every future alpha experiment

Before development outcomes are interpreted, the retained report should include the following, at the correct grain:

`complete eligible universe or natural event source`

→ `source-quality admissible population`

→ `PIT identity/history available`

→ `feature/predictor complete`

→ `production discovery/routing intersection` when applicable

→ `mechanism-specific complete case`

→ `candidate/session/direction eligible`

→ `signal/tail fired`

→ `outcome path available`

→ `selection sample`

→ `internal sample`

→ `finalist-only protected source sample`

For every transition ATLAS should persist:

- source and destination row counts;
- unique instruments;
- unique sessions;
- exact row grain;
- retention ratio when comparable;
- exclusion counts by deterministic reason;
- whether the source is complete, bounded upper-limit evidence, or only a probe;
- whether the transition is expected by the scientific mechanism;
- whether a severe narrowing requires investigation before a negative conclusion is interpreted.

## 6. Prospective freeze rule

The preferred future sequence is now:

`SOURCE FEASIBILITY`

→ `COMPLETE/BOUNDED POPULATION CENSUS`

→ `UNIVERSE-TO-SIGNAL COVERAGE AUDIT`

→ `GATE REACHABILITY / POWER CHECK`

→ `FREEZE SCIENTIFIC CONTRACT`

→ `DEVELOPMENT OUTCOMES`

→ `MULTIPLICITY / ROBUSTNESS`

→ `FINALIST`

→ `PROTECTED OUTCOME`

This does not require every strategy to see every stock. It requires ATLAS to prove why each stock/event entered or left the research population.

## 7. Current conclusion

There is no evidence that Phases26–28 were based on a small arbitrary sample; their source population comes from the reconstructed production discovery path. Phase30 and Phase31 show very large event-source-to-final-study narrowing, which is not automatically wrong but is now an explicit audit target. Phase32 demonstrates a different problem: a genuine development finalist encountered an insufficient protected source population.

The new coverage contract prevents these distinct cases from being collapsed into the same vague label of “no alpha.”

No protected outcome was opened and no broker/order/PAPER/LIVE authority is changed by this audit.
