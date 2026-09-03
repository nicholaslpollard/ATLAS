from pathlib import Path

MARKER = "## A34.5 implementation closeout — 2026-09-03"

README_APPEND = r'''

## A34.5 implementation closeout — 2026-09-03

This section is the current A34.5 implementation state and supersedes earlier
"must implement" wording above. The near-live Operational PAPER observability path
is implemented in the existing stacked Phase19 GUI; no separate trading truth was
created.

Contract `a34.5-paper-dashboard-v1-local-authoritative-artifacts-no-provider-calls`
adds a strictly read-only `PaperDashboardService` and local GET
`/api/v1/ops/paper-dashboard`. It reads Phase15 manifests/attempts/outcomes and the
persisted Phase5 live-market state only. Phase15 attempt paths are constrained to
the Phase15 root, SHA-256 verified, and schema validated. Phase15 outcomes are
immutable conflict-rejecting local records and are schema validated; the current
outcome store has no separate outcome-manifest hash, so ATLAS does not claim one.

The existing Phase19 browser now contains a PAPER operations panel for dashboard
state, execution routing, last reconciled account state, open ATLAS positions,
decisions/reasons, order/fill state, completed trades, realized gross P&L, provider
uncertainty/reconciliation warnings, and evidence health. It reuses the existing
local 5/15/30-second observability cadence through the
`atlas:observability-refreshed` event; `paper_dashboard.js` owns no second timer and
uses GET only. Browser refresh never initializes or refreshes a broker/provider and
has no mutation authority.

Open-position marks are conservative and only exist from persisted quotes that are
`FRESH` and no older than the accepted Phase15 30-second quote-age cap: LONG marks
use bid and SHORT marks use ask. Stale/missing quotes produce no marked P&L. The
latest displayed broker account/reconciled-position snapshot is explicitly
`LAST_RECONCILED_PRE_SUBMIT`; filled entry evidence is explicitly labeled
`ENTRY_EVIDENCE_PRESENT_RECONCILIATION_AFTER_ENTRY_NOT_IMPLIED`. Provider submission
uncertainty or unresolved reconciliation produces `DEGRADED`, while missing evidence
is `NOT_RUN` and path/hash/schema failure is `INVALID`.

Two upstream limitations remain visible rather than guessed: Phase15 execution
intents do not yet bind the exact practitioner `strategy_id`, so strategy provenance
is `UNAVAILABLE_UPSTREAM_STRATEGY_NOT_BOUND_TO_PHASE15_INTENT`; Phase15 outcomes
currently expose realized **gross** P&L only, so net realized P&L is
`UNAVAILABLE_PHASE15_OUTCOME_SCHEMA_IS_GROSS_ONLY`.

Acceptance caught and repaired a real defect: the first implementation compared the
lowercase `DiscoveryDirection.value` to uppercase `"BULLISH"`, causing LONG marks to
fall through to the short/ask branch. The focused test expected bid `102.00` but saw
ask `102.10`. The owning read model was repaired to compare enum members directly,
use bid for `BULLISH`, ask for `BEARISH`, and fail closed on unsupported marked
positions. The A34 focused workflow was then hardened to run
`tests/unit/test_a34_5_paper_dashboard.py` explicitly.

Pre-closeout exact-head acceptance evidence on `0cf249ac6df30a76f5f3dbd8ec0fed80a77a4c6f`:
A34/A34.5 focused workflow `33812319638` passed on Ubuntu and Windows; full
`ATLAS tests` workflow `33812319636` passed on Ubuntu and Windows; all specialized
scientific/contract workflows on that head also passed. The final documentation-
inclusive tree must still pass its own exact-head CI before merge.

Existing operator PAPER broker-switch controls remain explicit and flat-only: the
operator can review/request Webull ↔ Alpaca routing changes, and the processor
reconciles both PAPER brokers before changing local routing. Automatic broker
failover remains disabled. Automatically canceling/closing broker exposure before a
switch requires later provider-write authority and is not smuggled into this
read-only gate. Market-data selection remains contractually independent from
execution-broker selection.

Authority/safety after A34.5: strategy promotion **none**; A35 broker mutation **not
started by this package**; LIVE **false**; automatic broker failover **false**;
protected return rows read **0**; master holdout **unconsumed**. Once this package is
accepted/merged, the A34.5 observability prerequisite is satisfied and A35
Operational PAPER becomes the next separate operator-authorized product package,
with Webull PAPER preferred and Alpaca paper manually selectable. The planned
DEVELOPMENT replay on the user's trusted lake may still run independently and does
not become strategy authority merely because the product can PAPER trade.
'''

