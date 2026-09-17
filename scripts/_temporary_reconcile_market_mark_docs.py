from pathlib import Path

contract_fp = "1219f600e447f90718213ce0f974314f6480e90e13f46487770785e45c87c154"

readme_section = f'''## 2026-09-16 — Source-bound market-mark evidence\n\nTrack A now freezes `atlas-simulation-market-mark-evidence-v1` under contract\n`{contract_fp}`. The package binds one immutable mark record to one exact accepted\nopen-position fingerprint and requires explicit source id/SHA-256, provider, feed,\ntransport, feed-quality, market timestamp, receive timestamp, and valuation timestamp.\nIt is evidence-only: the accounting layer still performs no provider or broker read.\n\nFor the currently supported long stock and long-option positions, v1 selects the\n**executable bid** as the conservative valuation candidate. Midpoint and last may be\nretained descriptively but are never treated as liquidation truth. Stock requires a\npositive bid; a long option may legitimately carry a zero bid, preserving a possible\nzero liquidation value rather than inventing one. Crossed quotes fail closed.\n\nFreshness is frozen at a maximum **60 seconds** from market timestamp to valuation\ntime. `market_timestamp <= received_timestamp <= valuation_timestamp` is mandatory.\nA stale observation is retained for audit but is explicitly\n`valuation_eligible = false`; it cannot create or carry forward P&L. The 60-second\nlimit is a versioned simulation policy rather than a permanent provider constant.\n\nThis package computes no position value and grants no mark-to-market, unrealized or\nrealized P&L, exit/closeout, account mutation, provider/broker, order, PAPER, LIVE,\npromotion or confluence authority. The next bounded Track A package consumes only\nfresh valuation-eligible marks to create deterministic marked position/account state\nand unrealized P&L. The Strategy Evidence Register remains unchanged because this is\nproduct/account-simulation architecture only.\n'''

roadmap_section = readme_section.replace(
    "## 2026-09-16 — Source-bound market-mark evidence",
    "## Track A source-bound market-mark evidence — 2026-09-16",
    1,
)

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
old = '''This package deliberately stops before market valuation. It has no mark-to-market,\nunrealized-P&L, realized-P&L, exit/closeout, provider/broker, order, PAPER, LIVE,\npromotion or confluence authority. The next bounded Track A work is source-bound market\nmark evidence and deterministic mark-to-market/unrealized-P&L state, followed by\nexit/closeout and realized-P&L accounting. The Strategy Evidence Register remains\nunchanged because this is product/account-simulation architecture only.'''
new = '''The open-position package deliberately stops before market valuation. The source-bound\nmarket-mark evidence layer described below now supplies exact valuation provenance, but\nmark-to-market, unrealized/realized P&L, exits/closeout, broker mutation and PAPER/LIVE\nauthority remain separate gates. The Strategy Evidence Register remains unchanged\nbecause these packages change product/account-simulation architecture only.'''
if old not in text:
    raise SystemExit("README open-position continuation paragraph not found")
text = text.replace(old, new, 1)
marker = "## A33/B33 reference foundation"
if marker not in text:
    raise SystemExit("README A33 insertion marker not found")
if "## 2026-09-16 — Source-bound market-mark evidence" not in text:
    text = text.replace(marker, readme_section + "\n" + marker, 1)
readme.write_text(text, encoding="utf-8")

roadmap = Path("docs/roadmap.md")
text = roadmap.read_text(encoding="utf-8")
if old not in text:
    raise SystemExit("roadmap open-position continuation paragraph not found")
text = text.replace(old, new, 1)
insert_marker = "\n\n## Track A funding/collateral terms — 2026-09-16"
if insert_marker not in text:
    raise SystemExit("roadmap funding insertion marker not found")
if "## Track A source-bound market-mark evidence — 2026-09-16" not in text:
    text = text.replace(insert_marker, "\n\n" + roadmap_section + insert_marker, 1)
old_next = '''Immediate Track A continuation after acceptance:\n\n1. freeze source-bound stock/option market-mark evidence with explicit provider/feed,\n   market timestamp, receive timestamp, freshness and transport provenance;\n2. apply deterministic mark-to-market and unrealized-P&L accounting to the accepted\n   open-position state without treating stale/unknown marks as valuation truth;\n3. preserve entry cost basis, paid fees and entry-reference option delta separately\n   from current market marks/Greeks;\n4. only after valuation semantics are accepted, add deterministic exits/closeout and\n   realized-P&L accounting with replay/idempotency checks; and\n5. keep provider/broker mutation, orders, PAPER/LIVE, promotion and confluence under\n   their separate authority gates.'''
new_next = '''Immediate Track A continuation after acceptance:\n\n1. consume exact fresh, valuation-eligible mark evidence for every active open position;\n2. compute deterministic marked position value and unrealized P&L relative to immutable\n   entry book value, with marked account equity reconciling entry-book equity plus\n   aggregate unrealized P&L;\n3. fail closed to incomplete account valuation when any active position lacks a fresh\n   eligible mark; never silently carry a stale mark forward as current P&L;\n4. preserve option entry-delta reference separately and infer no current Greek unless a\n   later explicit current-Greeks evidence contract supplies it; and\n5. after MTM semantics are accepted, add deterministic exits/closeout and realized-P&L\n   accounting while provider/broker mutation, PAPER/LIVE, promotion and confluence stay\n   separately gated.'''
if old_next not in text:
    raise SystemExit("roadmap market-mark continuation list not found")
text = text.replace(old_next, new_next, 1)
roadmap.write_text(text, encoding="utf-8")
