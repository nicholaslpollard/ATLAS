from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from packages.core.settings import AtlasSettings


GIB = 1024 ** 3


class ResearchStorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResearchStorageSnapshot:
    disk_root: str
    disk_total_gib: float
    disk_used_gib: float
    disk_free_gib: float
    minimum_free_gib: float
    warning_free_gib: float
    acquisition_budget_gib: float
    category_usage_gib: dict[str, float]
    category_quota_gib: dict[str, float]
    total_research_usage_gib: float
    remaining_acquisition_budget_gib: float
    maximum_safe_additional_gib: float
    status: str


def _gib(value: int | float) -> float:
    return float(value) / GIB


def directory_size_bytes(path: Path) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    if path.is_file():
        return int(path.stat().st_size)
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += int(item.stat().st_size)
        except OSError:
            # A concurrently removed temp/cache file is not authoritative usage.
            continue
    return total


def research_category_paths(settings: AtlasSettings) -> dict[str, Path]:
    return {
        name: settings.resolved_path(category.local_subdir)
        for name, category in settings.data.research.storage.categories.items()
    }


def planned_research_layout(settings: AtlasSettings) -> tuple[Path, ...]:
    root = settings.resolved_path("data")
    news = settings.data.research.news
    options = settings.data.research.options
    relative = (
        news.raw_subdir,
        news.normalized_subdir,
        news.features_subdir,
        news.manifests_subdir,
        options.reference_subdir,
        options.daily_subdir,
        options.candidate_chain_subdir,
        options.candidate_minute_subdir,
        options.candidate_quote_subdir,
        options.candidate_trade_subdir,
        options.derived_iv_subdir,
        options.derived_greeks_subdir,
        options.manifests_subdir,
    )
    return tuple((root / item).resolve() for item in relative)


def initialize_research_layout(settings: AtlasSettings) -> tuple[Path, ...]:
    paths = planned_research_layout(settings)
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths


def inspect_research_storage(settings: AtlasSettings) -> ResearchStorageSnapshot:
    project = settings.project_root.resolve()
    usage = shutil.disk_usage(project)
    policy = settings.data.research.storage
    category_paths = research_category_paths(settings)
    category_usage = {
        name: _gib(directory_size_bytes(path))
        for name, path in category_paths.items()
    }
    category_quota = {
        name: float(policy.categories[name].quota_gib)
        for name in category_paths
    }
    total_research = sum(category_usage.values())
    remaining_budget = max(0.0, float(policy.acquisition_budget_gib) - total_research)
    safe_by_free_space = max(0.0, _gib(usage.free) - float(policy.minimum_free_gib))
    maximum_safe = min(remaining_budget, safe_by_free_space)

    free_gib = _gib(usage.free)
    if free_gib <= float(policy.minimum_free_gib):
        status = "BLOCKED_MINIMUM_FREE_SPACE"
    elif free_gib <= float(policy.warning_free_gib):
        status = "WARNING_LOW_FREE_SPACE"
    else:
        status = "SAFE"

    return ResearchStorageSnapshot(
        disk_root=str(project.anchor or project),
        disk_total_gib=_gib(usage.total),
        disk_used_gib=_gib(usage.used),
        disk_free_gib=free_gib,
        minimum_free_gib=float(policy.minimum_free_gib),
        warning_free_gib=float(policy.warning_free_gib),
        acquisition_budget_gib=float(policy.acquisition_budget_gib),
        category_usage_gib=category_usage,
        category_quota_gib=category_quota,
        total_research_usage_gib=total_research,
        remaining_acquisition_budget_gib=remaining_budget,
        maximum_safe_additional_gib=maximum_safe,
        status=status,
    )


def assert_category_acquisition_allowed(
    settings: AtlasSettings,
    *,
    category: str,
    projected_additional_bytes: int,
) -> ResearchStorageSnapshot:
    if projected_additional_bytes < 0:
        raise ValueError("projected additional bytes must be nonnegative")
    snapshot = inspect_research_storage(settings)
    policy = settings.data.research.storage
    if category not in policy.categories:
        raise ResearchStorageError(f"unknown research storage category: {category}")
    if snapshot.status == "BLOCKED_MINIMUM_FREE_SPACE":
        raise ResearchStorageError(
            "research acquisition blocked because disk free space is already at or "
            "below the configured minimum"
        )

    projected_gib = _gib(projected_additional_bytes)
    current_category_gib = snapshot.category_usage_gib.get(category, 0.0)
    quota_gib = float(policy.categories[category].quota_gib)
    if current_category_gib + projected_gib > quota_gib + 1e-12:
        raise ResearchStorageError(
            f"{category} acquisition would exceed its {quota_gib:.2f} GiB quota"
        )
    if projected_gib > snapshot.remaining_acquisition_budget_gib + 1e-12:
        raise ResearchStorageError(
            "research acquisition would exceed the configured total acquisition budget"
        )
    if snapshot.disk_free_gib - projected_gib < float(policy.minimum_free_gib):
        raise ResearchStorageError(
            "research acquisition would reduce disk below the configured minimum free space"
        )
    return snapshot
