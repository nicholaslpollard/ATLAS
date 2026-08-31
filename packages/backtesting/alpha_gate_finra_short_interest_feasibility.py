from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.finra_short_interest import (
    FINRA_EXCHANGE_LISTED_CODES,
    FINRAShortInterestClient,
    FINRAShortInterestFile,
    is_exchange_listed_short_interest_row,
)


FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT = (
    "alpha-gate-finra-short-interest-feasibility-v1-consolidated-position-source-only-no-market-outcomes"
)
FINRA_SHORT_INTEREST_SOURCE_PARENT_MERGE = "208529c5562920cc0b2bcf2bae546e2b9af0a25b"
FINRA_SHORT_INTEREST_MECHANISM = "PIT_FINRA_CONSOLIDATED_SHORT_INTEREST_POSITIONING_AND_CROWDING"
FINRA_SHORT_INTEREST_ALPHA_HYPOTHESES_FROZEN = False
FINRA_SHORT_INTEREST_TARGET_OUTCOME_READS_ALLOWED = False
FINRA_SHORT_INTEREST_PROTECTED_OUTCOME_READS_ALLOWED = False
FINRA_SHORT_INTEREST_PROVIDER_READS_ALLOWED = True
FINRA_SHORT_INTEREST_PROVIDER_WRITES = 0
FINRA_SHORT_INTEREST_BROKER_READS = 0
FINRA_SHORT_INTEREST_BROKER_WRITES = 0
FINRA_SHORT_INTEREST_ORDER_WRITES = 0
FINRA_SHORT_INTEREST_PAPER_SUBMITS = 0
FINRA_SHORT_INTEREST_LIVE_WRITES = 0
FINRA_SHORT_INTEREST_AUTOMATION_WRITES = 0
FINRA_SHORT_INTEREST_AUTOMATIC_BROKER_FAILOVER = False

FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES = (
    "2021-06-30",
    "2021-12-31",
    "2022-06-30",
    "2022-12-30",
    "2023-06-30",
    "2023-12-29",
    "2024-06-28",
    "2024-12-31",
    "2025-06-30",
    "2025-12-31",
    "2026-03-31",
    "2026-07-31",
)
FINRA_SHORT_INTEREST_MIN_SUCCESSFUL_FILES = 10
FINRA_SHORT_INTEREST_MIN_YEARS_REPRESENTED = 5
FINRA_SHORT_INTEREST_MIN_TOTAL_ROWS = 20_000
FINRA_SHORT_INTEREST_MIN_EXCHANGE_LISTED_ROWS = 10_000
FINRA_SHORT_INTEREST_MIN_UNIQUE_EXCHANGE_LISTED_SYMBOLS = 2_500
FINRA_SHORT_INTEREST_REQUIRED_SEMANTICS = (
    "settlement_date",
    "symbol",
    "current_short_position",
    "exchange_or_market",
)
FINRA_SHORT_INTEREST_ALLOWED_DELIMITERS = (",", "|", "\t")
FINRA_SHORT_INTEREST_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/finra_short_interest_feasibility_v1/source_census.json"
)


