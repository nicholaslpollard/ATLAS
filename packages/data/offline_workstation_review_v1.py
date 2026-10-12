from __future__ import annotations

"""Bounded local metadata inventory, never a source or strategy acceptance gate."""

import json
import os
import shutil
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from packages.core.exceptions import ConfigurationError
from packages.core.settings import AtlasSettings
from packages.data.external_storage import inspect_external_storage
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_RUN_CONTRACT_FINGERPRINT,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)


CONTRACT = "atlas-offline-workstation-metadata-review-v1"
MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_CANDIDATES = 20
STOCK_ROOT = "data/v2_build/alpaca_sip_v2"
STANDALONE_ROOT = (
    f"{STOCK_ROOT}/derived/strategy_lab/successor_development/"
    f"{ACCEPTED_RUN_CONTRACT_FINGERPRINT[:16]}"
)

# Explicit metadata-only locations. No recursive lake/cache traversal or automatic
# selection of the newest plan. Multiple candidates remain visible and unresolved.
ARTIFACT_GROUPS = (
    ("stock_source", f"{STOCK_ROOT}/manifests", ("native_acquisition_report.json",)),
    ("stock_acceptance", f"{STOCK_ROOT}/validation", ("native_acceptance.json", "daily_quality.json", "identity_lifecycle.json")),
    ("stock_research_manifest", f"{STOCK_ROOT}/manifests", ("research_daily.json",)),
    ("news_source", "data/news/manifests/alpaca", ("historical_news_v1_summary.json", "historical_news_v1_source_integrity_v2.json")),
    ("successor_standalone", STANDALONE_ROOT, ("standalone_summary.json", "input_manifest.json")),
    ("successor_conditioning", f"{STANDALONE_ROOT}/conditioning_v1/{SUCCESSOR_CONDITIONING_FINGERPRINT[:16]}", ("analysis_summary.json",)),
    ("dynamic_exit_v1", "data/research/recurrent_successor_dynamic_exit_v1/db538c8cc72189d4/560b35765e82b2ab", ("dynamic_exit_v1_summary.json",)),
    ("option_decision_clock", "data/options/derived", ("multiyear_intraday_stock_exit_clock_v1_*.json", "multiyear_option_decision_spot_v1_*.json")),
    ("option_quote_lineage", "data/options/manifests", ("multiyear_demand_quote_v1_*.json", "multiyear_option_quote_reuse_handoff_v1_*.json")),
    ("thetadata_plans", "data/options/manifests", ("thetadata_candidate_surface_source_plan_v1_*.json", "thetadata_candidate_surface_enrichment_plan_v1_*.json")),
)

HEADER_FIELDS = (
    "contract", "contract_version", "status", "stage", "cutoff_session",
    "start_session", "end_session", "contract_fingerprint", "run_fingerprint",
    "report_fingerprint", "acceptance_fingerprint", "analysis_fingerprint",
    "plan_fingerprint", "enrichment_plan_fingerprint", "decision_spot_fingerprint",
    "input_manifest_fingerprint", "run_contract_fingerprint",
)


def _linked(path: Path) -> bool:
    checker = getattr(os.path, "isjunction", None)
    return path.is_symlink() or bool(checker and checker(path))


def _metadata(path: Path, directory: Path) -> dict[str, object]:
    item: dict[str, object] = {"path": str(path)}
    try:
        if _linked(path) or not path.resolve().is_relative_to(directory.resolve()):
            return {**item, "inspection": "BLOCKED_PATH_LINK"}
        if not path.is_file():
            return {**item, "inspection": "NOT_A_FILE"}
        size = path.stat().st_size
        item["size_bytes"] = size
        if size > MAX_METADATA_BYTES:
            return {**item, "inspection": "SIZE_ONLY_METADATA_TOO_LARGE"}
        # Bound the read even if a file grows after stat; do not hash large data.
        with path.open("rb") as stream:
            raw = stream.read(MAX_METADATA_BYTES + 1)
        if len(raw) > MAX_METADATA_BYTES:
            return {**item, "inspection": "SIZE_ONLY_METADATA_TOO_LARGE"}
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return {**item, "inspection": "INVALID_METADATA_OBJECT"}
        # Never echo full JSON, errors, credentials, source URLs, or performance
        # fields. A reported status/identity is not independently verified here.
        item["reported_headers"] = {
            key: value for key in HEADER_FIELDS
            if isinstance((value := payload.get(key)), str) and len(value) <= 256
        }
        return {**item, "inspection": "HEADERS_ONLY_NOT_ACCEPTANCE"}
    except (OSError, ValueError, UnicodeError):
        return {**item, "inspection": "UNREADABLE_METADATA"}


