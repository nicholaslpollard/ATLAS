from __future__ import annotations

from packages.backtesting.alpha_gate_xbrl_predictor import (
    _feature_signals,
    _flow_quarter_value,
    reconstruct_issuer_quarters,
)


def _flow_row(*, tag: str, start: str, end: str, value: float) -> dict[str, object]:
    return {
        "tag": tag,
        "unit": "USD",
        "start": start,
        "end": end,
        "val": value,
    }


def test_q2_ytd_is_incrementalized_against_prior_public_q1() -> None:
    rows = (
        _flow_row(
            tag="NetIncomeLoss",
            start="2024-01-01",
            end="2024-06-30",
            value=150.0,
        ),
    )
    quarter, ytd, method = _flow_quarter_value(
        rows,
        tag="NetIncomeLoss",
        end=__import__("datetime").date(2024, 6, 30),
        fy=2024,
        quarter=2,
        ytd_history={(2024, 1, "NetIncomeLoss"): 60.0},
        quarter_history={},
    )
    assert quarter == 90.0
    assert ytd == 150.0
    assert method == "YTD_MINUS_PRIOR_YTD"


def test_q4_annual_is_incrementalized_against_public_q1_q2_q3() -> None:
    rows = (
        _flow_row(
            tag="NetIncomeLoss",
            start="2024-01-01",
            end="2024-12-31",
            value=400.0,
        ),
    )
    quarter, annual, method = _flow_quarter_value(
        rows,
        tag="NetIncomeLoss",
        end=__import__("datetime").date(2024, 12, 31),
        fy=2024,
        quarter=4,
        ytd_history={},
        quarter_history={
            (2024, 1, "NetIncomeLoss"): 80.0,
            (2024, 2, "NetIncomeLoss"): 90.0,
            (2024, 3, "NetIncomeLoss"): 100.0,
        },
    )
    assert quarter == 130.0
    assert annual == 400.0
    assert method == "FY_MINUS_Q1_Q2_Q3"


def test_feature_signals_match_only_frozen_yoy_signs() -> None:
    row = {
        "fiscal_year": 2024,
        "fiscal_quarter": 2,
        "gross_profitability": 0.20,
        "cash_profitability": 0.05,
        "accrual_intensity": 0.02,
    }
    prior = {
        (2023, 2, "gross_profitability"): 0.10,
        (2023, 2, "cash_profitability"): 0.10,
        (2023, 2, "accrual_intensity"): 0.05,
    }
    signals = _feature_signals(row, prior)
    assert [item["candidate_id"] for item in signals] == [
        "gross_profitability_improvement_long",
        "cash_profitability_deterioration_short",
        "accrual_quality_improvement_long",
    ]


def test_first_public_fiscal_period_version_is_not_overwritten() -> None:
    first_rows = (
        {
            "tag": "Assets",
            "unit": "USD",
            "start": None,
            "end": "2024-03-31",
            "filed": "2024-05-01",
            "form": "10-Q",
            "accn": "0000000000-24-000001",
            "fy": 2024,
            "fp": "Q1",
            "frame": None,
            "val": 100.0,
        },
    )
    later_rows = (
        {
            **first_rows[0],
            "filed": "2024-05-10",
            "accn": "0000000000-24-000002",
            "val": 101.0,
        },
    )
    rows, diagnostics = reconstruct_issuer_quarters(
        issuer_cik="0000000001",
        entity_name="Example",
        accession_rows=(
            (
                {
                    "form": "10-Q",
                    "filing_date": "2024-05-01",
                    "acceptance_datetime": "2024-05-01T16:30:00-04:00",
                    "accession_number": "0000000000-24-000001",
                },
                first_rows,
            ),
            (
                {
                    "form": "10-Q",
                    "filing_date": "2024-05-10",
                    "acceptance_datetime": "2024-05-10T16:30:00-04:00",
                    "accession_number": "0000000000-24-000002",
                },
                later_rows,
            ),
        ),
    )
    assert len(rows) == 1
    assert rows[0]["accession_number"] == "0000000000-24-000001"
    assert diagnostics["later_same_fiscal_period_accessions_excluded"] == 1
