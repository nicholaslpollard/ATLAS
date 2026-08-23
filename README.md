# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform.

Core flow:

`market/reference data -> Parquet/DuckDB -> features -> discovery -> regimes -> ML probabilities -> strategy routing -> promoted-candidate research -> news/events -> instrument/trade plan -> portfolio risk -> independent AI audit -> alerts/execution -> outcome learning -> browser control plane`

The accepted ML layer produces probability evidence; it does not directly create trades. Strategy selection, risk, AI review, and broker execution remain explicit downstream layers.

## Current state

- **Phases 1-17 are accepted and merged**, including the historical extension, strategy/regime routing, promoted-candidate research, deterministic context/geometry/risk, independent AI audit, broker-neutral shadow/paper execution, cumulative data-lineage audit, browser control plane, and provider-readonly operational readiness.
- The accepted Phase 10 production model remains the conventional HGB probability surface using 33 point-in-time quantitative features. The longer-history C result is retained as separately versioned challenger/research evidence rather than silently replacing production authority.
- Webull is the planned primary execution broker; Alpaca is the manually selectable secondary/fallback broker. Automatic cross-broker failover remains disabled.
- Phase 17 accepted real Webull sandbox and Alpaca paper read-only reconciliation with both brokers available/reconciled and zero provider/live writes.
- **Next authority checkpoint: paper/sandbox provider mutation.** It requires separate explicit user authorization before ATLAS may exercise real provider order submission/cancel/replace/flatten lifecycle behavior. Live execution remains disabled and is not implied by that future checkpoint.

The legacy Chart Monitor is preserved while ATLAS is built as the redesigned system.

## Project direction

The authoritative architecture, non-negotiable boundaries, phase roadmap, broker plan, and accelerated development/validation protocol are maintained in [`docs/roadmap.md`](docs/roadmap.md).

Detailed accepted-phase evidence remains in the phase-specific documents and merged pull requests.
