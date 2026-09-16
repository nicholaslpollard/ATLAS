from __future__ import annotations

from pathlib import Path


def append_once(path_text: str, marker: str, section: str) -> None:
    path = Path(path_text)
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + section.rstrip() + "\n", encoding="utf-8")


append_once(
    "README.md",
    "## 2026-09-16 — Deterministic simulation decision record",
    '''## 2026-09-16 — Deterministic simulation decision record

Track A now composes the accepted product-side decision layers into one immutable simulation record under frozen contract `62dceacde38687828e610c096d8c0a39479d5bc65b26b56aed2bf4164d8c8af8` (`atlas-simulation-decision-record-v1`). The record binds the full underlying move/time forecast, original stock-economics assumptions, calculated stock economics, exact universal `ActionabilityPolicy`, selected trade-expression mode, normalized option economic candidates when supplied, gate evaluations, final stock/option/abstain decision and reason-code lineage. It records the forecast instance fingerprint plus the accepted forecast, stock-economics and trade-expression contract fingerprints so a simulator result can be traced to the exact decision inputs that produced it.

Decision time is an explicit timezone-aware input and cannot precede forecast creation. Option candidate input order is normalized before evaluation and fingerprinting, making replay independent of caller ordering. Ignored instruments are not erased: for example, `OPTIONS_ONLY` retains the stock economics but explicitly records that the stock gate was not evaluated by mode, while `STOCKS_ONLY` retains supplied option candidates with equivalent not-evaluated lineage. The final record fingerprint changes when evidence, stock assumptions, actionability policy, mode, option candidates or decision timestamp changes.

This record is a simulation/control-plane artifact only. It performs no provider or broker access, creates no order, and grants no PAPER, LIVE, promotion or confluence authority. Option candidates may currently be supplied only as already-formed decision-support `EconomicCandidate` objects; the separately versioned option scenario-economics adapter remains future work and historical option P&L remains unclaimed.'''
)

append_once(
    "docs/roadmap.md",
    "## Track A deterministic simulation decision record — 2026-09-16",
    '''## Track A deterministic simulation decision record — 2026-09-16

The product-side path now has a versioned composition boundary before account simulation. Frozen contract: `62dceacde38687828e610c096d8c0a39479d5bc65b26b56aed2bf4164d8c8af8` (`atlas-simulation-decision-record-v1`).

The deterministic record binds:

1. the complete `atlas-underlying-move-time-forecast-v1` object and forecast instance fingerprint;
2. the original `StockEconomicsInputs` and resulting `atlas-stock-economics-adapter-v1` output;
3. the exact caller-supplied universal `ActionabilityPolicy` plus its deterministic fingerprint;
4. the selected `OPTIONS_ONLY`, `STOCKS_ONLY`, `OPTIONS_PREFERRED` or `STOCKS_PREFERRED` mode;
5. normalized option economic-candidate inputs and individual candidate fingerprints when supplied;
6. stock/option gate eligibility and reason-code lineage, including explicit `NOT_EVALUATED_BY_MODE` states rather than silently deleting ignored evidence;
7. the final trade-expression decision and selection/abstention reason codes;
8. an explicit timezone-aware decision timestamp and deterministic final record fingerprint.

The record requires accepted upstream contract identities and rejects a decision timestamp before forecast creation. Option input ordering is canonicalized, duplicate option identifiers are rejected, and changes to evidence, policy, mode, timestamp or instrument candidates are fingerprint material.

Authority boundary remains unchanged: provider reads/writes = 0, broker reads/writes = 0, order creation = false, PAPER = false, LIVE = false, promotion = false and confluence authority = false. The legacy Phase 13/15 execution contracts remain untouched.

Immediate Track A continuation after acceptance:

1. implement a new simulation account-state contract under `packages/simulation` with explicit cash, equity, reserved capital, gross exposure and simulated positions;
2. apply stock decisions to that state through deterministic capital reservation/release and opportunity competition without broker access or order authority;
3. produce a replayable account ledger keyed to simulation-decision-record fingerprints;
4. implement the separately versioned option scenario-economics adapter using the same underlying forecast plus strike/DTE/Greeks/IV/liquidity/event evidence;
5. add option capital/risk semantics to the same simulator only after the option-economics contract is accepted;
6. expose decision fingerprints, expression modes, economics and abstention/rejection reasons through the browser/control plane.

The Strategy Evidence Register is intentionally unchanged by this package because it introduces product/simulation architecture rather than new strategy research evidence or a strategy disposition change.'''
)
