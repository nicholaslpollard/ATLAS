from __future__ import annotations

import pytest

from packages.backtesting.phase32_predictor_acquisition import (
    Phase32PredictorAcquisitionError,
    _reconcile_massive_text_filing_entity_rows,
)
from scripts.run_phase32_predictor_acquisition import _print_progress


ACCESSION = "0001140361-26-029471"
CIK = "0002017526"
BASE = {
    "accession_number": ACCESSION,
    "cik": CIK,
    "filing_date": "2026-07-24",
    "form_type": "8-K",
    "filing_url": "https://www.sec.gov/Archives/edgar/data/2017526/0001140361-26-029471.txt",
    "items_text": "same authoritative filing text",
}


def test_ticker_only_massive_text_multiplicity_is_preserved() -> None:
    frnm = dict(BASE, ticker="FRNM")
    pcsc = dict(BASE, ticker="PCSC")

    evidence = _reconcile_massive_text_filing_entity_rows(
        [frnm, pcsc], accession=ACCESSION, issuer_cik=CIK
    )

    assert evidence["row_count"] == 2
    assert evidence["tickers"] == ["FRNM", "PCSC"]
    assert len(evidence["aggregate_sha256"]) == 64
    assert len(evidence["non_ticker_sha256"]) == 64


def test_massive_text_multiplicity_fails_closed_on_non_ticker_conflict() -> None:
    first = dict(BASE, ticker="FRNM")
    second = dict(BASE, ticker="PCSC", items_text="conflicting filing text")

    with pytest.raises(
        Phase32PredictorAcquisitionError,
        match="Massive Text rows conflict beyond ticker",
    ):
        _reconcile_massive_text_filing_entity_rows(
            [first, second], accession=ACCESSION, issuer_cik=CIK
        )


def test_massive_text_multiplicity_requires_at_least_one_row() -> None:
    with pytest.raises(
        Phase32PredictorAcquisitionError,
        match="requires at least one Massive Text row",
    ):
        _reconcile_massive_text_filing_entity_rows([], accession=ACCESSION, issuer_cik=CIK)


def test_progress_output_is_lightweight_and_periodic(capsys: pytest.CaptureFixture[str]) -> None:
    for completed in range(1, 101):
        _print_progress(completed, 100)
    output = capsys.readouterr().out.splitlines()
    assert output[0] == "Phase32 progress: 1 / 100 filing entities completed"
    assert output[-1] == "Phase32 progress: 100 / 100 filing entities completed"
    assert len(output) <= 22
