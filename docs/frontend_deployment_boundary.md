# ATLAS Frontend Deployment Boundary

**Unnumbered architecture note. This document does not create provider, broker, execution, or live authority.**

ATLAS already has a browser frontend through the Phase 19 loopback control-plane extension. The current frontend is intentionally local because the accepted Phase 16/19 security model is a loopback operator control plane, not an internet-facing application.

## 1. Current state — local web UI available now

Launcher:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase19_control_plane.py
```

Browser:

`http://127.0.0.1:8765`

Current characteristics:

- loopback-only;
- Phase 19 observability uses sanitized local artifacts;
- Phase 19 provider reads/writes disabled;
- existing broker read-only refresh remains an explicit Phase 16 action;
- browser is not execution authority;
- live promotion disabled;
- automatic cross-broker failover disabled;
- credentials/raw broker IDs are not exposed to the browser.

This is the correct environment for active frontend design and operator-UX work. Market hours are not required to build the UI; missing/stale live artifacts render as unavailable/not-ready rather than being synthesized.

## 2. Do not expose the current loopback server directly

The current server must not be made internet-accessible merely by changing its bind address, opening a router/firewall port, or placing it behind an unaudited tunnel.

The accepted loopback controls are not a substitute for an internet deployment boundary. Direct exposure would mix local operator controls, local filesystem state, and remote network access in a way the current Phase 16/19 contracts were not designed or accepted to secure.

## 3. Safe remote-readonly preview target

The first useful remotely accessible ATLAS frontend should be **read-only** and should not proxy the local control-plane action surface.

Recommended boundary:

`ATLAS local/runtime evidence -> sanitized publish/replication boundary -> remote read-only API/state -> authenticated HTTPS frontend`

The remote read-only surface may eventually expose only explicitly whitelisted fields already suitable for Phase 19 observability, such as:

- system/phase health;
- sanitized market-state summaries;
- candidate intelligence;
- ML probability display;
- regime/strategy evidence;
- AI-audit disposition summaries;
- descriptive paper/shadow outcomes;
- sanitized lineage and artifact recency.

It must not expose:

- provider/broker secrets;
- raw broker account IDs;
- provider order IDs unless a future sanitized public identifier is explicitly designed;
- local filesystem paths;
- mutation confirmation tokens;
- direct submit/cancel/replace/flatten controls;
- an implicit route back into the local Phase 16 action API.

## 4. Minimum remote security requirements

Before any ATLAS deployment is reachable beyond the trusted local host, the deployment design must explicitly provide and validate:

- HTTPS/TLS only;
- authenticated users/sessions;
- least-privilege authorization;
- secure cookie/session handling where applicable;
- strict origin policy;
- CSRF defenses for any future state-changing routes;
- self-restrictive Content Security Policy;
- request/body/rate limits;
- sanitized error handling;
- no secrets in browser bundles, HTML, logs, URLs, or API responses;
- dependency/build reproducibility and secret-hygiene CI;
- explicit audit trail for any future remote action;
- a network boundary that prevents the public frontend from obtaining direct provider credentials.

## 5. Three-stage frontend path

### Stage A — LOCAL_OPERATOR_UI — active now

Purpose: design the real ATLAS product experience against persisted/sanitized local evidence.

Allowed:

- navigation and page hierarchy;
- responsive layout;
- candidate workspaces;
- probability/regime visualizations;
- pipeline/system health;
- paper/shadow outcome charts;
- live-market diagnostics from persisted state;
- local read-only broker visibility through accepted explicit controls;
- empty/stale/error states.

No new trading authority is created.

### Stage B — PRIVATE_REMOTE_READONLY — future deployment boundary

Purpose: view ATLAS securely away from the target machine without exposing the local control plane.

Requirements:

- sanitized replicated state/API;
- authentication;
- HTTPS;
- no remote broker/provider mutation routes;
- no local secret forwarding;
- explicit deployment validation before use.

This stage does not require live-trading authorization and can be developed before ATLAS goes live, but it should be introduced as a deliberate deployment/security package rather than by exposing the current server.

### Stage C — AUTHENTICATED_REMOTE_CONTROL — later separate authority boundary

Purpose: permit selected remote operator actions only after the persistent operational-state architecture and security model are accepted.

This requires a future explicit contract for:

- remote action authorization;
- stronger identity/session controls;
- action-level confirmation and audit;
- replay/idempotency protections;
- reconciliation/uncertainty behavior;
- provider-mutation authority separation;
- live-trading authority separation.

Stage C is not implied by Stage A or B and is not currently authorized.

## 6. Frontend work that can proceed while markets are closed

Useful work that is independent of market hours includes:

- dashboard navigation/information architecture;
- candidate list/detail UX;
- ML probability visualization;
- regime and strategy evidence presentation;
- outcome/performance charts using persisted artifacts;
- data freshness/status affordances;
- responsive/mobile behavior;
- accessibility/keyboard semantics;
- loading/empty/error states;
- frontend performance;
- sanitized API contract tests;
- private remote-readonly deployment design.

Regular market hours are only required when the work specifically needs fresh regular-session evidence or real Phase 18B provider certification.

## 7. Authority statement

This document is planning/design only. It does not change the accepted Phase 16 loopback security model, Phase 18 mutation gate, Phase 19 read-only authority, provider permissions, broker permissions, live-trading state, or automatic-failover prohibition.
