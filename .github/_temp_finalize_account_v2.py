from pathlib import Path

OLD_FP = "7fa699bde64aaed1bb3423f0c0ea59d45a72aabe0ce4301937b03d2fe2fc9be6"
NEW_FP = "1e9da000571d02eb8fe4d317d770fdef25fb35a527ad177d1a87a6794c9592e5"

# Keep the frozen contract test aligned with the clarified contract identity.
test_path = Path("tests/test_simulation_account_state_v2.py")
test_text = test_path.read_text(encoding="utf-8")
if test_text.count(OLD_FP) != 1:
    raise SystemExit(f"expected one old v2 contract fingerprint in test, found {test_text.count(OLD_FP)}")
test_text = test_text.replace(OLD_FP, NEW_FP, 1)
needle = '    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["leverage_inference"] is False\n'
insert = (
    needle
    + '    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["stock_accounting_arithmetic_reuses_v1"] is True\n'
    + '    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["stock_candidate_fingerprint_lineage_required"] is True\n'
)
if needle not in test_text:
    raise SystemExit("contract assertion insertion point missing")
if "stock_accounting_arithmetic_reuses_v1" not in test_text:
    test_text = test_text.replace(needle, insert, 1)
test_path.write_text(test_text, encoding="utf-8")

README_MARKER = "## 2026-09-16 — Stock-option simulation account-state v2"
README_SECTION = r'''

## 2026-09-16 — Stock-option simulation account-state v2

Track A now has a broker-neutral reservation-only account model for both stock and
accepted long-option expressions under frozen contract fingerprint
`1e9da000571d02eb8fe4d317d770fdef25fb35a527ad177d1a87a6794c9592e5`
(`atlas-simulation-account-state-v2-stock-option-reservations`). The accepted v1
stock-accounting arithmetic is preserved, while v2 strengthens stock lineage by
requiring the exact chosen-candidate fingerprint. Option admission additionally
requires the separately accepted long-option reservation terms and their exact
decision, candidate, forecast, economics, and option-evidence lineage.

The state uses one unreserved-cash pool but never conflates instrument economics.
Stock reserved capital and stock gross notional remain separate from option reserved
capital, signed/absolute option delta-equivalent notional, option max-loss cash, and
option premium at risk. Reservation-only equity remains invariant and every state
must satisfy `cash + stock_reserved_capital + option_reserved_capital == equity`.
Missing option terms and insufficient unreserved cash fail closed. Releasing a stock
or option reservation restores exactly the reserved cash and exposure fields; it does
not invent a fill, gain/loss, mark, margin, collateral, or leverage event.

The mixed stock/option ledger is deterministic, chronological, idempotent,
fingerprint-linked, and replayable. Reservation and release events preserve exact
decision and, for options, reservation-terms/economics lineage. Stock gross notional
never includes option exposure, and option delta-equivalent exposure is never
reinterpreted as stock notional. No provider/broker reads or writes, order creation,
fill simulation, mark-to-market, realized P&L, PAPER, LIVE, promotion, or confluence
authority is granted.

The next bounded Track A package is deterministic broker-neutral simulated
execution/fill semantics. It may consume accepted reservation state and explicit fill
evidence, but mark-to-market, realized-P&L, and broker/PAPER/LIVE authority remain
separate later gates. The Strategy Evidence Register is intentionally unchanged
because this package changes product simulation architecture only.
'''

ROADMAP_MARKER = "## Track A stock-option simulation account-state v2 — 2026-09-16"
ROADMAP_SECTION = r'''

## Track A stock-option simulation account-state v2 — 2026-09-16

The reservation-only mixed-instrument account boundary is frozen under contract
`1e9da000571d02eb8fe4d317d770fdef25fb35a527ad177d1a87a6794c9592e5`
(`atlas-simulation-account-state-v2-stock-option-reservations`). It extends the
accepted account-state foundation without altering the historical v1 contract.

Frozen v2 semantics:

1. preserve the accepted v1 stock reservation arithmetic while strengthening chosen
   stock candidate lineage with an exact economic-candidate fingerprint check;
2. require exact accepted long-option reservation terms before any OPTION decision
   can reserve account capital;
3. use one unreserved-cash pool while tracking stock reserved capital, option reserved
   capital, stock gross notional, option signed/absolute delta-equivalent notional,
   option max-loss cash, and option premium-at-risk separately;
4. require `cash + stock_reserved_capital + option_reserved_capital == equity` and
   keep equity invariant throughout reservation-only state transitions;
5. fail closed on missing option terms, insufficient unreserved cash, contract or
   candidate lineage mismatch, backward chronology, or malformed state/ledger data;
6. make repeated decision applications and repeated releases idempotent, with
   deterministic competition ordering by decision timestamp then record fingerprint;
7. release exactly the previously reserved stock or option cash/exposure amounts
   without inventing fills, marks, or P&L;
8. provide deterministic state, event, and ledger fingerprints plus replay checks for
   chronology, before/after state lineage, and reservation/release integrity;
9. never fold option delta-equivalent exposure into stock gross notional; and
10. infer no margin, collateral, or leverage and grant no provider/broker, order,
    fill, mark-to-market, realized-P&L, PAPER, LIVE, promotion, or confluence authority.

Immediate Track A continuation after acceptance:

1. freeze explicit stock and option simulated-fill evidence contracts;
2. consume only accepted reservation/decision lineage and caller-supplied execution
   evidence, with no provider or broker lookup inside the fill engine;
3. transition reserved capital into deterministic open-position/cost-basis state while
   retaining instrument-specific stock versus option quantities and exposure lineage;
4. make duplicate fill application idempotent and ledger replay/tamper checks exact;
   and
5. leave mark-to-market, realized P&L, closeout accounting, and PAPER/LIVE broker
   authority to separately accepted packages.

The Strategy Evidence Register remains unchanged because this package changes
product/account-simulation architecture only.
'''


def append_once(path: str, marker: str, section: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker not in text:
        target.write_text(text.rstrip() + section + "\n", encoding="utf-8")


append_once("README.md", README_MARKER, README_SECTION)
append_once("docs/roadmap.md", ROADMAP_MARKER, ROADMAP_SECTION)