ROADMAP_APPEND = r'''

## 24. A34.5 implementation closeout — 2026-09-03

This section is the current A34.5 state and supersedes earlier prospective wording
in Sections 16, 19, 21, and 23 where it describes A34.5 as not yet implemented.
A34.5 is implemented as a read-only operator-observability layer over the accepted
Phase15/Phase5 local evidence path; it creates no second trading engine and grants no
broker-write authority.

### 24.1 Implemented product path

- Contract:
  `a34.5-paper-dashboard-v1-local-authoritative-artifacts-no-provider-calls`.
- Local read model: `packages/control_plane/paper_dashboard.py`.
- Local endpoint: `GET /api/v1/ops/paper-dashboard` in the stacked Phase19 server.
- Browser panel: `apps/web/paper_dashboard.js`, bundled into the existing Phase19
  observability asset rather than creating a second frontend.
- Refresh: the PAPER panel reuses the existing local 5/15/30-second observability
  timer via `atlas:observability-refreshed`; it creates no independent interval.
- Browser/provider safety: GET only, no broker/provider refresh query, no operations
  POST, browser mutation authority false, automatic broker refresh false.

Phase15 attempt evidence must remain inside the Phase15 root, match its manifest
SHA-256, and validate as `ExecutionAttemptRecord`. Phase15 outcomes remain immutable
conflict-rejecting files and validate as `ExecutionOutcome`; the current outcome
store has no separate outcome-manifest hash, so no stronger hash claim is made.
Persisted Phase5 market state is read locally only.

### 24.2 Operator truth and conservative marking

The dashboard exposes the execution manifest/routing state, latest broker account
snapshot, pre-submit reconciled positions, filled-but-unclosed ATLAS position
evidence, deterministic decision/reason codes, order/fill lifecycle, completed
trades, realized gross P&L, and provider/reconciliation health. It distinguishes:

- `LAST_RECONCILED_PRE_SUBMIT` broker/account state;
- `ENTRY_EVIDENCE_PRESENT_RECONCILIATION_AFTER_ENTRY_NOT_IMPLIED` after a fill;
- `NOT_RUN` when no Phase15 manifest exists;
- `INVALID` for path/hash/schema-invalid local evidence; and
- `DEGRADED` for provider-submission uncertainty or required reconciliation.

Marked unrealized P&L exists only when the persisted quote is `FRESH` and within
the accepted Phase15 30-second quote-age cap. LONG uses bid; SHORT uses ask. A stale
or missing quote produces no current mark or unrealized P&L. Unsupported/neutral
marked-position direction fails closed.

The GUI deliberately does **not** invent two upstream fields that Phase15 cannot yet
prove: exact practitioner `strategy_id` provenance is
`UNAVAILABLE_UPSTREAM_STRATEGY_NOT_BOUND_TO_PHASE15_INTENT`, and realized net P&L is
`UNAVAILABLE_PHASE15_OUTCOME_SCHEMA_IS_GROSS_ONLY`. Completed-trade P&L is labeled
`PHASE15_REALIZED_GROSS_DESCRIPTIVE_ONLY`.

### 24.3 Defect found by acceptance and repaired

The first full-suite run found that a LONG fixture was marked at ask `102.10` rather
than conservative bid `102.00`. Root cause was an enum/string case error:
`DiscoveryDirection.value` is lowercase while the read model compared against
uppercase `"BULLISH"`. The implementation was repaired at the owning layer to compare
`DiscoveryDirection.BULLISH` / `BEARISH` directly, use bid/ask correctly, and reject
unsupported marked directions. No validator was weakened.

Focused CI now explicitly includes `tests/unit/test_a34_5_paper_dashboard.py`, which
covers `NOT_RUN`, attempt hash failure → `INVALID`, LONG bid/SHORT ask marking,
stale quote no P&L, provider uncertainty → `DEGRADED`, local endpoint behavior with a
broker factory that fails if invoked, and browser polling/mutation safety.

Pre-closeout exact-head evidence on
`0cf249ac6df30a76f5f3dbd8ec0fed80a77a4c6f`:

- A34/A34.5 focused run `33812319638`: **SUCCESS**, Ubuntu + Windows;
- full `ATLAS tests` run `33812319636`: **SUCCESS**, Ubuntu + Windows;
- specialized retained scientific/contract workflows: **SUCCESS**.

The final living-document-inclusive tree must pass its own exact-head workflows
before merge; those final results are the merge gate, not a reason to rewrite this
historical pre-closeout evidence.

### 24.4 Broker controls and remaining provider-write work

The existing Phase16/Phase19 PAPER broker cards already let the operator review and
request Webull ↔ Alpaca routing changes. The switch processor reconciles both PAPER
brokers and changes local routing only when the accepted flat/reconciled switch
contract passes. It does not automatically cancel/close provider positions, and
A34.5 does not add that destructive authority. The later controlled handoff remains:
halt entries → cancel/reconcile source orders → close ATLAS-managed source positions
→ prove source flat → reconcile target → switch → fresh evaluation → only then new
orders. Automatic cross-broker failover remains prohibited.

Market-data provider/feed and execution broker remain independent domains. The
verified Webull real-time OpenAPI evidence in Section 23 remains valid and may later
support Webull data with Alpaca execution; provider entitlement/freshness must still
be measured at runtime.

### 24.5 Authority and next work

A34.5 changes product readiness, not strategy evidence:

- strategy authority promotion: **none**;
- protected return rows read: **0**;
- master holdout consumed: **false**;
- A34.5 browser/provider/broker writes: **0**;
- A35 PAPER broker mutation from this package: **0**;
- LIVE authority: **false**;
- automatic broker failover: **false**.

After final exact-head acceptance and merge, A34.5 satisfies the operator-
observability prerequisite. **A35 Operational PAPER is the next separate,
operator-authorized package**, using Webull PAPER as the preferred execution broker
and Alpaca paper as a manually selectable alternate. A35 must exercise the actual
prospective lifecycle, restart/idempotency, duplicate prevention, stale-data,
partial/cancel/reject handling, reconciliation, kill controls, and dashboard
traceability. It must not be conflated with qualifying PAPER or LIVE.

Independent Track B work remains valid in parallel: run the frozen nine-policy
DEVELOPMENT replay on the user's trusted lake when its exact source/regime bundle is
available; preserve all zero/negative/underpowered results and do not promote a
strategy merely because A34.5/A35 product plumbing works.
'''


def append_once(path: Path, appendix: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    path.write_text(text.rstrip() + appendix + "\n", encoding="utf-8")
    return True


changed = False
changed |= append_once(Path("README.md"), README_APPEND)
changed |= append_once(Path("docs/roadmap.md"), ROADMAP_APPEND)
print("living_docs_changed=" + str(changed).lower())
