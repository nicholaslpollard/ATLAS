from datetime import datetime, time
from zoneinfo import ZoneInfo

from packages.data import marketdata_massive_sparse_activity_v1 as sparse


EASTERN = ZoneInfo("America/New_York")
CONTRACT = sparse.CONTRACT


def _epoch_seconds(date_text: str) -> int:
    d = datetime.fromisoformat(date_text).date()
    return int(datetime.combine(d, time(16, 0), tzinfo=EASTERN).timestamp())


def _epoch_millis(date_text: str) -> int:
    d = datetime.fromisoformat(date_text).date()
    return int(datetime.combine(d, time(0, 0), tzinfo=EASTERN).timestamp() * 1000)


def test_sparse_sample_is_disjoint_from_prior_cross_provider_evidence() -> None:
    roots = {item["root"] for item in CONTRACT["anchors"]}
    dates = {item["date"] for item in CONTRACT["anchors"]}
    assert len(roots) == 12
    assert len(dates) == 12
    assert roots.isdisjoint(set(CONTRACT["excluded_prior_roots"]))
    assert dates.isdisjoint(set(CONTRACT["excluded_prior_dates"]))


def test_sparse_selector_uses_farthest_otm_not_volume() -> None:
    rows = (
        {
            "side": "call",
            "optionSymbol": "TEST1",
            "strike": 101,
            "underlyingPrice": 100,
            "volume": 0,
        },
        {
            "side": "call",
            "optionSymbol": "TEST2",
            "strike": 120,
            "underlyingPrice": 100,
            "volume": 999,
        },
        {
            "side": "call",
            "optionSymbol": "TEST3",
            "strike": 110,
            "underlyingPrice": 100,
            "volume": 1,
        },
    )
    selected = sparse._choose_sparse_contract(rows)
    assert selected is not None
    assert selected["optionSymbol"] == "TEST2"


def test_activity_records_accept_zero_absent_and_positive_present() -> None:
    md = (
        {"updated": _epoch_seconds("2026-01-05"), "volume": 0, "last": 1.0},
        {"updated": _epoch_seconds("2026-01-06"), "volume": 5, "last": 1.1},
    )
    massive = [{"t": _epoch_millis("2026-01-06"), "v": 5}]
    result = sparse._activity_records(md, massive)
    assert result["extra_massive_dates"] == []
    assert [row["concordant"] for row in result["records"]] == [True, True]


def test_activity_records_reject_zero_present_and_positive_absent() -> None:
    md = (
        {"updated": _epoch_seconds("2026-01-05"), "volume": 0, "last": 1.0},
        {"updated": _epoch_seconds("2026-01-06"), "volume": 5, "last": 1.1},
    )
    massive = [{"t": _epoch_millis("2026-01-05"), "v": 0}]
    result = sparse._activity_records(md, massive)
    dispositions = {row["disposition"] for row in result["records"]}
    assert "ZERO_VOLUME_WITH_MASSIVE_BAR" in dispositions
    assert "POSITIVE_VOLUME_MISSING_MASSIVE_BAR" in dispositions


def test_sparse_gate_requires_support_across_multiple_anchors() -> None:
    anchors = []
    for index in range(12):
        records = []
        if index < 3:
            records.extend(
                {
                    "date": f"2026-01-{index + 1:02d}",
                    "marketdata_volume": 0,
                    "concordant": True,
                    "disposition": "ZERO_VOLUME_WITHOUT_MASSIVE_BAR",
                }
                for _ in range(4)
            )
        records.extend(
            {
                "date": f"2026-02-{index + 1:02d}",
                "marketdata_volume": 1,
                "concordant": True,
                "disposition": "POSITIVE_VOLUME_WITH_MASSIVE_BAR",
            }
            for _ in range(2)
        )
        anchors.append(
            {
                "status": "DIAGNOSED",
                "marketdata_quote_rows": len(records),
                "activity_records": records,
                "extra_massive_dates": [],
            }
        )
    summary = sparse._summarize(anchors)
    checks = sparse._checks(anchors, summary)
    assert summary["zero_volume_sessions"] == 12
    assert summary["zero_volume_anchor_count"] == 3
    assert summary["positive_volume_sessions"] == 24
    assert all(checks.values())


def test_sparse_gate_does_not_grant_price_authority() -> None:
    authority = CONTRACT["authority_if_passed"]
    assert authority["marketdata_massive_sparse_activity_concordance_confirmed"] is True
    assert authority["marketdata_zero_volume_last_validated"] is False
    assert authority["marketdata_positive_volume_eod_last_volume_semantics_validated"] is False
    assert authority["execution_price_authority"] is False
