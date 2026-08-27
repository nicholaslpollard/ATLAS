# Phase 28 End-to-End Anti-Workaround Audit

**Contract:** `phase28-end-to-end-anti-workaround-audit-v1`

**Disposition:** PASS

## Purpose

This audit is the required Phase 28 closeout review for workaround debt, duplicate authority, hidden protected reads, post-result tuning, and temporary repair paths. It applies the ATLAS root-cause rule: a failing check must be traced to and corrected at the owning layer; a bypass, relaxed validator, parallel authority path, fallback whose purpose is merely to produce PASS, or post-result threshold change is not acceptable.

Phase 28 produced valid negative alpha evidence. The audit therefore asks whether that negative result came from the preregistered cross-stock network path and whether any Phase 28 research component can accidentally become a runtime trading-authority shortcut.

## Target evidence reviewed

Exact pre-target branch head:

`2eea81855803faddbfc7d07109d3af02a799f430`

Frozen Phase 28 policy fingerprint:

`0f15966f61a0baf52513cd46dc4fa8492c98e7dc8cf9ed3d551c2ebc955adea5`

Target-machine result:

- development network rows: **14,466**;
- protected network predictor rows: **741**;
- selection survivors: **0**;
- selection winners: **0**;
- internal-validation finalists: **0**;
- protected-confirmed supported candidates: **0**;
- protected candidate rows queried: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- independent validation: **PASS**;
- provider/broker/order/PAPER/LIVE activity: **0**.

## Critical chain reviewed

`accepted Phase26 exact-PIT observations -> Phase28 observation-time peer universe -> canonical 1d return history -> cross-sectional common-move residualization -> asymmetric t-1 lead-lag network -> frozen relational signals -> fixed 20% directional tails -> chronological selection -> global Holm -> internal validation -> protected-blindness audit -> zero-finalist skip or immutable finalist-only protected read plan -> independent reconstruction/reconciliation -> historical support overlay`

The existing runtime authority chain was also rechecked:

`discovery/promotion -> portfolio/risk -> execution engine -> broker adapter -> operator/browser control plane`

## Findings

### 1. Phase 28 is research-only and does not modify runtime trading authority

The branch changes are bounded to Phase 28 backtesting/research modules, tests, scripts, documentation, and the CI workflow. No discovery, portfolio, risk, execution, broker, operations, or control-plane implementation was modified by Phase 28.

Phase 28 modules are not imported by the runtime trading-authority packages. A research artifact cannot therefore become an execution shortcut merely by existing.

### 2. No provider, broker, order, PAPER, LIVE, or automatic-failover authority was introduced

All Phase 28 external-authority constants remain zero and automatic broker failover remains disabled. The target run reported zero provider/broker/order/PAPER/LIVE activity. The historical support overlay explicitly grants no PAPER or LIVE authority.

### 3. The information source materially changed rather than retuning the failed self-feature families

Phase 28 uses cross-stock relational information derived from canonical daily returns and exact PIT production candidate identities. It does not add another threshold sweep over Phase 26 deterministic self-features or another generic learner over the Phase 27 same-stock predictor block.

The frozen network settings remained 60 lag pairs, minimum 50 valid pairs, top 3 positive-asymmetric leaders, minimum 2 leaders, and a 20% fixed score tail. These were not altered after target performance was observed.

### 4. Network estimation is observation-time and leader selection ends at t-1

Leader relationships are estimated using residual history ending at `t-1`. Current finalized session `t` residuals may enter the four preregistered signal formulas only after the network is fixed. Future outcomes are not used to choose peers, leaders, weights, signals, or score tails.

### 5. Exact PIT identity and split boundaries remain authoritative

The Phase 28 population is rooted in accepted Phase 26 exact-PIT observations. Network history is restricted to each row's safe identity interval. Split crossings in the required history window censor the affected ticker rather than bridging ticker text across identity discontinuities.

No current-only relationship mapping, sector membership, customer/supplier graph, ownership data, or text-derived relationship was projected backward to create historical peers.

### 6. All eight hypotheses use one frozen complete-case population

Every eligible Phase 28 row requires all four relational signals to be finite. This prevents candidate-specific missing-data populations from becoming an implicit tuning path. LONG and SHORT remain separate direction hypotheses, and all eight candidate/direction hypotheses participate in one global Holm-Bonferroni family.

### 7. No runner-up, near-miss, or “best available” substitution exists

At most one selection winner per direction may advance. Runner-up substitution is disabled. If a winner fails internal validation, another same-direction candidate cannot be promoted in its place. The target result had zero selection survivors, so no winner or finalist existed to reinterpret.

### 8. Protected evidence remained fully unopened

The target result had zero internal finalists. Confirmation therefore exited through `SKIPPED_ZERO_FINALISTS` with:

- protected candidate rows queried = 0;
- protected return rows read = 0;
- no protected read plan;
- no protected scored-prediction artifact;
- no protected score-signal artifact;
- no protected outcome-signal artifact;
- `protected_holdout_consumed = False`.

This preserves the master holdout as genuinely outcome-unopened evidence. It is not treated as support and cannot be described as “passed protected validation.”

### 9. If finalists had existed, the protected read boundary was immutable before outcomes

The confirmation implementation freezes exact finalist score-tail query keys into a read plan before invoking the future-outcome join. Outcome reads are restricted to those frozen keys. This is resumability with immutable evidence, not a fallback analytical authority path.

### 10. Independent validation reconstructs network evidence rather than trusting Phase 28 helpers

The independent validator does not import the Phase 28 network helper module. It independently reconstructs a deterministic sample of residuals, asymmetric leader edges, weights, and four signal values from Phase 26 identities plus canonical daily bars, then separately reconciles fixed-tail keys, economics, Holm decisions, finalist relationships, protected relationships, and support authority.

The target run returned independent validation `PASS`.

### 11. No post-result tuning or hidden model-search loop was added

Phase 28 contains no hyperparameter/model tuning loop. The candidate library remained exactly four raw signal families × LONG/SHORT. No network window, peer threshold, leader count, score-tail fraction, outcome horizon, cost assumption, confidence level, multiplicity rule, or minimum-evidence threshold was changed after the target result.

### 12. Resumability is evidence-preserving, not a workaround

The cumulative runner may reuse an already-passing artifact with the same contract and policy fingerprint instead of recomputing it. Protected confirmation may resume only an exact previously frozen read plan. These mechanisms preserve deterministic evidence and do not create alternate selection logic or weaker acceptance criteria.

## Classification of findings

1. **Legitimate resilience/provenance:** immutable passing-artifact reuse; immutable protected read-plan resumability; persisted hashes and contract fingerprints.
2. **Simplification debt:** none found that affects Phase 28 authority or scientific interpretation.
3. **Root-cause defects:** none found in the accepted target path.
4. **Obsolete bypasses:** none found in the Phase 28 critical chain.

## Closeout conclusion

No acceptance-blocking workaround, duplicate trading authority, hidden protected read, post-result retuning path, runner-up substitution path, identity shortcut, or weakened-validator path was found.

The scientifically correct result remains negative: Phase 28 executed the frozen cross-stock lead-lag/residual-network experiment correctly, but none of the eight hypotheses earned historical analytical support. The protected holdout remains unconsumed. Signal-to-trade construction remains blocked until a separately preregistered alpha phase earns accepted support.
