# Phase 21 — Unified Paper Execution Authority and Operational Binding

**State: VALIDATED / MERGE PENDING. Last synchronized: 2026-08-24.**

Phase 21 closes an authority gap in the accepted execution stack without rebuilding broker execution. Its purpose is to ensure that every **new real PAPER provider submit** crosses one centralized, default-deny, run-scoped authority boundary while preserving accepted Phase 15 execution semantics, separate Phase 18 certification authority, Phase 20 orchestration limits, browser non-authority, and hard-disabled LIVE execution.

## 1. Upstream binding

Phase 21 was defined from the post-Phase20 `main` baseline:

`4afe8e0a5238b176edd47eb6e70359ccff6d65b1`

Accepted Phase 20 remains merged at:

`3b34bc700f8a0241ca5716c6d18bcb89f0d45620`

Phase 21 changes execution authority only. It does not replace accepted Phase 13 risk, Phase 14 AI-audit, Phase 15 broker-neutral execution, Phase 18 certification, Phase 19 observability, or Phase 20 local orchestration contracts.

## 2. Locked policy

Policy contract:

`phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny`

Validated policy fingerprint:

`0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`

Authority contract:

`phase21-paper-execution-authority-v1-broker-paper-run-scoped`

Locked invariants:

- PAPER provider submission is **disabled by default**.
- Webull PAPER and Alpaca PAPER use the same centralized authority contract.
- Authority must exactly match broker, PAPER environment, operation, policy fingerprint, deterministic execution scope, explicit authorization flag, and exact confirmation text.
- Missing, false, malformed, stale, or mismatched authority fails closed before a new provider submit.
- SHADOW remains authority-free because it performs no real provider mutation.
- An exact existing deterministic client-order ID may be reconciled/reused without new mutation authority because no new provider submit occurs.
- LIVE remains disabled.
- Automatic cross-broker failover remains disabled.
- The browser/control plane cannot acquire Phase 21 execution authority.
- Phase 20 external mutation-stage registration remains prohibited.
- Uncertain provider mutation is never blindly retried.
- Phase 21 implementation/validation performs zero real provider calls or writes.

## 3. Deterministic authority scope

Phase 21 uses deterministic `p21-...` execution-scope identifiers and exact confirmation text:

`AUTHORIZE_ATLAS_PAPER_SUBMIT:<broker>:<p21-scope>`

The confirmation text is authorization input and is not emitted in public authority metadata.

### 3.1 Phase 15 operational PAPER scope

`derive_phase15_paper_execution_scope_id(...)` binds:

- Phase 21 policy fingerprint;
- scope kind `PHASE15_OPERATIONAL_PAPER_RUN`;
- explicit `as_of_date`;
- accepted Phase 15 input fingerprint;
- accepted Phase 15 policy fingerprint;
- selected broker;
- PAPER environment.

`Phase15ExecutionRunEngine.prepare_paper_execution_challenge(...)` resolves accepted local input and returns this challenge without initializing a broker or live quote provider.

For a nonzero PAPER run, Phase 15 validates exact Phase 21 authority **before** `Phase15LiveQuoteResolver` initialization. A missing or mismatched authority therefore fails before broker/provider submission and before the Phase 15 live-quote path is initialized.

### 3.2 Phase 18 standard certification scope

`derive_phase18_paper_execution_scope_id(intent)` binds the compatibility scope to the exact Phase 18 PAPER execution intent, accepted Phase 13/14 lineage, instrument identity, date, broker, and environment.

The original Phase 18 explicit mutation authorization remains the required outer authority. Only after that authorization passes does `phase18_lifecycle.py` construct the narrow Phase 21 compatibility authority needed by the centralized submit seam.

### 3.3 Phase 18 operational-validation scope

`derive_phase18_operational_validation_scope_id(plan, broker=...)` binds:

- Phase 21 policy fingerprint;
- scope kind `PHASE18_OPERATIONAL_VALIDATION_PAPER_SUBMIT`;
- broker and PAPER environment;
- deterministic client-order ID;
- validation intent ID;
- ticker;
- a stable fingerprint of the complete one-share certification `BrokerOrderPlan`.

This preserves the specialized Phase 18 validation-plan checks instead of constructing a synthetic strategy `ExecutionIntent`.

## 4. Central provider-submit seam

The only raw `adapter.submit(plan)` call under `packages/` is in:

`packages/execution/engine.py`

`ExecutionEngine.submit_authorized_plan(...)` is the centralized mutation seam for an already-validated order plan:

- PAPER requires exact Phase 21 authority immediately before raw submit;
- LIVE is rejected;
- SHADOW remains non-provider-mutating;
- `BrokerSubmissionUncertain` propagates so callers stop and reconcile;
- deterministic Phase 15 idempotent reuse happens before the new-submit path.

`ExecutionEngine.attempt(...)` now uses this same method, so routine Phase 15 PAPER execution and specialized Phase 18 certification cannot maintain separate raw submit bypasses.

The independent Phase 21 validator AST-scans `packages/**/*.py` and requires:

