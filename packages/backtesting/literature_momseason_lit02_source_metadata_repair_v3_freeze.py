from __future__ import annotations

import json
import re
from datetime import date
from typing import Mapping

from packages.core.atomic_io import atomic_write_text

from .literature_momseason_lit02_source_metadata import _fingerprint
from .literature_momseason_lit02_source_metadata_repair_v2_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
)
from .literature_momseason_lit02_source_metadata_repair_v3 import (
    LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
    _report_fingerprint_v3,
    lit02_repair_v3_source_expansion_fingerprint,
    lit02_repair_v3_source_expansion_payload,
)
from .literature_momseason_lit02_source_metadata_repair_v3_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION,
    MomSeasonLIT02SourceMetadataRepairV3Certified,
)
from .literature_momseason_source import canonical_json


LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT = (
    "lit02-source-metadata-repair-v3-source-parser-freeze-v1-pre-provider-read"
)
LIT02_REPAIR_V3_DEFINED_CASH_TERMS = (
    "CASH CONSIDERATION",
    "MERGER CONSIDERATION",
    "OFFER PRICE",
    "PER SHARE MERGER CONSIDERATION",
)
_CONTINGENT_CONSIDERATION_RE = re.compile(
    r"(?i:\bCVRs?\b|\bcontingent\s+value\s+rights?\b)"
)


def _contains_contingent_consideration(value: object) -> bool:
    return bool(_CONTINGENT_CONSIDERATION_RE.search(str(value or "")))


def lit02_repair_v3_freeze_payload() -> dict[str, object]:
    return {
        "freeze_contract": LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT,
        "repair_contract": LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
        "source_expansion": lit02_repair_v3_source_expansion_payload(),
        "source_expansion_fingerprint": lit02_repair_v3_source_expansion_fingerprint(),
        "base_parser_certification": LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
        "repair_v3_parser_certification": (
            LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
        ),
        "defined_cash_terms": list(LIT02_REPAIR_V3_DEFINED_CASH_TERMS),
        "defined_term_rule": (
            "only an admitted final SC TO-T/A or SC 13E3/A may use defined-term linkage; "
            "the official filing must contain an explicit executed-event context on or before "
            "the frozen endpoint in which the holder's share is canceled/converted into the "
            "right to receive the same explicitly defined per-share cash term"
        ),
        "defined_term_value_rule": (
            "the same official filing must define the referenced term as exactly one positive "
            "dollar amount per common share; unrelated per-share values are ignored"
        ),
        "conflict_rule": (
            "multiple values for the same referenced defined term fail closed; multiple latest "
            "terminal classifications fail closed"
        ),
        "contingent_rule": (
            "CVR or contingent value right evidence in either the defined-term evidence or the "
            "executed-event consideration context is not admitted as TERMINAL_CASH under repair-v3"
        ),
        "future_event_rule": "effective/execution date must be on or before frozen endpoint",
        "economic_paths_changed": False,
        "required_source_coverage": 1.0,
        "ticker_specific_exceptions_allowed": False,
        "economic_outcome_values_allowed": False,
        "new_price_or_return_reads_allowed": False,
        "protected_reads_allowed": False,
        "broker_or_order_authority": False,
        "phase33_authority": False,
    }


def lit02_repair_v3_freeze_fingerprint() -> str:
    return _fingerprint(lit02_repair_v3_freeze_payload())


class MomSeasonLIT02SourceMetadataRepairV3Frozen(
    MomSeasonLIT02SourceMetadataRepairV3Certified
):
    """Repair-v3 with a pre-provider-read fingerprint over source + parser semantics."""

    def _sec_resolution_v3(
        self,
        *,
        identity: Mapping[str, object],
        endpoint_session: date,
        historical_ticker: str,
    ) -> tuple[dict[str, object] | None, list[dict[str, object]], list[str]]:
        candidate, evidence_rows, reasons = super()._sec_resolution_v3(
            identity=identity,
            endpoint_session=endpoint_session,
            historical_ticker=historical_ticker,
        )
        if candidate is not None and candidate.get("path_id") == "TERMINAL_CASH":
            excerpt = candidate.get("matched_excerpt")
            definition_excerpts = candidate.get("definition_excerpts")
            combined = " ".join(
                [
                    str(excerpt or ""),
                    *(
                        [str(value) for value in definition_excerpts]
                        if isinstance(definition_excerpts, list)
                        else []
                    ),
                ]
            )
            if _contains_contingent_consideration(combined):
                return (
                    None,
                    evidence_rows,
                    sorted(
                        set(
                            [
                                *reasons,
                                "CONTINGENT_CONSIDERATION_NOT_SUPPORTED_V3",
                            ]
                        )
                    ),
                )
        return candidate, evidence_rows, reasons

    def _load_cached_case(self, case: Mapping[str, object]) -> dict[str, object] | None:
        result = super()._load_cached_case(case)
        if result is None:
            return None
        if result.get("repair_v3_freeze_fingerprint") != lit02_repair_v3_freeze_fingerprint():
            return None
        return result

    def _write_case(self, case: Mapping[str, object], result: Mapping[str, object]) -> None:
        frozen_result = dict(result)
        frozen_result["repair_v3_freeze_contract"] = (
            LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT
        )
        frozen_result["repair_v3_freeze_fingerprint"] = lit02_repair_v3_freeze_fingerprint()
        super()._write_case(case, frozen_result)

    def run(self, *, force: bool = False) -> dict[str, object]:
        report = super().run(force=force)
        persisted = json.loads(self.report_path().read_text(encoding="utf-8"))
        persisted["repair_v3_freeze_contract"] = (
            LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT
        )
        persisted["repair_v3_freeze_fingerprint"] = lit02_repair_v3_freeze_fingerprint()
        persisted["repair_v3_parser_certification"] = (
            LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
        )
        persisted["report_fingerprint"] = _report_fingerprint_v3(persisted)
        atomic_write_text(self.report_path(), canonical_json(persisted) + "\n")
        output = dict(persisted)
        output["report_path"] = str(self.report_path())
        return output


assert lit02_repair_v3_freeze_payload()["required_source_coverage"] == 1.0
assert lit02_repair_v3_freeze_payload()["economic_outcome_values_allowed"] is False
assert lit02_repair_v3_freeze_payload()["new_price_or_return_reads_allowed"] is False
assert lit02_repair_v3_freeze_payload()["protected_reads_allowed"] is False
