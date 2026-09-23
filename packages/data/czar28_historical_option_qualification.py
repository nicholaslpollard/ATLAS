from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.provider_source_qualification import stable_fingerprint
from packages.providers.czar28.client import (
    CZAR28_CREDENTIAL_ENV,
    Czar28Error,
    Czar28QuotaExhausted,
    Czar28Response,
    get_json,
)


QUALIFICATION_ROOTS: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "AAPL",
    "MSFT",
    "AMZN",
    "GOOG",
    "GOOGL",
    "NVDA",
    "AMD",
    "INTC",
    "IBM",
    "ORCL",
    "CSCO",
    "JPM",
    "BAC",
    "GS",
    "XOM",
    "CVX",
    "WMT",
    "COST",
    "HD",
    "MCD",
    "KO",
    "PEP",
    "JNJ",
    "PFE",
    "DIS",
    "BA",
)
ANCHOR_YEARS: tuple[int, ...] = tuple(range(2016, 2027))
MAX_FREE_REQUESTS = 1000
MAX_QUALIFICATION_RPM = 55
CHAIN_PROBE_TARGET = len(QUALIFICATION_ROOTS) * len(ANCHOR_YEARS)
EOD_PROBE_TARGET = 520
INTRADAY_PROBE_TARGET = 50
TRADE_PROBE_TARGET = 50
CHAIN_REPEAT_TARGET = 25
EOD_REPEAT_TARGET = 25


CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT = {
    "contract_id": "atlas-czar28-historical-option-source-qualification-v1",
    "provider": "czar28_publicoptions",
    "credential_env": CZAR28_CREDENTIAL_ENV,
    "purpose": (
        "read-only qualification of Czar28 as a candidate historical US equity "
        "option source for the stock-aligned 2016-2026 ATLAS research horizon"
    ),
    "documented_provider_claims_frozen_2026_09_23": {
        "history": "12y+",
        "ticker_count": "5.2k",
        "free_monthly_requests": MAX_FREE_REQUESTS,
        "free_requests_per_minute": 60,
        "free_burst": 20,
        "endpoints": [
            "/options/chain",
            "/options/quote/eod",
            "/options/quote/intraday",
            "/options/trades",
        ],
    },
    "local_safety": {
        "max_provider_calls_per_run": MAX_FREE_REQUESTS,
        "qualification_requests_per_minute": MAX_QUALIFICATION_RPM,
        "never_exceed_observed_provider_remaining": True,
        "stop_on_provider_remaining_zero": True,
        "stop_on_http_429": True,
        "persist_each_response_before_next_dependent_probe": True,
        "idempotency_key_per_logical_probe": True,
        "credential_never_persisted": True,
    },
    "probe_matrix": {
        "roots": list(QUALIFICATION_ROOTS),
        "anchor_years": list(ANCHOR_YEARS),
        "anchor_expiration": "June standard monthly third-Friday expiration",
        "chain_target": CHAIN_PROBE_TARGET,
        "eod_target": EOD_PROBE_TARGET,
        "intraday_target": INTRADAY_PROBE_TARGET,
        "trades_target": TRADE_PROBE_TARGET,
        "intentional_chain_repeat_target": CHAIN_REPEAT_TARGET,
        "intentional_eod_repeat_target": EOD_REPEAT_TARGET,
        "fallback_fill": (
            "unused representative EOD contracts, then March/September monthly "
            "chain probes, until provider quota or local 1000-call ceiling is reached"
        ),
    },
    "selection": {
        "chain_contract": (
            "for each non-empty chain select median-strike call and median-strike put; "
            "selection is structural only and does not claim ATM/delta equivalence"
        ),
        "eod_window_days_before_expiration": 90,
        "intraday_and_trades_date": "last returned EOD trading date for that contract",
        "intraday_interval_ms": 60_000,
        "intraday_rth": True,
    },
    "acceptance_scope": {
        "measure_historical_depth": True,
        "measure_symbol_breadth": True,
        "measure_chain_identity": True,
        "measure_eod_presence_and_schema": True,
        "measure_intraday_presence_and_schema": True,
        "measure_trade_presence_and_schema": True,
        "measure_repeat_stability": True,
        "cross_provider_price_acceptance": False,
        "historical_data_authority": False,
        "strategy_evidence": False,
    },
    "authority": {
        "provider_reads": True,
        "provider_writes": False,
        "broker_reads": False,
        "broker_writes": False,
        "order_creation": False,
        "paper": False,
        "live": False,
        "promotion": False,
        "strategy_outcome_access": False,
    },
}


CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT_FINGERPRINT = (
    stable_fingerprint(CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT)
)


class Czar28QualificationError(RuntimeError):
    pass


class Czar28LocalBudgetExhausted(Czar28QualificationError):
    pass


@dataclass
class ProbeBudget:
    max_requests: int
    requests_per_minute: int
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        if not 1 <= self.max_requests <= MAX_FREE_REQUESTS:
            raise ValueError(f"max_requests must be within 1..{MAX_FREE_REQUESTS}")
        if not 1 <= self.requests_per_minute <= MAX_QUALIFICATION_RPM:
            raise ValueError(
                f"requests_per_minute must be within 1..{MAX_QUALIFICATION_RPM}"
            )
        self.minimum_interval_seconds = 60.0 / float(self.requests_per_minute)
        self.request_attempts = 0
        self.provider_limit: int | None = None
        self.provider_remaining: int | None = None
        self.provider_reset: str | None = None
        self.provider_minute_limit: int | None = None
        self.provider_burst: int | None = None
        self._next_start = 0.0
        self.halted = False

    def can_request(self) -> bool:
        return (
            not self.halted
            and self.request_attempts < self.max_requests
            and self.provider_remaining != 0
        )

    def halt(self) -> None:
        self.halted = True

    def before_request(self) -> None:
        if not self.can_request():
            raise Czar28LocalBudgetExhausted("Czar28 qualification budget exhausted")
        now = self.clock()
        wait = max(0.0, self._next_start - now)
        if wait > 0:
            self.sleep(wait)
        now = self.clock()
        self._next_start = now + self.minimum_interval_seconds
        self.request_attempts += 1

    def observe_headers(self, headers: dict[str, str]) -> None:
        lowered = {str(k).lower(): str(v) for k, v in headers.items()}

        def parse_int(name: str) -> int | None:
            raw = lowered.get(name)
            if raw is None:
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        limit = parse_int("x-ratelimit-limit")
        remaining = parse_int("x-ratelimit-remaining")
        minute = parse_int("x-ratelimit-limit-minute")
        burst = parse_int("x-ratelimit-burst")
        if limit is not None:
            self.provider_limit = limit
        if remaining is not None:
            self.provider_remaining = max(0, remaining)
        if minute is not None:
            self.provider_minute_limit = minute
        if burst is not None:
            self.provider_burst = burst
        if lowered.get("x-ratelimit-reset"):
            self.provider_reset = lowered["x-ratelimit-reset"]


def standard_monthly_expiration(year: int, month: int) -> date:
    current = date(year, month, 1)
    first_friday_offset = (4 - current.weekday()) % 7
    first_friday = current + timedelta(days=first_friday_offset)
    return first_friday + timedelta(days=14)


def _stable_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe_id(descriptor: dict[str, object]) -> str:
    return stable_fingerprint(descriptor)


def _rows(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    header = payload.get("header")
    response = payload.get("response")
    if not isinstance(header, dict) or not isinstance(response, list):
        return ()
    columns = header.get("format")
    if not isinstance(columns, list) or any(not isinstance(x, str) for x in columns):
        return ()
    result: list[dict[str, Any]] = []
    for raw in response:
        if not isinstance(raw, list) or len(raw) != len(columns):
            continue
        result.append(dict(zip(columns, raw, strict=True)))
    return tuple(result)


def _filtered_response_headers(headers: dict[str, str]) -> dict[str, str]:
    keep = {
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "x-ratelimit-limit-minute",
        "x-ratelimit-burst",
        "retry-after",
        "api-version",
        "idempotent-replayed",
        "content-type",
    }
    return {
        str(k): str(v)
        for k, v in headers.items()
        if str(k).lower() in keep
    }


def _qualification_root(settings: AtlasSettings) -> Path:
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "czar28"
        / "historical_options_v1"
    )


