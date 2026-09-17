from pathlib import Path

contract_fp = "c15c03400d61bf9e025f836118bf431178caadbdfc7c9a62826ec03796a0ee37"

section = f'''## 2026-09-16 — Deterministic open-position entry-book account state

Track A now adds `atlas-simulation-open-position-account-state-v1` under contract
`{contract_fp}`. It consumes one immutable accepted reservation-account snapshot plus
exact simulated entry-fill and funding/collateral evidence, then converts reservations
into deterministic **entry-book-value open positions**. The source reservation batch is
never rewritten: every fill and funding record remains bound to the exact account-state
fingerprint against which it was created, while the position layer tracks which source
reservations remain unconverted.

Each transition releases exactly one matching reservation and updates cash as
`current cash + released reservation - accepted required cash`. Cash is rechecked at
the moment of transition, so multiple fills that were individually affordable against
the same original unreserved-cash pool cannot spend those dollars twice. Same-fill
reapplication is idempotent; a different fill for an already-open decision fails
closed. Batch application is deterministic by `(filled_utc, fill_fingerprint)`, and
state/event/ledger fingerprints support exact replay verification and tamper detection.

Entry fees are expenses immediately: `entry book equity = initial equity - cumulative
entry fees`, while `cash + remaining reservations + open entry book value` must equal
that entry-book equity. Stock gross exposure transfers exactly from the reservation to
the cash-funded bullish stock position. Long-option premium paid becomes option entry
book value/premium at risk; the reservation's signed/absolute delta-equivalent exposure
is retained only as an **entry reference**, not a current Greek or mark. Stock shorts
remain unsupported because no accepted collateral/proceeds model exists.

This package deliberately stops before market valuation. It has no mark-to-market,
unrealized-P&L, realized-P&L, exit/closeout, provider/broker, order, PAPER, LIVE,
promotion or confluence authority. The next bounded Track A work is source-bound market
mark evidence and deterministic mark-to-market/unrealized-P&L state, followed by
exit/closeout and realized-P&L accounting. The Strategy Evidence Register remains
unchanged because this is product/account-simulation architecture only.
'''

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
old = '''The next bounded Track A package may now atomically convert an accepted reservation +
accepted fill + exact funding terms into deterministic open-position/cost-basis state,
with idempotent duplicate application and replay/tamper checks. Mark-to-market,
unrealized/realized P&L, exits/closeout, broker mutation and PAPER/LIVE authority remain
later gates. The Strategy Evidence Register is intentionally unchanged because this
package changes product simulation architecture only.'''
new = '''That funding boundary is now consumed by the deterministic open-position entry-book
account state described below. Mark-to-market, unrealized/realized P&L, exits/closeout,
broker mutation and PAPER/LIVE authority remain later gates. The Strategy Evidence
Register is intentionally unchanged because these packages change product simulation
architecture only.'''
if old not in text:
    raise SystemExit("README funding continuation paragraph not found")
text = text.replace(old, new, 1)
marker = "## A33/B33 reference foundation"
if marker not in text:
    raise SystemExit("README A33 insertion marker not found")
if "## 2026-09-16 — Deterministic open-position entry-book account state" not in text:
    text = text.replace(marker, section + "\n" + marker, 1)
readme.write_text(text, encoding="utf-8")

roadmap = Path("docs/roadmap.md")
text = roadmap.read_text(encoding="utf-8")
old_block = '''Immediate Track A continuation after acceptance:

1. consume exact reservation + fill + funding/collateral fingerprints in one
   deterministic open-position transition;
2. release only the exact reservation being converted, debit the exact accepted cash
   requirement, retain any explicit unspent reserve, and preserve instrument-specific
   quantity/cost-basis/exposure lineage;
3. make duplicate fill application idempotent and ledger replay/tamper checks exact;
4. continue to reject stock shorts until a separately versioned collateral/proceeds
   model exists; and
5. leave mark-to-market, unrealized/realized P&L, exits/closeout and PAPER/LIVE broker
   authority to separately accepted packages.'''
new_block = '''Immediate Track A continuation after acceptance:

1. freeze source-bound stock/option market-mark evidence with explicit provider/feed,
   market timestamp, receive timestamp, freshness and transport provenance;
2. apply deterministic mark-to-market and unrealized-P&L accounting to the accepted
   open-position state without treating stale/unknown marks as valuation truth;
3. preserve entry cost basis, paid fees and entry-reference option delta separately
   from current market marks/Greeks;
4. only after valuation semantics are accepted, add deterministic exits/closeout and
   realized-P&L accounting with replay/idempotency checks; and
5. keep provider/broker mutation, orders, PAPER/LIVE, promotion and confluence under
   their separate authority gates.'''
if old_block not in text:
    raise SystemExit("roadmap immediate open-position continuation block not found")
text = text.replace(old_block, new_block, 1)
anchor = '''The Strategy Evidence Register is intentionally unchanged because this package changes
product simulation architecture only.'''
if anchor not in text:
    raise SystemExit("roadmap funding-section anchor not found")
roadmap_section = section.replace(
    "## 2026-09-16 — Deterministic open-position entry-book account state",
    "## Track A open-position entry-book account state — 2026-09-16",
    1,
)
if "## Track A open-position entry-book account state — 2026-09-16" not in text:
    text = text.replace(anchor, anchor + "\n\n" + roadmap_section, 1)
roadmap.write_text(text, encoding="utf-8")