class FINRAShortInterestFeasibilityError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT,
        "source_parent_merge": FINRA_SHORT_INTEREST_SOURCE_PARENT_MERGE,
        "mechanism": FINRA_SHORT_INTEREST_MECHANISM,
        "source_host": "cdn.finra.org",
        "source_path_template": "/equity/otcmarket/biweekly/shrtYYYYMMDD.csv",
        "frozen_settlement_dates": list(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES),
        "min_successful_files": FINRA_SHORT_INTEREST_MIN_SUCCESSFUL_FILES,
        "min_years_represented": FINRA_SHORT_INTEREST_MIN_YEARS_REPRESENTED,
        "min_total_rows": FINRA_SHORT_INTEREST_MIN_TOTAL_ROWS,
        "min_exchange_listed_rows": FINRA_SHORT_INTEREST_MIN_EXCHANGE_LISTED_ROWS,
        "min_unique_exchange_listed_symbols": (
            FINRA_SHORT_INTEREST_MIN_UNIQUE_EXCHANGE_LISTED_SYMBOLS
        ),
        "required_semantics": list(FINRA_SHORT_INTEREST_REQUIRED_SEMANTICS),
        "allowed_delimiters": list(FINRA_SHORT_INTEREST_ALLOWED_DELIMITERS),
        "alpha_hypotheses_frozen": FINRA_SHORT_INTEREST_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": (
            FINRA_SHORT_INTEREST_TARGET_OUTCOME_READS_ALLOWED
        ),
        "protected_outcome_reads_allowed": (
            FINRA_SHORT_INTEREST_PROTECTED_OUTCOME_READS_ALLOWED
        ),
        "provider_reads_allowed": FINRA_SHORT_INTEREST_PROVIDER_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": FINRA_SHORT_INTEREST_PROVIDER_WRITES,
            "broker_reads": FINRA_SHORT_INTEREST_BROKER_READS,
            "broker_writes": FINRA_SHORT_INTEREST_BROKER_WRITES,
            "order_writes": FINRA_SHORT_INTEREST_ORDER_WRITES,
            "paper_submits": FINRA_SHORT_INTEREST_PAPER_SUBMITS,
            "live_writes": FINRA_SHORT_INTEREST_LIVE_WRITES,
            "automation_writes": FINRA_SHORT_INTEREST_AUTOMATION_WRITES,
            "automatic_broker_failover": (
                FINRA_SHORT_INTEREST_AUTOMATIC_BROKER_FAILOVER
            ),
        },
    }


def finra_short_interest_feasibility_fingerprint() -> str:
    return hashlib.sha256(
        _canonical_json(_fingerprint_payload()).encode("utf-8")
    ).hexdigest()


def _file_report(source: FINRAShortInterestFile) -> dict[str, Any]:
    listed_rows = [
        row for row in source.rows if is_exchange_listed_short_interest_row(row)
    ]
    revised_rows = sum(
        bool(str(row.get("revision_flag") or "").strip()) for row in source.rows
    )
    split_rows = sum(
        bool(str(row.get("stock_split_flag") or "").strip()) for row in source.rows
    )
    resolved_semantics = sorted(
        key
        for key, column in source.resolved_columns.items()
        if column is not None
    )
    exchange_identity_present = (
        source.resolved_columns.get("exchange_code") is not None
        or source.resolved_columns.get("market_code") is not None
    )
    return {
        "settlement_date": source.settlement_date,
        "source_url": source.source_url,
        "source_sha256": source.source_sha256,
        "delimiter": source.delimiter,
        "row_count": len(source.rows),
        "unique_symbols": len({str(row["symbol"]) for row in source.rows}),
        "exchange_listed_rows": len(listed_rows),
        "unique_exchange_listed_symbols": len(
            {str(row["symbol"]) for row in listed_rows}
        ),
        "revised_rows": revised_rows,
        "stock_split_flagged_rows": split_rows,
        "resolved_columns": source.resolved_columns,
        "resolved_semantics": resolved_semantics,
        "exchange_or_market_identity_present": exchange_identity_present,
    }


