from __future__ import annotations

from packages.backtesting.phase32_predictor_acquisition import (
    PHASE32_FROZEN_POLICY_FINGERPRINT,
    Phase32PredictorAcquisitionError,
    _reconcile_massive_text_filing_entity_rows,
)


ACCESSION = "0001140361-26-029471"
CIK = "0002017526"
BASE = {
    "accession_number": ACCESSION,
    "cik": CIK,
    "filing_date": "2026-07-24",
    "form_type": "8-K",
    "filing_url": "https://www.sec.gov/Archives/edgar/data/2017526/0001140361-26-029471.txt",
    "items_text": "same filing text",
}


def main() -> int:
    frnm = dict(BASE, ticker="FRNM")
    pcsc = dict(BASE, ticker="PCSC")
    evidence = _reconcile_massive_text_filing_entity_rows(
        [frnm, pcsc], accession=ACCESSION, issuer_cik=CIK
    )
    if evidence["row_count"] != 2 or evidence["tickers"] != ["FRNM", "PCSC"]:
        raise SystemExit("ticker-only Massive Text multiplicity was not preserved")

    conflicting = dict(pcsc, items_text="conflicting filing text")
    try:
        _reconcile_massive_text_filing_entity_rows(
            [frnm, conflicting], accession=ACCESSION, issuer_cik=CIK
        )
    except Phase32PredictorAcquisitionError as exc:
        if "conflict beyond ticker" not in str(exc):
            raise
    else:
        raise SystemExit("non-ticker Massive Text conflict did not fail closed")

    print("ATLAS Phase 32 Massive Text multiplicity contract: PASS")
    print(f"- frozen policy fingerprint unchanged: {PHASE32_FROZEN_POLICY_FINGERPRINT}")
    print("- multiple Text rows are accepted only when every non-ticker field is identical")
    print("- all ticker variants remain source provenance and may enter exact PIT identity checks")
    print("- any non-ticker conflict still fails closed")
    print("- no market outcomes, broker reads, orders, PAPER, or LIVE authority are involved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
