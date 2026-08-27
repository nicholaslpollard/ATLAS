# ATLAS Phase Execution Flow

**Normative development-flow contract. Last synchronized: 2026-08-26.**

## 1. Core rule

ATLAS advances by explicit numbered phases:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Use the largest safe coherent batch. No credential, endpoint, connected account, local file, adapter, passing test, or prior success silently expands provider, broker, strategy-support, automation, or LIVE authority.

## 2. Phase states

- PLANNED
- STACKED_PREP
- ACTIVE
- WAITING_EXTERNAL
- BLOCKED
- VALIDATED / MERGE PENDING
- ACCEPTED
- MERGED

Unnumbered maintenance may occur between merged phases only when it changes no numbered-phase authority; it still requires appropriate validation/documentation.

## 3. Required definition

Before substantive implementation, state:

1. number/name;
2. purpose;
3. upstream binding;
4. scope;
5. non-goals;
6. authority boundary;
7. dependencies;
8. deliverables;
9. validation/acceptance criteria;
10. target/external evidence requirements;
11. uncertainty/failure behavior;
12. documentation to synchronize.

Research phases that select models/strategies/thresholds preregister search space, metrics, dependence handling, multiplicity, temporal validation, costs/stress, and protected-evidence boundary before final/protected evidence is read.

## 4. Batch-first package

Normal coherent package:

`implementation + targeted tests + independent validator + CLI/orchestration as applicable + documentation/status`

Focused tests do not replace final regression/CI. Do not run full CI after every tiny edit merely for ceremony. Fix correctness/security/data/authority defects before stacking more work. Never weaken evidence/risk/authority gates to create activity.

When several adjacent research gates are local/read-only and their thresholds can be preregistered together, prefer one cumulative implementation + CI + target run over repeated operator handoffs. Negative results should flow through the full preregistered batch rather than stop the software path.

## 5. Validation ladder

1. syntax/static/compile as useful;
2. focused unit/contract tests;
3. independent validator;
4. full regression at evidence boundary;
5. Ubuntu + Windows CI;
6. target-machine/provider evidence only when CI/mocks cannot establish the required fact;
7. reconciliation/audit for real mutation or authority-changing work.

Target-machine evidence is scarce and should not be repeated without a relevant code/data change.

## 6. Provider/target rules

- Exact authority only for the declared provider/broker class.
- Unknown/uncertain state fails closed.
- No blind mutation retry.
- No automatic broker failover.
- Cleanup/flatten authority is separate when specified.
- PAPER never implies LIVE.
- Provider-free prepare should inventory missing read classes before external reads.
- Read-only provider commands may use the explicit CLI subcommand itself as authorization when the phase contract says so; mutation/trading/destructive actions retain stronger confirmation boundaries.
- Entitlement/session gaps are surfaced, never hidden.
- Partial failed analytical output does not become accepted state merely because it is newer.
- Zero cases/promotions/selections/finalists/provider calls are valid accepted outcomes when they follow the locked evidence path.

## 7. Research/protected-evidence rules

- Candidate/search space and selection rules are frozen before protected evidence.
- Selection and protected/final evidence remain logically and, where practical, physically separated.
- Selection locks are written before internal/protected validation when required.
- Losing alternatives are not revisited after internal/protected results unless a new separately preregistered phase is started.
- Descriptive post-run forensics may explain failure but cannot retroactively change thresholds or support.
- If no candidate earns protected-evidence access, do not open the protected set.
- A population/source mismatch discovered by evidence is a research limitation to correct in the next preregistered phase, not authority to impute missing rows or relax gates.

## 8. Acceptance and merge

A phase is ACCEPTED only when required implementation, focused tests, independent validator, full CI, target evidence, negative/uncertainty paths, and documentation are complete with no unresolved blocker.

After acceptance:

1. mark PR ready;
2. merge the exact tested/documented head;
3. verify authoritative `main`;
4. synchronize living docs to record the merge SHA;
5. verify the post-merge no-authority handoff head as appropriate;
6. define/lock the next numbered phase before substantive implementation.

## 9. Current application — Phase25 validated / merge pending

- Phases 1–24 ACCEPTED / MERGED.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 PR: #27.
- Phase25 target-tested code head: `302bf6db5d807884f3b74cda049fc95864c5a194`.
- Exact-head CI `32981080421`: Ubuntu/Windows SUCCESS through Gate11 + full regression.
- Phase25 disposition: **NO SUPPORT REPLACEMENT — DEVELOPMENT ROBUSTNESS FAILED**.

Phase25 evidence:

1. Gate0–5 established exact PIT reference feasibility, active-only equivalence, entitlement, and 1,253-session historical active-reference acquisition.
2. Gate6 reconstructed 1,260 Phase7/discovery sessions and produced 23,177 WARM/HOT directional cases with one bounded reconciliation event and independent PASS.
3. Gate7 reconstructed exact PIT market/ticker route context: 15,283 fully route-eligible candidates and 61,132 eligible strategy-route decisions.
4. Gates8–11 were preregistered/implemented together and run cumulatively.
5. Gate8 matched 43,456/57,160 route rows to the legacy research source, produced 24,753 incumbent signal rows, and found every non-empty incumbent negative at 10 bps and worse than broad comparator.
6. Gate9 selected 0 strategies; all eight failed core chronology/mean/median/positive-rate/LCB/stress/year/regime gates.
7. Gate10 read zero protected evidence because there were zero finalists.
8. Gate11 verdict: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`.
9. Phase11 support remains SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.

## 10. Next-phase boundary

After Phase25 merge, DEFINE/LOCK **Phase26 — Materially Different Strategy Architecture Research**.

Phase26 principles:

- research-only; zero provider/broker/order/PAPER/LIVE/support authority;
- use accepted Phase25 PIT production-path lineage as primary research source;
- do not rely on the incomplete legacy Phase11/24 broad research join as primary input;
- freeze materially different architecture families and search dimensions before target performance;
- retain realistic costs, temporal purge, dependence handling, block bootstrap, year/regime robustness, concentration gates, and multiplicity control;
- investigate cross-sectional relative strength, volatility/liquidity-conditioned mean reversion, gap/event continuation/reversal, volatility-normalized trend/breakout, multi-timeframe confirmation, and composite feature-block signals;
- short strategies must not simply mirror long rules;
- protected/future evidence remains separate;
- Phase11 support remains production authority unless a later separately accepted replacement decision occurs.

Preserve Phase21/22 PAPER authority, Phase13/14 independence, LIVE disablement, and no automatic failover. GUI remains monitoring/control only. Scheduler/PostgreSQL promotion remain separate future authority decisions.