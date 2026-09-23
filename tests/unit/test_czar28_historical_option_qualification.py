from __future__ import annotations

from packages.data.czar28_historical_option_qualification import (
    ProbeBudget,
    representative_contracts,
    standard_monthly_expiration,
)


def test_standard_monthly_expiration_is_third_friday() -> None:
    assert standard_monthly_expiration(2016, 6).isoformat() == "2016-06-17"
    assert standard_monthly_expiration(2020, 6).isoformat() == "2020-06-19"
    assert standard_monthly_expiration(2026, 6).isoformat() == "2026-06-19"


def test_representative_contracts_selects_median_call_and_put() -> None:
    payload = {
        "header": {
            "format": ["root", "expiration", "strike", "right"],
        },
        "response": [
            ["AAPL", 20260619, 150000, "C"],
            ["AAPL", 20260619, 200000, "C"],
            ["AAPL", 20260619, 250000, "C"],
            ["AAPL", 20260619, 150000, "P"],
            ["AAPL", 20260619, 200000, "P"],
            ["AAPL", 20260619, 250000, "P"],
        ],
    }

    assert representative_contracts(payload) == (
        {
            "root": "AAPL",
            "exp": "20260619",
            "strike": "200",
            "right": "C",
        },
        {
            "root": "AAPL",
            "exp": "20260619",
            "strike": "200",
            "right": "P",
        },
    )


def test_probe_budget_honors_provider_remaining_zero() -> None:
    now = [0.0]

    def clock() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    budget = ProbeBudget(
        max_requests=10,
        requests_per_minute=10,
        clock=clock,
        sleep=sleep,
    )
    assert budget.can_request()
    budget.before_request()
    assert budget.request_attempts == 1

    budget.observe_headers(
        {
            "X-RateLimit-Limit": "1000",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Limit-Minute": "60",
            "X-RateLimit-Burst": "20",
        }
    )
    assert budget.provider_limit == 1000
    assert budget.provider_remaining == 0
    assert budget.provider_minute_limit == 60
    assert budget.provider_burst == 20
    assert not budget.can_request()


def test_probe_budget_halt_is_fail_closed() -> None:
    budget = ProbeBudget(max_requests=10, requests_per_minute=10)
    assert budget.can_request()
    budget.halt()
    assert not budget.can_request()
