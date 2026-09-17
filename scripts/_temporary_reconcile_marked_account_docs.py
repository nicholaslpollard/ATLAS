from pathlib import Path

contract_fp = "f09a1ead48e86ae82442785f281c0e57d242db3773537a3ba64a44bb2519c082"

readme_section = f'''## 2026-09-16 — Deterministic marked account and unrealized P&L\n\nTrack A now adds `atlas-simulation-marked-account-state-v1` under contract\n`{contract_fp}`. It consumes the exact accepted open-position account snapshot plus\none exact fresh, valuation-eligible market-mark record for **every** active position at\none common valuation timestamp. Missing, stale, duplicate, mismatched, or extra marks\nfail closed; ATLAS does not publish an authoritative account-level marked-equity value\nfor an incomplete valuation snapshot.\n\nFor each active position, marked value is `quantity * selected bid mark * multiplier`.\nUnrealized P&L is marked value minus immutable entry book value, and unrealized return\nuses entry book value as its denominator. Account unrealized P&L is the sum of the\nposition values, while marked equity is `entry_book_equity + aggregate_unrealized_P&L`\nand independently reconciles to `cash + remaining reservations + marked open-position\nvalue`. Entry fees were already expensed when the position opened and are therefore\nnever subtracted a second time in unrealized P&L.\n\nA long option with a valid fresh zero bid may mark to zero and therefore to a full loss\nof its entry book value. Option delta-equivalent exposure remains the immutable\n**entry reference** only; this package does not infer a current Greek from price marks.\nAll marked positions share the requested valuation timestamp, and a mark whose market\ntimestamp predates the position open is rejected. Empty accounts produce a complete\nzero-position valuation deterministically.\n\nThis is deterministic simulation valuation only. It does not mutate the open-position\nstate and grants no realized-P&L, exit/closeout, provider/broker, order, PAPER, LIVE,\npromotion or confluence authority. The next bounded Track A work is broker-neutral\nsimulated exit-fill evidence followed by deterministic closeout/realized-P&L accounting\nwith lifetime trade-P&L and account-equity semantics kept explicit so entry fees cannot\nbe double counted. The Strategy Evidence Register remains unchanged because this is\nproduct/account-simulation architecture only.\n'''

roadmap_section = readme_section.replace(
    "## 2026-09-16 — Deterministic marked account and unrealized P&L",
    "## Track A deterministic marked account and unrealized P&L — 2026-09-16",
    1,
)

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
old = '''This package computes no position value and grants no mark-to-market, unrealized or\nrealized P&L, exit/closeout, account mutation, provider/broker, order, PAPER, LIVE,\npromotion or confluence authority. The next bounded Track A package consumes only\nfresh valuation-eligible marks to create deterministic marked position/account state\nand unrealized P&L. The Strategy Evidence Register remains unchanged because this is\nproduct/account-simulation architecture only.'''
new = '''The market-mark package itself remains evidence-only and grants no account mutation,\nrealized P&L, exit/closeout, provider/broker, order, PAPER, LIVE, promotion or\nconfluence authority. The deterministic marked-account layer described below now\nconsumes those fresh marks for simulation valuation and unrealized P&L. The Strategy\nEvidence Register remains unchanged because these packages change\nproduct/account-simulation architecture only.'''
if old not in text:
    raise SystemExit("README market-mark continuation paragraph not found")
text = text.replace(old, new, 1)
marker = "## A33/B33 reference foundation"
if marker not in text:
    raise SystemExit("README A33 insertion marker not found")
if "## 2026-09-16 — Deterministic marked account and unrealized P&L" not in text:
    text = text.replace(marker, readme_section + "\n" + marker, 1)
readme.write_text(text, encoding="utf-8")

roadmap = Path("docs/roadmap.md")
text = roadmap.read_text(encoding="utf-8")
if old not in text:
    raise SystemExit("roadmap market-mark continuation paragraph not found")
text = text.replace(old, new, 1)
insert_marker = "\n\n## Track A funding/collateral terms — 2026-09-16"
if insert_marker not in text:
    raise SystemExit("roadmap funding insertion marker not found")
if "## Track A deterministic marked account and unrealized P&L — 2026-09-16" not in text:
    text = text.replace(insert_marker, "\n\n" + roadmap_section + insert_marker, 1)
old_next = '''Immediate Track A continuation after acceptance:\n\n1. consume exact fresh, valuation-eligible mark evidence for every active open position;\n2. compute deterministic marked position value and unrealized P&L relative to immutable\n   entry book value, with marked account equity reconciling entry-book equity plus\n   aggregate unrealized P&L;\n3. fail closed to incomplete account valuation when any active position lacks a fresh\n   eligible mark; never silently carry a stale mark forward as current P&L;\n4. preserve option entry-delta reference separately and infer no current Greek unless a\n   later explicit current-Greeks evidence contract supplies it; and\n5. after MTM semantics are accepted, add deterministic exits/closeout and realized-P&L\n   accounting while provider/broker mutation, PAPER/LIVE, promotion and confluence stay\n   separately gated.'''
new_next = '''Immediate Track A continuation after acceptance:\n\n1. freeze broker-neutral simulated complete exit-fill evidence tied to one exact active\n   open-position fingerprint, explicit source id/SHA-256, exit timestamp, executable\n   exit price, exact quantity/multiplier and explicit exit fees;\n2. keep the exit evidence descriptive only—no broker/order/PAPER/LIVE authority and no\n   position mutation merely because an exit fill record exists;\n3. consume exact open-position + exit-fill lineage in a deterministic closeout state\n   that removes only the matched position and returns exact net exit proceeds to cash;\n4. distinguish account-state realized P&L from lifetime trade net P&L so previously\n   expensed entry fees are not double counted, and add replay/idempotency/tamper checks;\n5. only after lifecycle accounting is accepted, integrate the authoritative records into\n   browser observability and later broker/PAPER authority gates.'''
if old_next not in text:
    raise SystemExit("roadmap marked-account continuation list not found")
text = text.replace(old_next, new_next, 1)
roadmap.write_text(text, encoding="utf-8")
