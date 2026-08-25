# ATLAS Phase Execution Flow

**Normative development-flow contract. Last synchronized: 2026-08-24.**

## 1. Core rule

ATLAS advances by explicit numbered phases:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

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

Authority-changing phases preregister exact authorization and fail-closed behavior. Research phases that select models/strategies/thresholds preregister the search space, metrics, dependence handling, multiplicity, temporal validation, costs/stress, and protected-evidence boundary before final/protected evidence is read.

## 4. Batch-first package

Normal coherent package:

`implementation + targeted tests + independent validator + CLI/orchestration as applicable + documentation/status`

Focused tests do not replace final regression/CI. Do not run full CI after every tiny edit merely for ceremony. Fix correctness/security/data/authority defects before stacking more work. Never weaken evidence/risk/authority gates to create activity.

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
- Entitlement/session gaps are surfaced, never hidden.
- Partial failed analytical output does not become accepted state merely because it is newer.
- Zero cases/promotions/finalists/provider calls are valid accepted outcomes when they follow the locked evidence path.

## 7. Research/protected-evidence rules

- Candidate/search space and selection rules are frozen before protected evidence.
- Selection and protected/final evidence remain logically and, where practical, physically separated.
- Selection locks are written before internal/protected validation when required.
- Losing alternatives are not revisited after internal/protected results unless a new separately preregistered phase is started.
- Descriptive post-run forensics may explain failure but cannot retroactively change thresholds or support.
- If no candidate earns protected-evidence access, do not open the protected set.

## 8. Acceptance and merge

A phase is ACCEPTED only when required implementation, focused tests, independent validator, full CI, target evidence, negative/uncertainty paths, and documentation are complete with no unresolved blocker.

After acceptance:

1. mark PR ready;
2. merge the exact tested head;
3. verify authoritative `main`;
4. synchronize living docs to record the merge SHA;
5. verify the post-merge no-authority handoff head as appropriate;
6. define/lock the next numbered phase before substantive implementation.

## 9. Current application — Phase24 accepted/merged

- **Phases 1–24 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a` through PR #26.
- Phase24 disposition: **NO SUPPORT REPLACEMENT**.
- Gate1 fingerprint: `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
- Gate2 target head: `f591942413973107d7abc9d21325623e2e7000f1`.
- Final pre-merge living-doc head: `5ed3311d4ec1ac97cf841e160cf9c0987f731fe5`.
- Final pre-merge CI `32806726958`: Ubuntu/Windows SUCCESS; all validators through Phase24 Gate2 and full regression passed.

Phase24 evidence:

1. Gate0: 23 current WARM/HOT cases, 92 eligible incumbent route evaluations, 48 counterfactual fires, 21/23 cases with >=1 fire; authority zero.
2. Gate1: exactly 28 bounded challengers and stronger methodology preregistered before challenger results.
3. Gate2: 28 challengers, 0 basic-pass, 0 selections/finalists, 0 protected reads, all external/execution/support writes zero, independent PASS.
4. Post-run forensics: all 28 failed chronological-fold robustness, positive bootstrap LCB, and positive 25 bps stress; sample scarcity was not the general problem.
5. Phase11 support remains SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.
6. No Gate3 protected evaluation occurred.

## 10. Next-phase boundary

The post-Phase24 audit found a population-fidelity mismatch between historical support and production promotion. Historical studies use broad daily rows plus broad market-regime routing; production requires PIT universe -> discovery -> WARM/HOT direction -> market/sector/ticker routing -> support -> current rule firing.

Therefore DEFINE/LOCK **Phase25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence** next.

Initial Phase25 principles:

- zero provider/broker/order/PAPER/LIVE/support authority;
- no replay before legitimate intraday/ticker-regime origin **2021-08-16**;
- no synthetic pre-2021 1h/4h/ticker context;
- reconstruct PIT universe, multi-timeframe discovery scoring, discovery hysteresis, WARM/HOT direction, market/ticker route semantics;
- sector remains `UNAVAILABLE` absent authoritative historical sector mapping;
- initially hold incumbent rules and the three-session outcome fixed;
- independently validate the reconstructed production-path population;
- only after route-fidelity evidence decide whether a new support-replacement or materially different strategy-family phase is justified.

If route-fidelity conditioning still has no robust edge, later separately preregistered strategy research should examine genuinely different architectures—relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite—rather than further threshold tweaks.

Preserve Phase21/22 PAPER authority, Phase13/14 independence, LIVE disablement, and no automatic failover. GUI remains monitoring/control only. Scheduler/PostgreSQL promotion remain separate future authority decisions.