def inspect_artifact_group(
    settings: AtlasSettings,
    name: str,
    relative: str,
    patterns: tuple[str, ...],
) -> dict[str, object]:
    group: dict[str, object] = {"name": name, "relative_directory": relative, "patterns": list(patterns)}
    try:
        directory = settings.resolved_path(relative)
    except ConfigurationError:
        return {**group, "status": "BLOCKED_STORAGE_BINDING", "files": []}
    if not directory.is_dir():
        return {**group, "status": "DIRECTORY_MISSING", "files": []}
    candidates: dict[str, Path] = {}
    matched_patterns: set[str] = set()
    truncated = False
    try:
        for pattern in patterns:
            for path in directory.glob(pattern):
                matched_patterns.add(pattern)
                candidates[str(path)] = path
                if len(candidates) > MAX_CANDIDATES:
                    truncated = True
                    break
            if truncated:
                break
    except OSError:
        return {**group, "status": "DIRECTORY_UNREADABLE", "files": []}
    files = [_metadata(path, directory) for _, path in sorted(candidates.items())[:MAX_CANDIDATES]]
    missing = [pattern for pattern in patterns if pattern not in matched_patterns]
    status = "CANDIDATES_PRESENT_NOT_VALIDATED" if files else "NO_MATCHING_METADATA"
    if files and (missing or truncated or any(row["inspection"] != "HEADERS_ONLY_NOT_ACCEPTANCE" for row in files)):
        status = "PARTIAL_METADATA_INVENTORY"
    return {
        **group, "status": status, "files": files, "missing_patterns": missing,
        "candidate_set_truncated": truncated, "active_artifact_selected": False,
    }


def build_offline_workstation_review(settings: AtlasSettings) -> dict[str, object]:
    snapshot = inspect_external_storage(settings)
    volumes = []
    roots = [("primary", settings.project_root)]
    if snapshot.configured and snapshot.external_root:
        roots.append(("secondary", Path(snapshot.external_root)))
    for label, path in roots:
        try:
            usage = shutil.disk_usage(path)
            volumes.append({"name": label, "path": str(path), "free_bytes": usage.free, "total_bytes": usage.total})
        except OSError:
            volumes.append({"name": label, "path": str(path), "status": "UNAVAILABLE"})
    groups = [inspect_artifact_group(settings, *spec) for spec in ARTIFACT_GROUPS]
    gaps = [group["name"] for group in groups if group["status"] != "CANDIDATES_PRESENT_NOT_VALIDATED"]
    return {
        "contract": CONTRACT,
        "generated_utc": datetime.now(UTC).isoformat(),
        "status": "COMPLETE_METADATA_INVENTORY_WITH_GAPS" if gaps else "COMPLETE_METADATA_INVENTORY",
        "project_root": str(settings.project_root),
        "storage": asdict(snapshot), "volumes": volumes, "artifact_groups": groups,
        "groups_with_gaps": gaps,
        "limits": {"max_metadata_bytes": MAX_METADATA_BYTES, "max_candidates_per_group": MAX_CANDIDATES},
        "authority": {
            "provider_requests": 0, "broker_requests": 0, "historical_bar_scans": 0,
            "raw_quote_scans": 0, "simulations_run": 0, "strategy_rule_changes": False,
            "source_acceptance_granted": False, "strategy_promotion": False,
            "paper_authority": False, "live_authority": False,
        },
        "limitations": [
            "Reported headers are inventory observations, not hash or lineage acceptance.",
            "Candidate filenames are not a selection of the active plan; ambiguity is preserved.",
            "Only explicit metadata files are inspected; market data, cache receipts and bars are not rescanned.",
        ],
    }