def _summarize_files(
    files: list[FINRAShortInterestFile],
) -> tuple[dict[str, Any], dict[str, bool]]:
    reports = [_file_report(source) for source in files]
    years = sorted({int(report["settlement_date"][:4]) for report in reports})
    total_rows = sum(int(report["row_count"]) for report in reports)
    exchange_listed_rows = sum(
        int(report["exchange_listed_rows"]) for report in reports
    )
    listed_symbols: set[str] = set()
    for source in files:
        listed_symbols.update(
            str(row["symbol"])
            for row in source.rows
            if is_exchange_listed_short_interest_row(row)
        )
    schema_proven = all(
        report["exchange_or_market_identity_present"]
        and all(
            semantic in report["resolved_semantics"]
            for semantic in ("settlement_date", "symbol", "current_short_position")
        )
        for report in reports
    )
    delimiters_proven = all(
        str(report["delimiter"]) in FINRA_SHORT_INTEREST_ALLOWED_DELIMITERS
        for report in reports
    )
    summary = {
        "successful_files": len(files),
        "years_represented": years,
        "year_count": len(years),
        "total_rows": total_rows,
        "exchange_listed_rows": exchange_listed_rows,
        "unique_exchange_listed_symbols": len(listed_symbols),
        "revised_rows": sum(int(report["revised_rows"]) for report in reports),
        "stock_split_flagged_rows": sum(
            int(report["stock_split_flagged_rows"]) for report in reports
        ),
        "exchange_listed_codes": sorted(FINRA_EXCHANGE_LISTED_CODES),
        "file_reports": reports,
    }
    gates = {
        "successful_files_min": (
            len(files) >= FINRA_SHORT_INTEREST_MIN_SUCCESSFUL_FILES
        ),
        "historical_years_min": (
            len(years) >= FINRA_SHORT_INTEREST_MIN_YEARS_REPRESENTED
        ),
        "total_rows_min": total_rows >= FINRA_SHORT_INTEREST_MIN_TOTAL_ROWS,
        "exchange_listed_rows_min": (
            exchange_listed_rows >= FINRA_SHORT_INTEREST_MIN_EXCHANGE_LISTED_ROWS
        ),
        "unique_exchange_listed_symbols_min": (
            len(listed_symbols)
            >= FINRA_SHORT_INTEREST_MIN_UNIQUE_EXCHANGE_LISTED_SYMBOLS
        ),
        "required_schema_semantics": schema_proven,
        "allowed_delimiters_only": delimiters_proven,
    }
    return summary, gates


class FINRAShortInterestFeasibility:
    """Source-only feasibility census for a FINRA positioning/crowding mechanism."""

    def __init__(
        self, settings: AtlasSettings, client: FINRAShortInterestClient
    ) -> None:
        self.settings = settings
        self.client = client

    def run(self) -> dict[str, Any]:
        files: list[FINRAShortInterestFile] = []
        failures: list[dict[str, str]] = []
        for index, settlement_date in enumerate(
            FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES, start=1
        ):
            try:
                files.append(
                    self.client.historical_file(settlement_date=settlement_date)
                )
            except Exception as exc:  # source census records failures; gates decide acceptance
                failures.append(
                    {
                        "settlement_date": settlement_date,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            print(
                "FINRA short-interest source census progress: "
                f"{index}/{len(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES)} "
                f"success={len(files)} failures={len(failures)}"
            )

        summary, gates = _summarize_files(files)
        report = {
            "contract_version": FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT,
            "feasibility_fingerprint": (
                finra_short_interest_feasibility_fingerprint()
            ),
            "source_parent_merge": FINRA_SHORT_INTEREST_SOURCE_PARENT_MERGE,
            "mechanism": FINRA_SHORT_INTEREST_MECHANISM,
            "status": "FEASIBILITY_PASS" if all(gates.values()) else "FEASIBILITY_FAIL",
            "pass": all(gates.values()),
            "alpha_hypotheses_frozen": False,
            "performance_evaluated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads_performed": len(
                FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES
            ),
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "automatic_broker_failover": False,
            "frozen_settlement_dates": list(
                FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES
            ),
            "source_summary": summary,
            "failures": failures,
            "gates": gates,
            "next_scientific_action": (
                "If feasibility passes, independently freeze and audit FINRA publication-time "
                "chronology, revision handling, split handling, and point-in-time active-common-stock "
                "identity before defining any finite performance hypotheses or opening market outcomes."
            ),
        }

        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        report_path = derived_root / FINRA_SHORT_INTEREST_REPORT_RELATIVE
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            report_path, json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        report["report_path"] = str(report_path)
        return report
