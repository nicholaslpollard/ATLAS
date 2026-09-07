from pathlib import Path

root = Path(__file__).resolve().parents[1]
readme_path = root / "README.md"
roadmap_path = root / "docs" / "roadmap.md"
workflow_path = root / ".github" / "workflows" / "a34-5-stale-truth-once.yml"
self_path = Path(__file__).resolve()


def swap(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing stale-truth anchor: {label}")
    return text.replace(old, new, 1)


text = readme_path.read_text(encoding="utf-8")
text = swap(
    text,
    """- A33/B33 foundation implementation is complete and protected by its exact-head\n  acceptance workflow. It has not opened ATLAS historical performance, changed\n  strategy authority, or submitted any provider, broker, PAPER, or LIVE mutation.\n- The first trusted-lake adapter is implemented for the Massive-only post-seam\n  DEVELOPMENT interval. It remains source-only in this repository: no historical\n  strategy result has been created or inspected here.\n""",
    """- A33/B33 foundation implementation is complete and protected by its exact-head\n  acceptance workflow. Historical performance has now been opened only for the\n  frozen V2 DEVELOPMENT and one-time walk-forward versions described below; strategy\n  authority did not change and provider/broker/PAPER/LIVE mutations remain zero.\n- The trusted-lake adapters are implemented. The retained Massive path remains\n  reproducibility-only; the isolated Alpaca SIP V2 adapter produced the completed\n  frozen DEVELOPMENT and walk-forward evidence described below.\n""",
    "README A33/adapter current truth",
)
text = swap(
    text,
    """- The first A34 RESEARCH account-replay vertical slice is implemented: deterministic\n  candidate admission, cash/position accounting, simulated orders, outcomes, equity\n  curve, read-only API, and visible browser state. No empirical replay exists in this\n  checkout. It was accepted in PR #48 and merged as\n""",
    """- The first A34 RESEARCH account-replay vertical slice is implemented: deterministic\n  candidate admission, cash/position accounting, simulated orders, outcomes, equity\n  curve, read-only API, and visible browser state. Empirical V2 DEVELOPMENT and\n  frozen walk-forward account replays now exist and are negative at the aggregate\n  account level; no strategy was promoted. The slice was accepted in PR #48 and\n  merged as\n""",
    "README A34 current truth",
)
text = swap(
    text,
    """  complete isolated native candidate base, not daily identity/quality acceptance or\n  production promotion. The quarantine is retained evidence and must be attributed\n  by the post-build gate rather than discarded or assumed harmless. Historical\n  results, PAPER authority, and LIVE authority remain absent.\n""",
    """  complete isolated native candidate base, not production promotion. The quarantine\n  is retained evidence and was carried into the post-build gate rather than\n  discarded or assumed harmless. Historical V2 RESEARCH results now exist only for\n  the frozen versions described below; PAPER authority and LIVE authority remain\n  absent.\n""",
    "README native V2 current truth",
)
text = swap(
    text,
    """- **Operator live observability is now a hard prerequisite to Operational PAPER.**\n  Before any A35 PAPER test begins, A34.5 must connect the authoritative engine/event\n  state to the browser so the operator can observe account state, positions, live\n  unrealized/realized P&L, strategy/setup rationale, risk/sizing, order/fill state,\n  exits, trade history, and system/provider/broker health without manual refresh.\n  No PAPER broker mutation is authorized merely by documenting this requirement.\n""",
    """- **A34.5 operator live observability is now implemented in PR #60.** Its\n  accepted merge closes the observability prerequisite before A35; A35 itself remains\n  a separate PAPER/broker-authority package and has not begun. No PAPER broker\n  mutation is authorized by A34.5.\n""",
    "README A34.5 prerequisite current truth",
)
readme_path.write_text(text.rstrip() + "\n", encoding="utf-8")

roadmap = roadmap_path.read_text(encoding="utf-8")
roadmap = swap(
    roadmap,
    """- Operational PAPER may be built and used with labeled baselines under its own\n  explicit controls, but actual A35 PAPER testing is blocked until A34.5 operator\n  live observability is accepted.\n""",
    """- PR #60 implements the A34.5 operator live-observability prerequisite. Once this\n  exact-head package is merged, A35 may begin only under its own separate PAPER/\n  broker-authority package; A35 has not begun.\n""",
    "roadmap section 9 A34.5 state",
)
roadmap_path.write_text(roadmap.rstrip() + "\n", encoding="utf-8")

workflow_path.unlink(missing_ok=True)
self_path.unlink(missing_ok=True)