def _load_completed_qualification(root: Path) -> dict[str, object] | None:
    completion_path = root / "completion.json"
    if not completion_path.exists():
        return None
    try:
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
        if (
            completion.get("status") != "COMPLETE"
            or completion.get("contract_fingerprint")
            != CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT_FINGERPRINT
        ):
            return None
        report_name = str(completion.get("report_name") or "")
        if not report_name:
            return None
        report_path = root / "reports" / report_name
        if not report_path.exists():
            return None
        if completion.get("report_sha256") != _sha256_file(report_path):
            return None
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("evidence_fingerprint") != completion.get("evidence_fingerprint"):
            return None
        report["report_path"] = str(report_path.resolve())
        report["reused_completed_qualification"] = True
        return report
    except Exception:
        return None


def _persist_probe(
    root: Path,
    *,
    descriptor: dict[str, object],
    response: Czar28Response,
) -> dict[str, object]:
    probe_id = _probe_id(descriptor)
    probe_dir = root / "probes"
    probe_dir.mkdir(parents=True, exist_ok=True)
    raw_path = probe_dir / f"{probe_id}.json.gz"
    receipt_path = probe_dir / f"{probe_id}.receipt.json"

    envelope = {
        "descriptor": descriptor,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "http_status": response.http_status,
        "headers": _filtered_response_headers(response.headers),
        "response_bytes": response.response_bytes,
        "elapsed_seconds": response.elapsed_seconds,
        "payload": response.payload,
    }
    raw_bytes = _stable_json_bytes(envelope)
    compressed = gzip.compress(raw_bytes, compresslevel=6, mtime=0)
    raw_tmp = raw_path.with_suffix(raw_path.suffix + ".tmp")
    raw_tmp.write_bytes(compressed)
    os.replace(raw_tmp, raw_path)
    raw_sha256 = _sha256_file(raw_path)

    rows = _rows(response.payload)
    receipt = {
        "status": "COMPLETE",
        "contract_fingerprint": (
            CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT_FINGERPRINT
        ),
        "probe_id": probe_id,
        "descriptor": descriptor,
        "http_status": response.http_status,
        "row_count": len(rows),
        "raw_path": str(raw_path.resolve()),
        "raw_sha256": raw_sha256,
        "response_bytes": response.response_bytes,
        "elapsed_seconds": response.elapsed_seconds,
        "rate_limit": _filtered_response_headers(response.headers),
        "payload_fingerprint": stable_fingerprint(response.payload),
    }
    atomic_write_text(
        receipt_path,
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    )
    return receipt


def _load_reusable_probe(
    root: Path,
    descriptor: dict[str, object],
) -> tuple[dict[str, object], dict[str, Any]] | None:
    probe_id = _probe_id(descriptor)
    probe_dir = root / "probes"
    raw_path = probe_dir / f"{probe_id}.json.gz"
    receipt_path = probe_dir / f"{probe_id}.receipt.json"
    if not raw_path.exists() or not receipt_path.exists():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            receipt.get("status") != "COMPLETE"
            or receipt.get("contract_fingerprint")
            != CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT_FINGERPRINT
            or receipt.get("probe_id") != probe_id
            or receipt.get("descriptor") != descriptor
            or receipt.get("raw_sha256") != _sha256_file(raw_path)
        ):
            return None
        envelope = json.loads(gzip.decompress(raw_path.read_bytes()).decode("utf-8"))
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            return None
        if stable_fingerprint(payload) != receipt.get("payload_fingerprint"):
            return None
        return receipt, payload
    except Exception:
        return None


def _strike_dollars(raw: object) -> str | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    rendered = f"{value / 1000.0:.3f}".rstrip("0").rstrip(".")
    return rendered if rendered else "0"


