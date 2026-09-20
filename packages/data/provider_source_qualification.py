from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable


SOURCE_QUALIFICATION_DIMENSIONS: tuple[str, ...] = (
    "IDENTITY_AND_CARDINALITY",
    "TIMESTAMP_AND_CHRONOLOGY",
    "DUPLICATE_AND_VERSION_SEMANTICS",
    "PAGINATION_COMPLETENESS",
    "PROVIDER_METADATA_VS_OBSERVED_DATA",
    "POINT_IN_TIME_AVAILABILITY",
    "SCHEMA_TYPES_AND_NULLABILITY",
    "ENTITLEMENT_AND_COVERAGE_BOUNDARIES",
    "RAW_TO_NORMALIZED_RECONCILIATION",
    "CORRUPTION_HASH_AND_RECEIPT_INTEGRITY",
    "UNKNOWN_ANOMALIES_FAIL_CLOSED",
)

VALID_DIMENSION_STATUSES: frozenset[str] = frozenset(
    {"PASS", "LIMITATION", "NOT_APPLICABLE", "FAIL"}
)


def stable_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def stable_fingerprint(value: object) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class QualificationDimension:
    name: str
    status: str
    evidence: str

    def as_dict(self) -> dict[str, str]:
        if self.name not in SOURCE_QUALIFICATION_DIMENSIONS:
            raise ValueError(f"unknown source-qualification dimension: {self.name}")
        if self.status not in VALID_DIMENSION_STATUSES:
            raise ValueError(
                f"invalid source-qualification status for {self.name}: {self.status}"
            )
        return {
            "name": self.name,
            "status": self.status,
            "evidence": self.evidence,
        }


def qualification_dimensions(
    items: Iterable[QualificationDimension],
) -> list[dict[str, str]]:
    by_name = {item.name: item for item in items}
    missing = [
        name for name in SOURCE_QUALIFICATION_DIMENSIONS if name not in by_name
    ]
    extra = sorted(set(by_name) - set(SOURCE_QUALIFICATION_DIMENSIONS))
    if missing or extra:
        raise ValueError(
            f"source-qualification dimensions incomplete; missing={missing} extra={extra}"
        )
    return [
        by_name[name].as_dict()
        for name in SOURCE_QUALIFICATION_DIMENSIONS
    ]


def qualification_status(
    dimensions: Iterable[dict[str, str]],
) -> str:
    statuses = [str(item.get("status") or "") for item in dimensions]
    if "FAIL" in statuses:
        return "FAIL"
    if "LIMITATION" in statuses:
        return "PASS_WITH_LIMITATIONS"
    return "PASS"
