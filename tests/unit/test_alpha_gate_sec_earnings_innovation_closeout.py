from __future__ import annotations

from packages.backtesting.alpha_gate_sec_earnings_innovation_closeout import (
    EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT,
    _metadata_signature,
    _period_signature,
    earnings_innovation_closeout_fingerprint,
)


def test_closeout_fingerprint_is_frozen() -> None:
    assert earnings_innovation_closeout_fingerprint() == EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT


def test_period_signature_preserves_ambiguous_semantics() -> None:
    row = {
        "issuer_cik": "0001758488",
        "period_end": "2019-06-30",
        "earliest_accession": "0001193125-19-222179",
        "earliest_semantics": [
            ["2019-04-01", "2019-06-30", 0.05],
            ["2019-03-21", "2019-06-30", -0.31],
        ],
    }
    assert _period_signature(row) == (
        "0001758488",
        "2019-06-30",
        "0001193125-19-222179",
        (("2019-03-21", "2019-06-30", -0.31), ("2019-04-01", "2019-06-30", 0.05)),
    )


def test_metadata_signature_preserves_exact_fact_form_and_date_contradiction() -> None:
    row = {
        "issuer_cik": "0001173313",
        "accession_number": "0001213900-17-005701",
        "companyfacts_form": "10-Q",
        "companyfacts_filed": "2017-05-22",
        "submissions_form": "10-Q/A",
        "submissions_filing_date": "2017-05-22",
        "companyfacts_row": {
            "start": "2015-10-01",
            "end": "2015-12-31",
            "val": -0.02,
        },
    }
    assert _metadata_signature(row) == (
        "0001173313",
        "0001213900-17-005701",
        "2015-12-31",
        "2015-10-01",
        -0.02,
        "10-Q",
        "2017-05-22",
        "10-Q/A",
        "2017-05-22",
    )
