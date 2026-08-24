from __future__ import annotations

import hashlib
import heapq
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .phase20_policy import (
    PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED,
    phase20_policy_fingerprint,
)


_STAGE_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_PIPELINE_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class RegistryError(ValueError):
    pass


class DuplicateStageError(RegistryError):
    pass


class MissingDependencyError(RegistryError):
    pass


class DependencyCycleError(RegistryError):
    pass


class StageAuthorityError(RegistryError):
    pass


class StageAuthority(str, Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    EXTERNAL_READ = "EXTERNAL_READ"
    EXTERNAL_MUTATION = "EXTERNAL_MUTATION"


@dataclass(frozen=True)
class StageDefinition:
    stage_id: str
    dependencies: tuple[str, ...] = ()
    authority: StageAuthority = StageAuthority.LOCAL_ONLY
    retry_safe_local: bool = False
    max_attempts: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.stage_id, str) or not _STAGE_ID_RE.fullmatch(self.stage_id):
            raise RegistryError(f"invalid stage_id: {self.stage_id!r}")
        if not isinstance(self.dependencies, tuple) or any(
            not isinstance(dependency, str) for dependency in self.dependencies
        ):
            raise RegistryError("dependencies must be an immutable tuple of stage IDs")
        if not isinstance(self.authority, StageAuthority):
            raise StageAuthorityError("authority must be a StageAuthority value")
        if not isinstance(self.retry_safe_local, bool):
            raise RegistryError("retry_safe_local must be boolean")
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise RegistryError("max_attempts must be an integer")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise RegistryError(f"duplicate dependency in stage {self.stage_id!r}")
        if self.stage_id in self.dependencies:
            raise DependencyCycleError(f"stage {self.stage_id!r} cannot depend on itself")
        for dependency in self.dependencies:
            if not _STAGE_ID_RE.fullmatch(dependency):
                raise RegistryError(f"invalid dependency stage_id: {dependency!r}")
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise RegistryError("max_attempts must be between 1 and 5")
        if not self.retry_safe_local and self.max_attempts != 1:
            raise RegistryError("max_attempts > 1 requires retry_safe_local=True")
        if self.retry_safe_local and self.authority is not StageAuthority.LOCAL_ONLY:
            raise StageAuthorityError("only LOCAL_ONLY stages can be retry-safe in Phase 20")

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "stage_id": self.stage_id,
            "dependencies": list(sorted(self.dependencies)),
            "authority": self.authority.value,
            "retry_safe_local": self.retry_safe_local,
            "max_attempts": self.max_attempts,
        }


class PipelineRegistry:
    def __init__(
        self,
        pipeline_id: str,
        pipeline_version: str,
        stages: Iterable[StageDefinition],
    ) -> None:
        if not isinstance(pipeline_id, str) or not _PIPELINE_ID_RE.fullmatch(pipeline_id):
            raise RegistryError(f"invalid pipeline_id: {pipeline_id!r}")
        if not isinstance(pipeline_version, str) or not _VERSION_RE.fullmatch(pipeline_version):
            raise RegistryError(f"invalid pipeline_version: {pipeline_version!r}")
        self.pipeline_id = pipeline_id
        self.pipeline_version = pipeline_version
        stage_map: dict[str, StageDefinition] = {}
        for stage in stages:
            if not isinstance(stage, StageDefinition):
                raise RegistryError("pipeline stages must be StageDefinition values")
            if stage.stage_id in stage_map:
                raise DuplicateStageError(f"duplicate stage_id: {stage.stage_id}")
            if stage.authority is not StageAuthority.LOCAL_ONLY:
                if (
                    stage.authority is StageAuthority.EXTERNAL_MUTATION
                    and not PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED
                ):
                    raise StageAuthorityError(
                        "Phase 20 forbids external mutation-stage registration"
                    )
                raise StageAuthorityError(
                    f"Phase 20 orchestration does not authorize {stage.authority.value} stages"
                )
            stage_map[stage.stage_id] = stage
        if not stage_map:
            raise RegistryError("pipeline must contain at least one stage")
        self._stages = stage_map
        self._validate_dependencies()
        self._topological_order = self._build_topological_order()

    @property
    def stages(self) -> tuple[StageDefinition, ...]:
        return tuple(self._stages[stage_id] for stage_id in sorted(self._stages))

    def get(self, stage_id: str) -> StageDefinition:
        try:
            return self._stages[stage_id]
        except KeyError as exc:
            raise RegistryError(f"unknown stage_id: {stage_id}") from exc

    def topological_order(self) -> tuple[str, ...]:
        return self._topological_order

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "pipeline_id": self.pipeline_id,
            "pipeline_version": self.pipeline_version,
            "phase20_policy_fingerprint": phase20_policy_fingerprint(),
            "stages": [stage.fingerprint_payload() for stage in self.stages],
            "topological_order": list(self._topological_order),
        }

    def fingerprint(self) -> str:
        raw = json.dumps(
            self.fingerprint_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _validate_dependencies(self) -> None:
        known = set(self._stages)
        for stage in self._stages.values():
            missing = sorted(set(stage.dependencies) - known)
            if missing:
                raise MissingDependencyError(
                    f"stage {stage.stage_id!r} has missing dependencies: {missing}"
                )

    def _build_topological_order(self) -> tuple[str, ...]:
        indegree = {stage_id: 0 for stage_id in self._stages}
        children: dict[str, list[str]] = {stage_id: [] for stage_id in self._stages}
        for stage in self._stages.values():
            indegree[stage.stage_id] = len(stage.dependencies)
            for dependency in stage.dependencies:
                children[dependency].append(stage.stage_id)

        ready = [stage_id for stage_id, degree in indegree.items() if degree == 0]
        heapq.heapify(ready)
        order: list[str] = []
        while ready:
            stage_id = heapq.heappop(ready)
            order.append(stage_id)
            for child in sorted(children[stage_id]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    heapq.heappush(ready, child)

        if len(order) != len(self._stages):
            unresolved = sorted(stage_id for stage_id, degree in indegree.items() if degree > 0)
            raise DependencyCycleError(f"dependency cycle detected: {unresolved}")
        return tuple(order)
