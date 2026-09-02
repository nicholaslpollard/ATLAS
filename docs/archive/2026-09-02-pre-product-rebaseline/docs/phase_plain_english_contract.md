# ATLAS Plain-English Phase Communication Contract

**Normative communication requirement. Added: 2026-08-26.**

This document exists so the operator can always understand what ATLAS is doing without having to interpret implementation jargon, statistical notation, hashes, CI logs, or internal research terminology.

## 1. Rule

Every numbered phase must have a plain-English explanation at both **phase start** and **phase end**.

Technical detail is still retained for development, auditability, reproducibility, and future continuation. It follows the plain-English explanation instead of replacing it.

## 2. Phase-start format

Before material work begins on a phase, return these items in ordinary language:

1. **Where we are now** — the current state of ATLAS and the specific problem blocking the next step.
2. **What this phase is trying to accomplish** — the phase objective in one or two understandable paragraphs.
3. **Why it matters for the end goal** — how the work improves ATLAS's ability to make better, safer, or more profitable-after-cost trading decisions.
4. **What will be built or changed** — the meaningful user/system changes, without implementation-level detail unless it helps understanding.
5. **What will be tested at the end** — what must be proven before the phase is allowed to pass.
6. **What success means** — what ATLAS will be able to do or know if the phase succeeds.
7. **What happens if it fails or produces a negative result** — whether we repair the phase, remain blocked, or define a new research direction.
8. **What is explicitly not happening yet** — especially LIVE authority, broker mutation, deployment, or other downstream work that could be confused with the current phase.

The start explanation should normally be short enough to read in a few minutes. Technical implementation plans may follow separately.

## 3. Phase-end format

Before detailed evidence, return these items:

1. **Goal** — what the phase was supposed to accomplish.
2. **What we built** — the material changes that now exist.
3. **Did the full phase gate pass?** — PASS, ACCEPTED-NEGATIVE, or NOT ACCEPTED.
4. **What the results mean** — the practical meaning in ordinary language.
5. **What ATLAS can do now** — the real capability or authority change, or `NONE`.
6. **What is still missing or risky** — unresolved limitations, uncertainty, or downstream requirements.
7. **Where this leaves the project** — the current position in the roadmap.
8. **What happens next** — the exact next phase/objective and why it follows.

Only after those items should the response provide hashes, row counts, confidence intervals, p-values, fingerprints, test counts, CI IDs, validator output, or other technical evidence.

## 4. GUI/web/deployment visibility

Whenever a phase contains GUI, browser, API, web-development, deployment, scheduler, host, or production-operations work, the plain-English start/end explanation must specifically state:

- what the operator will be able to see or control in the interface;
- what is frontend/display-only versus what can actually trigger system actions;
- whether the interface is local development, test deployment, PAPER/shadow operation, or production deployment;
- what security/authority restrictions remain in place;
- what deployment environment is being created or changed;
- whether the change affects trading logic or only how the operator interacts with it.

## 5. Future-chat requirement

A future chat continuing ATLAS should read `README.md`, `docs/roadmap.md`, `docs/current_status.md`, `docs/phase_flow.md`, this communication contract, and the active phase specification before continuing material work.

The operator should never have to infer project status solely from technical logs. If technical evidence is necessary for continuation, preserve it, but accompany it with the plain-English explanation above.
