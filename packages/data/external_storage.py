from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings


EXTERNAL_STORAGE_CONTRACT = "atlas-external-secondary-storage-v1"


class ExternalStorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalBindingStatus:
    name: str
    project_path: str
    external_path: str
    status: str


@dataclass(frozen=True, slots=True)
class ExternalStorageSnapshot:
    contract: str
    configured: bool
    external_root: str | None
    status: str
    bindings: tuple[ExternalBindingStatus, ...]


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _is_junction(path: Path) -> bool:
    checker = getattr(os.path, "isjunction", None)
    return bool(checker and checker(str(path)))


def _samefile(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def _binding_status(
    settings: AtlasSettings,
    name: str,
    *,
    external_root: Path,
) -> ExternalBindingStatus:
    project_path, external_path = settings.external_storage_binding_paths(
        name,
        root_override=external_root,
    )

    if not external_path.is_dir():
        status = "TARGET_MISSING"
    elif _lexists(project_path) and _samefile(project_path, external_path):
        status = "READY"
    elif _lexists(project_path) and (project_path.is_symlink() or _is_junction(project_path)):
        status = "WRONG_TARGET"
    elif project_path.is_file():
        status = "PROJECT_PATH_IS_FILE"
    elif project_path.is_dir():
        try:
            nonempty = next(project_path.iterdir(), None) is not None
        except OSError:
            nonempty = True
        status = "LOCAL_DATA_PRESENT" if nonempty else "UNBOUND_EMPTY_DIRECTORY"
    else:
        status = "UNBOUND"

    return ExternalBindingStatus(
        name=name,
        project_path=str(project_path),
        external_path=str(external_path),
        status=status,
    )


def inspect_external_storage(
    settings: AtlasSettings,
    *,
    root_override: Path | None = None,
) -> ExternalStorageSnapshot:
    root = (
        Path(root_override).expanduser().resolve()
        if root_override is not None
        else settings.external_data_root()
    )
    if root is None:
        return ExternalStorageSnapshot(
            contract=EXTERNAL_STORAGE_CONTRACT,
            configured=False,
            external_root=None,
            status="NOT_CONFIGURED",
            bindings=(),
        )
    if not root.is_dir():
        return ExternalStorageSnapshot(
            contract=EXTERNAL_STORAGE_CONTRACT,
            configured=True,
            external_root=str(root),
            status="ROOT_MISSING",
            bindings=(),
        )

    bindings = tuple(
        _binding_status(settings, name, external_root=root)
        for name in settings.data.external_storage.bindings
    )
    status = "READY" if bindings and all(item.status == "READY" for item in bindings) else "NOT_READY"
    return ExternalStorageSnapshot(
        contract=EXTERNAL_STORAGE_CONTRACT,
        configured=True,
        external_root=str(root),
        status=status,
        bindings=bindings,
    )


def assert_external_storage_ready(settings: AtlasSettings) -> ExternalStorageSnapshot:
    snapshot = inspect_external_storage(settings)
    if not snapshot.configured:
        return snapshot
    if snapshot.status != "READY":
        details = ", ".join(
            f"{item.name}={item.status}" for item in snapshot.bindings
        ) or snapshot.status
        raise ExternalStorageError(
            "external secondary storage is configured but not ready; "
            f"refusing local spillover ({details})"
        )
    return snapshot


def _move_directory_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if destination.exists() or _lexists(destination):
            raise ExternalStorageError(
                f"cannot migrate {item}: target already exists: {destination}"
            )
        shutil.move(str(item), str(destination))


def _create_directory_link(project_path: Path, external_path: Path) -> None:
    project_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        completed = subprocess.run(
            [
                "cmd",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(project_path),
                str(external_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "").strip()
            raise ExternalStorageError(
                f"failed to create directory junction {project_path} -> "
                f"{external_path}: {message}"
            )
    else:
        os.symlink(external_path, project_path, target_is_directory=True)


def apply_external_storage_bindings(
    settings: AtlasSettings,
    *,
    external_root: Path,
    migrate_existing: bool = False,
) -> ExternalStorageSnapshot:
    root = Path(external_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    for name in settings.data.external_storage.bindings:
        project_path, external_path = settings.external_storage_binding_paths(
            name,
            root_override=root,
        )
        external_path.mkdir(parents=True, exist_ok=True)

        if _lexists(project_path):
            if _samefile(project_path, external_path):
                continue
            if project_path.is_symlink() or _is_junction(project_path):
                raise ExternalStorageError(
                    f"{project_path} is already linked to a different target"
                )
            if project_path.is_file():
                raise ExternalStorageError(
                    f"cannot bind external storage over file: {project_path}"
                )
            if project_path.is_dir():
                has_content = next(project_path.iterdir(), None) is not None
                if has_content and not migrate_existing:
                    raise ExternalStorageError(
                        f"{project_path} contains existing data; rerun with "
                        "--migrate-existing after reviewing the target"
                    )
                if has_content:
                    _move_directory_contents(project_path, external_path)
                project_path.rmdir()

        _create_directory_link(project_path, external_path)
        if not _samefile(project_path, external_path):
            raise ExternalStorageError(
                f"created binding did not resolve to target: "
                f"{project_path} -> {external_path}"
            )

    marker: dict[str, Any] = {
        "contract": EXTERNAL_STORAGE_CONTRACT,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "project_root": str(settings.project_root.resolve()),
        "external_root": str(root),
        "bindings": {
            name: {
                "project_subdir": str(binding.project_subdir).replace("\\", "/"),
                "external_subdir": str(binding.external_subdir).replace("\\", "/"),
            }
            for name, binding in settings.data.external_storage.bindings.items()
        },
        "stock_storage_moved": False,
        "primary_data_paths_unchanged": True,
    }
    marker_path = root / settings.data.external_storage.marker_name
    atomic_write_text(marker_path, json.dumps(marker, indent=2, sort_keys=True) + "\n")

    snapshot = inspect_external_storage(settings, root_override=root)
    if snapshot.status != "READY":
        raise ExternalStorageError(
            "external secondary-storage setup did not finish in READY state"
        )
    return snapshot


def snapshot_as_dict(snapshot: ExternalStorageSnapshot) -> dict[str, Any]:
    return {
        **asdict(snapshot),
        "bindings": [asdict(item) for item in snapshot.bindings],
    }