- raw submit path exactly `packages/execution/engine.py`;
- raw `adapter.submit` count exactly **1**;
- Phase 21 authority check before that submit.

## 5. Phase 18 composition remains separate

Phase 21 does **not** replace or weaken Phase 18 authorization.

For both accepted Phase 18 submission paths:

1. original `require_phase18_mutation_authorization(...)` passes first;
2. all existing broker/PAPER/plan/reconciliation/idempotency/preflight checks remain in force;
3. an exact narrow Phase 21 compatibility challenge is derived;
4. compatibility authority is constructed only because the original Phase 18 explicit authority already passed;
5. submit crosses the centralized Phase 21 seam.

Phase 18 cancellation remains governed by the accepted Phase 18 lifecycle. Phase 21 centralizes **new provider SUBMIT** authority; it is not a broad provider-mutation switch and does not silently grant cleanup, flatten, broker-switch, or LIVE authority.

## 6. Phase 15 lineage compatibility

The first Phase 21 implementation added a `phase21_execution_scope_id` field to the Phase 15 source-fingerprint payload unconditionally. That would have created unrelated source-lineage drift for SHADOW/no-case runs.

The validated implementation adds that source-fingerprint field **only when the selected environment is PAPER**. SHADOW and no-case source-payload shape therefore retains its pre-Phase21 semantics. Phase 21 audit metadata may still appear in the run manifest without silently changing non-PAPER source lineage.

## 7. Defect discovered by independent validation

The first Phase 21 CI correctly failed before pytest because the new validator found a second raw provider-write seam in:

`packages/execution/phase18_operational_validation.py`

The failure was:

`adapter.submit mutation seam is not centralized`

This was a real accepted-code bypass, not a validator false positive. The validator was not weakened. The operational-validation path was refactored through the central engine seam and its authority was bound to the exact certification plan.

## 8. Implementation evidence

Validated implementation head:

`d3599f3a184142de4ac5f03b58fc355f0bb11001`

Implementation CI:

`32781962354`

Cross-platform results:

- Ubuntu: **964 passed in 15.42s**;
- Windows: **964 passed in 24.52s**;
- every validator through Phase 21 PASS on both platforms;
- dependency lock PASS;
- secret hygiene PASS;
- ATLAS Doctor PASS;
- browser JavaScript syntax PASS;
- exact 33-feature self-test parity retained.

Phase 21 validator evidence on both platforms:

- policy fingerprint exact;
- `paper_provider_submit_default=false`;
- `live_execution=false`;
- `automatic_broker_failover=false`;
- `adapter_submit_seam=packages/execution/engine.py`;
- `raw_adapter_submit_count=1`;
- `phase18_operational_submit=centralized`;
- provider calls 0;
- provider writes 0;
- broker writes 0.

No real target-provider mutation is required to validate Phase 21 itself because Phase 18 already supplied accepted real Webull sandbox mutation/reconciliation evidence and this phase changes the internal authorization boundary rather than provider behavior.

## 9. Negative-path evidence

Focused tests prove:

- exact Webull PAPER authority submits once;
- exact Alpaca PAPER authority submits once;
- missing authority submits zero times;
- explicit false authority submits zero times;
- broker/environment/scope/confirmation/policy/contract/operation mismatch submits zero times;
- exact existing deterministic order reuse performs no second submit and requires no new mutation authority;
- SHADOW remains authority-free;
- LIVE remains blocked;
- Phase 18 operational scope changes if broker or exact plan changes;
- central plan submission rejects scope mismatch before the raw adapter submit;
- public authority metadata omits confirmation text.

## 10. Non-goals

Phase 21 does not:

- enable LIVE execution;
- enable automatic broker failover;
- let the browser submit trades;
- let Phase 20 register external mutation work;
- add autonomous scheduling;
- promote PostgreSQL as a runtime prerequisite;
- change strategy support, ML model authority, Phase 13 risk limits, Phase 14 AI authority, or execution geometry;
- repeat the Phase 18 real provider mutation merely for reconfirmation;
- grant cleanup/flatten authority.

## 11. Acceptance boundary

The implementation and first cross-platform evidence boundary are green. This document and the living status/roadmap/README/phase-flow files are being synchronized before final exact-head closeout CI and merge.

Phase 21 may be marked ACCEPTED only after the documentation head itself passes the full Ubuntu/Windows workflow with every validator through Phase 21 green. After acceptance, PR #22 may be marked ready and merged to `main`.

## 12. Next-phase direction

After Phase 21 merges, the next phase must be selected by auditing the remaining gap to routine end-to-end Webull-primary PAPER operation. The likely high-value area is the operator-facing run binding that safely carries accepted Phase 13/14 evidence through Phase 15 challenge/authority, PAPER execution/reconciliation, and Phase 19 outcome/observability artifacts.

That next phase must be defined from actual merged code and roadmap evidence. Scheduler/PostgreSQL work must not be selected merely because infrastructure remains available to build, and no provider mutation may be inferred without its explicit authority contract.
