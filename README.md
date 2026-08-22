# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is a broad-market quantitative discovery, analysis, decision-support, learning, and eventual automated-trading platform.

Core flow:

`market/reference data -> Parquet/DuckDB -> features -> discovery -> regimes -> ML probabilities -> strategy routing -> promoted-candidate research -> news/events -> instrument/trade plan -> portfolio risk -> independent AI audit -> alerts/execution -> outcome learning -> browser control plane`

The accepted ML layer produces probability evidence; it does not directly create trades. Strategy selection, risk, AI review, and broker execution remain explicit downstream layers.

## Current state

- Foundation through **Phase 10 — ML Probability & Evaluation**: accepted.
- Accepted Phase 10 model: conventional HGB probability surface using 33 point-in-time quantitative features.
- Active sidecar work: controlled Alpaca raw-SIP daily historical extension back to 2016, preserving the accepted Massive-era production lineage and Phase 10 model.
- Next roadmap phase after the historical extension: **Phase 11 — Strategy Evaluation and Regime Routing**.

The legacy Chart Monitor is preserved while ATLAS is built as the redesigned system.

## Project direction

The authoritative architecture, non-negotiable boundaries, phase roadmap, broker plan, and accelerated development/validation protocol are maintained in [`docs/roadmap.md`](docs/roadmap.md).

Detailed accepted-phase evidence remains in the phase-specific documents and merged pull requests.