def representative_contracts(payload: dict[str, Any]) -> tuple[dict[str, str], ...]:
    rows = _rows(payload)
    selected: list[dict[str, str]] = []
    for right in ("C", "P"):
        candidates = [
            row
            for row in rows
            if str(row.get("right") or "").upper() == right
            and _strike_dollars(row.get("strike")) is not None
        ]
        candidates.sort(key=lambda row: int(row["strike"]))
        if not candidates:
            continue
        row = candidates[len(candidates) // 2]
        strike = _strike_dollars(row.get("strike"))
        if strike is None:
            continue
        selected.append(
            {
                "root": str(row.get("root") or "").upper(),
                "exp": str(row.get("expiration") or ""),
                "strike": strike,
                "right": right,
            }
        )
    return tuple(selected)


def _last_eod_date(payload: dict[str, Any]) -> str | None:
    dates: list[int] = []
    for row in _rows(payload):
        raw = row.get("date")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if 19000101 <= value <= 29991231:
            dates.append(value)
    return str(max(dates)) if dates else None


def _descriptor(
    kind: str,
    params: dict[str, object],
    *,
    role: str,
    repeat_index: int = 0,
) -> dict[str, object]:
    return {
        "kind": kind,
        "role": role,
        "repeat_index": repeat_index,
        "params": {str(k): str(v) for k, v in sorted(params.items())},
    }


def _call_probe(
    root: Path,
    budget: ProbeBudget,
    descriptor: dict[str, object],
    *,
    request_json: Callable[..., Czar28Response],
) -> tuple[dict[str, object], dict[str, Any], bool]:
    reusable = _load_reusable_probe(root, descriptor)
    if reusable is not None:
        receipt, payload = reusable
        return receipt, payload, True

    budget.before_request()
    kind = str(descriptor["kind"])
    params = dict(descriptor["params"])
    path_by_kind = {
        "chain": "options/chain",
        "eod": "options/quote/eod",
        "intraday": "options/quote/intraday",
        "trades": "options/trades",
    }
    try:
        response = request_json(
            path_by_kind[kind],
            params=params,
            idempotency_key=_probe_id(descriptor),
        )
    except Czar28QuotaExhausted:
        budget.provider_remaining = 0
        raise

    budget.observe_headers(response.headers)
    receipt = _persist_probe(root, descriptor=descriptor, response=response)
    return receipt, response.payload, False


def _chain_descriptors(month: int = 6) -> tuple[dict[str, object], ...]:
    result: list[dict[str, object]] = []
    for year in ANCHOR_YEARS:
        exp = standard_monthly_expiration(year, month).strftime("%Y%m%d")
        for symbol in QUALIFICATION_ROOTS:
            result.append(
                _descriptor(
                    "chain",
                    {"root": symbol, "exp": exp},
                    role=f"anchor_{year}_{month:02d}",
                )
            )
    return tuple(result)


def _eod_descriptor(
    contract: dict[str, str],
    *,
    role: str,
    repeat_index: int = 0,
) -> dict[str, object]:
    expiration = datetime.strptime(contract["exp"], "%Y%m%d").date()
    start = expiration - timedelta(days=90)
    return _descriptor(
        "eod",
        {
            "root": contract["root"],
            "exp": contract["exp"],
            "strike": contract["strike"],
            "right": contract["right"],
            "start_date": start.strftime("%Y%m%d"),
            "end_date": expiration.strftime("%Y%m%d"),
        },
        role=role,
        repeat_index=repeat_index,
    )


def _spread_cases_across_expiration_years(
    cases: Iterable[tuple[dict[str, object], dict[str, Any]]],
    *,
    limit: int,
) -> list[tuple[dict[str, object], dict[str, Any]]]:
    groups: dict[int, list[tuple[dict[str, object], dict[str, Any]]]] = defaultdict(list)
    for descriptor, payload in cases:
        exp = str(dict(descriptor["params"]).get("exp") or "")
        if len(exp) == 8 and exp[:4].isdigit():
            groups[int(exp[:4])].append((descriptor, payload))
    selected: list[tuple[dict[str, object], dict[str, Any]]] = []
    offset = 0
    years = sorted(groups)
    while len(selected) < limit:
        added = False
        for year in years:
            bucket = groups[year]
            if offset < len(bucket):
                selected.append(bucket[offset])
                added = True
                if len(selected) >= limit:
                    break
        if not added:
            break
        offset += 1
    return selected


def _summary_record(
    descriptor: dict[str, object],
    receipt: dict[str, object],
    payload: dict[str, Any],
    *,
    reused: bool,
) -> dict[str, object]:
    rows = _rows(payload)
    params = dict(descriptor["params"])
    return {
        "probe_id": receipt["probe_id"],
        "kind": descriptor["kind"],
        "role": descriptor["role"],
        "repeat_index": descriptor["repeat_index"],
        "root": params.get("root"),
        "exp": params.get("exp"),
        "http_status": receipt["http_status"],
        "row_count": len(rows),
        "payload_fingerprint": receipt["payload_fingerprint"],
        "reused": reused,
        "response_bytes": receipt["response_bytes"],
        "elapsed_seconds": receipt["elapsed_seconds"],
    }


def run_czar28_historical_option_qualification_v1(
    settings: AtlasSettings,
    *,
    max_requests: int = MAX_FREE_REQUESTS,
    requests_per_minute: int = MAX_QUALIFICATION_RPM,
    request_json: Callable[..., Czar28Response] = get_json,
) -> dict[str, object]:
    root = _qualification_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    if max_requests == MAX_FREE_REQUESTS:
        completed = _load_completed_qualification(root)
        if completed is not None:
            return completed

    budget = ProbeBudget(
        max_requests=max_requests,
        requests_per_minute=requests_per_minute,
    )

    probe_summaries: list[dict[str, object]] = []
    chain_payloads: list[tuple[dict[str, object], dict[str, Any]]] = []
    successful_eod: list[tuple[dict[str, object], dict[str, Any]]] = []
    terminal_error: str | None = None
    quota_exhausted = False

    def execute(descriptor: dict[str, object]) -> dict[str, Any] | None:
        nonlocal terminal_error, quota_exhausted
        if not budget.can_request() and _load_reusable_probe(root, descriptor) is None:
            return None
        try:
            receipt, payload, reused = _call_probe(
                root,
                budget,
                descriptor,
                request_json=request_json,
            )
        except Czar28QuotaExhausted as exc:
            quota_exhausted = True
            terminal_error = str(exc)
            return None
        except Czar28LocalBudgetExhausted:
            return None
        except Czar28Error as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            budget.halt()
            return None
        probe_summaries.append(
            _summary_record(descriptor, receipt, payload, reused=reused)
        )
        if not reused and budget.request_attempts % 25 == 0:
            print(
                "  Czar28 progress: "
                f"provider_calls={budget.request_attempts:,}/{max_requests:,} "
                f"remaining={budget.provider_remaining} "
                f"saved_probes={len(probe_summaries):,}",
                flush=True,
            )
        return payload

    # Phase 1: one standard monthly chain snapshot for 30 durable roots across
    # every stock-aligned anchor year. This alone establishes historical depth
    # and broad root/contract identity behavior.
    for descriptor in _chain_descriptors(month=6):
        payload = execute(descriptor)
        if payload is None and not budget.can_request():
            break
        if payload is not None and _rows(payload):
            chain_payloads.append((descriptor, payload))

    # Phase 2: deterministic median-strike call/put EOD lifecycle probes.
    primary_eod: list[dict[str, object]] = []
    secondary_eod: list[dict[str, object]] = []
    for chain_descriptor, payload in chain_payloads:
        representatives = representative_contracts(payload)
        for index, contract in enumerate(representatives):
            if not contract["root"] or not contract["exp"]:
                continue
            descriptor = _eod_descriptor(
                contract,
                role=(
                    f"representative_from_"
                    f"{chain_descriptor['role']}_{contract['right']}"
                ),
            )
            if index == 0:
                primary_eod.append(descriptor)
            else:
                secondary_eod.append(descriptor)
    # Open one representative contract from every successful root/year chain
    # before spending additional quota on the second right. This prevents early
    # years from consuming the EOD budget before 2025/2026 are tested.
    eod_descriptors = primary_eod + secondary_eod

    for descriptor in eod_descriptors[:EOD_PROBE_TARGET]:
        payload = execute(descriptor)
        if payload is None and not budget.can_request():
            break
        if payload is not None and _rows(payload):
            successful_eod.append((descriptor, payload))

    # Phase 3: real one-day intraday NBBO-style quote and trade-print presence
    # for 50 contracts spread deterministically over the successful EOD pool.
    detail_cases = _spread_cases_across_expiration_years(
        successful_eod,
        limit=max(INTRADAY_PROBE_TARGET, TRADE_PROBE_TARGET),
    )
    for index, (eod_descriptor, payload) in enumerate(detail_cases):
        day = _last_eod_date(payload)
        if day is None:
            continue
        base = dict(eod_descriptor["params"])
        common = {
            "root": base["root"],
            "exp": base["exp"],
            "strike": base["strike"],
            "right": base["right"],
            "start_date": day,
            "end_date": day,
        }
        if index < INTRADAY_PROBE_TARGET:
            execute(
                _descriptor(
                    "intraday",
                    {**common, "ivl": 60000, "rth": "true"},
                    role="one_day_intraday_presence",
                )
            )
        if index < TRADE_PROBE_TARGET:
            execute(
                _descriptor(
                    "trades",
                    common,
                    role="one_day_trade_presence",
                )
            )
        if not budget.can_request():
            break

    # Phase 4: intentional uncached repeats. Different logical probe ids force
    # fresh provider observations so payload stability can be measured.
    for descriptor, _payload in _spread_cases_across_expiration_years(
        chain_payloads,
        limit=CHAIN_REPEAT_TARGET,
    ):
        repeat = _descriptor(
            "chain",
            dict(descriptor["params"]),
            role="intentional_chain_stability_repeat",
            repeat_index=1,
        )
        execute(repeat)
        if not budget.can_request():
            break

    for descriptor, _payload in _spread_cases_across_expiration_years(
        successful_eod,
        limit=EOD_REPEAT_TARGET,
    ):
        repeat = _descriptor(
            "eod",
            dict(descriptor["params"]),
            role="intentional_eod_stability_repeat",
            repeat_index=1,
        )
        execute(repeat)
        if not budget.can_request():
            break

    # Phase 5: consume otherwise-unused free quota with additional useful,
    # deterministic evidence. First use representative EOD contracts not yet
    # opened, then March/September chain snapshots. No random or duplicate noise.
    existing_probe_ids = {str(item["probe_id"]) for item in probe_summaries}
    for descriptor in eod_descriptors[EOD_PROBE_TARGET:]:
        if not budget.can_request():
            break
        if _probe_id(descriptor) in existing_probe_ids:
            continue
        execute(descriptor)

    if budget.can_request():
        for month in (3, 9):
            for descriptor in _chain_descriptors(month=month):
                if not budget.can_request():
                    break
                if _probe_id(descriptor) in existing_probe_ids:
                    continue
                execute(descriptor)
            if not budget.can_request():
                break

    kind_counts = Counter(str(item["kind"]) for item in probe_summaries)
    status_counts = Counter(int(item["http_status"]) for item in probe_summaries)
    nonempty_by_kind = Counter(
        str(item["kind"])
        for item in probe_summaries
        if int(item["http_status"]) == 200 and int(item["row_count"]) > 0
    )
    year_stats: dict[int, dict[str, int]] = defaultdict(
        lambda: {
            "chain_probes": 0,
            "chain_nonempty": 0,
            "eod_probes": 0,
            "eod_nonempty": 0,
        }
    )
    for item in probe_summaries:
        exp = str(item.get("exp") or "")
        if len(exp) != 8 or not exp[:4].isdigit():
            continue
        year = int(exp[:4])
        if item["kind"] == "chain" and int(item["repeat_index"]) == 0:
            year_stats[year]["chain_probes"] += 1
            if int(item["http_status"]) == 200 and int(item["row_count"]) > 0:
                year_stats[year]["chain_nonempty"] += 1
        if item["kind"] == "eod" and int(item["repeat_index"]) == 0:
            year_stats[year]["eod_probes"] += 1
            if int(item["http_status"]) == 200 and int(item["row_count"]) > 0:
                year_stats[year]["eod_nonempty"] += 1

    chain_repeat_matches = 0
    chain_repeat_checked = 0
    eod_repeat_matches = 0
    eod_repeat_checked = 0
    base_fingerprints: dict[tuple[str, tuple[tuple[str, str], ...]], str] = {}
    for item in probe_summaries:
        descriptor_receipt = json.loads(
            (
                root
                / "probes"
                / f"{item['probe_id']}.receipt.json"
            ).read_text(encoding="utf-8")
        )
        descriptor = dict(descriptor_receipt["descriptor"])
        params_key = tuple(sorted(dict(descriptor["params"]).items()))
        key = (str(descriptor["kind"]), params_key)
        if int(descriptor["repeat_index"]) == 0:
            base_fingerprints[key] = str(item["payload_fingerprint"])
            continue
        if descriptor["kind"] == "chain":
            chain_repeat_checked += 1
            if base_fingerprints.get(key) == item["payload_fingerprint"]:
                chain_repeat_matches += 1
        if descriptor["kind"] == "eod":
            eod_repeat_checked += 1
            if base_fingerprints.get(key) == item["payload_fingerprint"]:
                eod_repeat_matches += 1

    observed_years = {
        year
        for year, stats in year_stats.items()
        if stats["chain_nonempty"] > 0 and stats["eod_nonempty"] > 0
    }
    full_year_span_observed = set(ANCHOR_YEARS).issubset(observed_years)
    endpoint_presence = all(
        nonempty_by_kind.get(kind, 0) > 0
        for kind in ("chain", "eod", "intraday", "trades")
    )
    quota_fully_exercised = (
        budget.request_attempts >= max_requests
        or budget.provider_remaining == 0
        or quota_exhausted
    )

    status = (
        "DIAGNOSTIC_COMPLETE"
        if full_year_span_observed and endpoint_presence and quota_fully_exercised
        else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
    )

    report: dict[str, object] = {
        "status": status,
        "contract": CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT["contract_id"],
        "contract_fingerprint": (
            CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT_FINGERPRINT
        ),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "credential_env": CZAR28_CREDENTIAL_ENV,
        "provider_request_attempts_this_run": budget.request_attempts,
        "provider_limit_observed": budget.provider_limit,
        "provider_remaining_observed": budget.provider_remaining,
        "provider_reset_observed": budget.provider_reset,
        "provider_minute_limit_observed": budget.provider_minute_limit,
        "provider_burst_observed": budget.provider_burst,
        "quota_exhausted": quota_exhausted,
        "terminal_error": terminal_error,
        "probe_count_in_report": len(probe_summaries),
        "kind_counts": dict(sorted(kind_counts.items())),
        "http_status_counts": {
            str(k): v for k, v in sorted(status_counts.items())
        },
        "nonempty_by_kind": dict(sorted(nonempty_by_kind.items())),
        "year_stats": {
            str(year): dict(year_stats.get(year, {}))
            for year in ANCHOR_YEARS
        },
        "full_2016_through_2026_chain_and_eod_presence": full_year_span_observed,
        "all_four_endpoint_classes_nonempty": endpoint_presence,
        "chain_repeat_stability": {
            "checked": chain_repeat_checked,
            "exact_payload_matches": chain_repeat_matches,
        },
        "eod_repeat_stability": {
            "checked": eod_repeat_checked,
            "exact_payload_matches": eod_repeat_matches,
        },
        "probes": probe_summaries,
        "authority": CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT["authority"],
        "interpretation": {
            "candidate_source_only": True,
            "cross_provider_price_validation_still_required": True,
            "open_interest_not_documented_in_czar28_v1_eod_schema": True,
            "historical_data_authority_created": False,
            "strategy_evidence_created": False,
            "paper_or_live_authority_created": False,
        },
    }
    report["evidence_fingerprint"] = stable_fingerprint(report)

    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = reports / f"{stamp}.json"
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, sort_keys=True) + "\n",
    )
    report["report_path"] = str(report_path.resolve())

    qualification_cycle_complete = (
        max_requests == MAX_FREE_REQUESTS
        and (
            budget.request_attempts >= MAX_FREE_REQUESTS
            or budget.provider_remaining == 0
        )
    )
    report["qualification_cycle_complete"] = qualification_cycle_complete
    report["reused_completed_qualification"] = False
    if qualification_cycle_complete:
        completion = {
            "status": "COMPLETE",
            "contract_fingerprint": (
                CZAR28_HISTORICAL_OPTION_QUALIFICATION_V1_CONTRACT_FINGERPRINT
            ),
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "report_name": report_path.name,
            "report_sha256": _sha256_file(report_path),
            "evidence_fingerprint": report["evidence_fingerprint"],
        }
        atomic_write_text(
            root / "completion.json",
            json.dumps(completion, indent=2, sort_keys=True) + "\n",
        )
    return report
