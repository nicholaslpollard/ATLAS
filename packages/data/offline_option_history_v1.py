from __future__ import annotations

"""Read-only, provider-free view of accepted 2022 historical CALL EOD bodies.

This is the first reusable research adapter, not a trade simulator or an
executable-quote/PIT-publication guarantee. Missing or altered evidence fails
closed; it never falls through to a paid provider request.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_2022_broad_quote_campaign_v2 import PLAN_REL
from packages.data.marketdata_2022_ranked_eod_readiness_v1 import EXPECTED_PLAN
from packages.data.marketdata_2022_rank0_later_eod_reference_v1 import _original_observations
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    CONTRACT as QUOTE_CONTRACT,
    _cache_paths,
    _read_intact_quote,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError,
    _fingerprint,
)

CONTRACT = "atlas-offline-accepted-2022-call-eod-history-v1"
PLAN_FILENAME = "through_shard_070.json"
EXPECTED_QUOTE_HISTORIES = 6398
EASTERN = ZoneInfo("America/New_York")
AUTHORITY = {
    "provider_requests": 0,
    "provider_fallback": False,
    "executable_0935_option_quote": False,
    "historical_publication_time_verified": False,
    "historical_deliverable_verified": False,
    "option_cash_pnl": False,
    "paper": False,
    "live": False,
    "strategy_promotion": False,
}


class OfflineOptionHistoryError(ValueError):
    """A local source is absent, inconsistent or beyond the frozen scope."""


class OfflineOptionHistoryStore:
    """Index a frozen plan once; verify exact raw body and receipt on each read.

    Full retrospective history must not be presented as a predecision feature.
    Use `predecision_history` for strategy inputs. Neither method calls a
    network client, writes files, fills gaps or silently picks another option.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        settings.assert_external_storage_binding("options")
        path = settings.resolved_path(f"{PLAN_REL}/{PLAN_FILENAME}")
        if path.is_symlink() or not path.is_file():
            raise OfflineOptionHistoryError("accepted local 2022 quote plan missing")
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(plan, dict):
                raise ValueError("plan is not an object")
            unsigned = dict(plan)
            fingerprint = unsigned.pop("plan_fingerprint", None)
            requests = plan["requests"]
            if (
                fingerprint != EXPECTED_PLAN
                or fingerprint != _fingerprint(unsigned)
                or plan.get("contract") != QUOTE_CONTRACT
                or plan.get("status") != "SOURCE_ONLY_SELECTED_CALL_QUOTE_HISTORIES_FROZEN"
                or plan.get("year") != 2022
                or plan.get("provider_reads_in_planning") != 0
                or plan.get("last_shard_inclusive") != 70
                or plan.get("unique_exact_quote_series") != EXPECTED_QUOTE_HISTORIES
                or not isinstance(requests, list)
                or len(requests) != EXPECTED_QUOTE_HISTORIES
            ):
                raise ValueError("accepted 2022 plan lineage differs")
            by_symbol: dict[str, dict[str, Any]] = {}
            identities: set[str] = set()
            for ticket in requests:
                symbol = ticket["option_symbol"]
                query = {
                    key: ticket[key]
                    for key in ("option_symbol", "from_inclusive", "to_exclusive")
                }
                identity = _fingerprint({"contract": QUOTE_CONTRACT, "query": query})
                if (
                    not isinstance(symbol, str)
                    or not symbol
                    or symbol in by_symbol
                    or identity in identities
                    or ticket.get("request_identity") != identity
                    or ticket.get("from_inclusive") != "2022-01-01"
                    or ticket.get("historical_eod_only") is not True
                    or ticket.get("historical_deliverable_not_verified") is not True
                ):
                    raise ValueError("duplicate or altered exact OCC query identity")
                by_symbol[symbol] = ticket
                identities.add(identity)
        except (OSError, TypeError, ValueError, KeyError, CandidateChainCacheError) as exc:
            raise OfflineOptionHistoryError("accepted local 2022 plan cannot be trusted") from exc
        self.settings = settings
        self.plan_path = path
        self.plan_fingerprint = fingerprint
        self._tickets = by_symbol

    @property
    def available_symbols(self) -> int:
        return len(self._tickets)

    def _observations(self, symbol: str) -> list[dict[str, Any]]:
        ticket = self._tickets.get(symbol)
        if ticket is None:
            raise OfflineOptionHistoryError("symbol is outside frozen 2022 CALL coverage")
        try:
            receipt = _read_intact_quote(self.settings, ticket)
            if receipt is None or receipt.get("status") != "COMPLETE_SOURCE_ONLY":
                raise OfflineOptionHistoryError("exact local quote body/receipt unavailable")
            body_path = _cache_paths(self.settings, ticket)[0]
            raw = body_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != receipt["body_sha256"]:
                raise OfflineOptionHistoryError("exact local quote body SHA differs")
            return _original_observations(
                raw, ticket, receipt["safe_summary"]["observed_rows"]
            )
        except OfflineOptionHistoryError:
            raise
        except (OSError, ValueError, TypeError, KeyError, CandidateChainCacheError) as exc:
            raise OfflineOptionHistoryError("original local quote source invalid") from exc

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_et": row["day"].isoformat(),
            "provider_updated_at_utc": row["updated_at_utc"],
            "bid_per_share": str(row["bid"]) if row["bid"] is not None else None,
            "ask_per_share": str(row["ask"]) if row["ask"] is not None else None,
            "two_sided": row["two_sided"],
            "positive_reported_volume": row["positive_volume"],
        }

    def inspect_retrospective_history(self, symbol: str) -> dict[str, Any]:
        """Descriptive complete observed path; MUST NOT be used for feature PIT."""
        rows = self._observations(symbol)
        return self._payload(symbol, rows, "RETROSPECTIVE_FULL_HISTORY", None)

    def predecision_history(self, symbol: str, *, decision_utc: datetime) -> dict[str, Any]:
        """Exclude same-session EOD and any original provider update after cutoff.

        This is conservative source filtering, NOT proof of original article/
        quote publication timing. No forward-looking fallback or imputation.
        """
        if not isinstance(decision_utc, datetime) or decision_utc.tzinfo is None:
            raise OfflineOptionHistoryError("decision_utc must be timezone-aware")
        cutoff = decision_utc.astimezone(UTC)
        session = cutoff.astimezone(EASTERN).date()
        rows = [
            row for row in self._observations(symbol)
            if row["day"] < session
            and datetime.fromisoformat(row["updated_at_utc"]) <= cutoff
        ]
        return self._payload(
            symbol, rows, "CONSERVATIVE_PREDECISION_EOD_SOURCE_VIEW", cutoff.isoformat()
        )

    def _payload(
        self, symbol: str, rows: list[dict[str, Any]], scope: str,
        cutoff: str | None,
    ) -> dict[str, Any]:
        return {
            "contract": CONTRACT,
            "source_quote_plan_fingerprint": self.plan_fingerprint,
            "option_symbol": symbol,
            "scope": scope,
            "decision_cutoff_utc": cutoff,
            "observations": [self._serialize(row) for row in rows],
            "observation_count": len(rows),
            "provider_updated_timestamp_is_not_publication_or_fill_proof": True,
            "authority": AUTHORITY,
        }
