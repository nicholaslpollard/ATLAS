from __future__ import annotations

"""Create or validate the isolated ThetaData Python-library provider environment.

This is an operational setup command, not a market-data command. It installs the
pinned provider package into .provider_venvs/thetadata so its protobuf>=6 dependency
cannot conflict with ATLAS's accepted Webull SDK protobuf<6 requirement.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.thetadata.client import (
    DEFAULT_PROVIDER_VENV,
    TARGET_LIBRARY_VERSION,
    WORKER_SCRIPT,
)


REQUIREMENTS = ROOT / "requirements-thetadata-provider.txt"
CONTRACT = "atlas-thetadata-python-provider-environment-v1"
OUTPUT_REL = "data/options/manifests/thetadata_python_provider_environment_v1"


def _python_path(root: Path) -> Path:
    if sys.platform == "win32":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def _run(cmd: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _base_python_version(python_path: Path) -> tuple[int, int, int]:
    completed = _run(
        [
            str(python_path),
            "-c",
            (
                "import json,sys;"
                "print(json.dumps([sys.version_info.major,sys.version_info.minor,"
                "sys.version_info.micro]))"
            ),
        ],
    )
    if completed.returncode != 0:
        raise RuntimeError("base Python version probe failed")
    try:
        values = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("base Python version probe returned invalid JSON") from exc
    if (
        not isinstance(values, list)
        or len(values) != 3
        or any(type(item) is not int for item in values)
    ):
        raise RuntimeError("base Python version probe returned invalid version")
    return int(values[0]), int(values[1]), int(values[2])


def _worker_preflight(python_path: Path) -> dict:
    completed = _run(
        [str(python_path), str(WORKER_SCRIPT), "--preflight"],
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"isolated ThetaData worker preflight failed with code {completed.returncode}"
        )
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("isolated ThetaData worker preflight returned invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("isolated ThetaData worker preflight did not pass")
    return payload


def _freeze(python_path: Path) -> list[str]:
    completed = _run(
        [str(python_path), "-m", "pip", "freeze", "--all"],
    )
    if completed.returncode != 0:
        raise RuntimeError("isolated ThetaData environment freeze failed")
    return sorted(
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    )


def _persist_manifest(settings, payload: dict) -> tuple[Path, str]:
    body = dict(payload)
    body["environment_fingerprint"] = _fingerprint(body)
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{body['environment_fingerprint'][:16]}.json"
    )
    raw = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise RuntimeError("existing ThetaData environment manifest differs")
        return path, "REUSED_IDENTICAL_PROVIDER_ENVIRONMENT_MANIFEST"
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
    return path, "WRITTEN_PROVIDER_ENVIRONMENT_MANIFEST"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create/validate the isolated ThetaData Python provider environment. "
            "This installs packages only and makes zero market-data requests."
        )
    )
    parser.add_argument(
        "--venv",
        type=Path,
        default=DEFAULT_PROVIDER_VENV,
        help="Provider virtual environment path.",
    )
    parser.add_argument(
        "--base-python",
        type=Path,
        default=Path(sys.executable),
        help=(
            "Python 3.12+ interpreter used to create the provider venv. "
            "Defaults to the current ATLAS interpreter."
        ),
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete/recreate an existing provider venv. Never implied.",
    )
    args = parser.parse_args(argv)

    print("ATLAS THETADATA ISOLATED PYTHON ENVIRONMENT V1", flush=True)
    print(
        "  ZERO market-data requests. Keeps ThetaData protobuf dependencies isolated "
        "from the Webull/core ATLAS environment.",
        flush=True,
    )
    try:
        base_python = args.base_python.expanduser()
        if not base_python.is_file():
            raise RuntimeError(f"base Python unavailable: {base_python}")
        base_version = _base_python_version(base_python)
        if base_version[:2] < (3, 12):
            raise RuntimeError(
                "ThetaData provider environment requires a Python 3.12+ base interpreter"
            )
        if not REQUIREMENTS.is_file():
            raise RuntimeError(f"provider requirements unavailable: {REQUIREMENTS}")
        if not WORKER_SCRIPT.is_file():
            raise RuntimeError(f"provider worker unavailable: {WORKER_SCRIPT}")

        root = args.venv if args.venv.is_absolute() else ROOT / args.venv
        python_path = _python_path(root)

        if root.exists() and args.recreate:
            shutil.rmtree(root)
        elif root.exists() and not python_path.is_file():
            raise RuntimeError(
                "provider venv exists but is incomplete; inspect it or rerun explicitly "
                "with --recreate"
            )

        action = "REUSED_EXISTING_PROVIDER_VENV"
        if not root.exists():
            completed = _run(
                [str(base_python), "-m", "venv", str(root)],
            )
            if completed.returncode != 0:
                raise RuntimeError("provider virtual environment creation failed")
            action = "CREATED_PROVIDER_VENV"

        python_path = _python_path(root)
        if not python_path.is_file():
            raise RuntimeError("provider Python missing after venv setup")

        pre_before = _worker_preflight(python_path)
        install_required = (
            pre_before.get("thetadata_installed") is not True
            or pre_before.get("thetadata_version") != TARGET_LIBRARY_VERSION
        )
        if install_required:
            completed = _run(
                [
                    str(python_path),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "-r",
                    str(REQUIREMENTS),
                ]
            )
            if completed.returncode != 0:
                tail = "\n".join(
                    (completed.stderr or completed.stdout).splitlines()[-20:]
                )
                raise RuntimeError(
                    "ThetaData provider dependency installation failed:\n" + tail
                )
            action += "+INSTALLED_PINNED_PROVIDER_DEPENDENCIES"

        preflight = _worker_preflight(python_path)
        if (
            preflight.get("python_meets_3_12") is not True
            or preflight.get("thetadata_installed") is not True
            or preflight.get("thetadata_version") != TARGET_LIBRARY_VERSION
            or not isinstance(preflight.get("environment_fingerprint"), str)
            or len(preflight["environment_fingerprint"]) != 64
        ):
            raise RuntimeError("ThetaData provider environment did not meet pinned contract")

        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        frozen = _freeze(python_path)
        payload = {
            "contract": CONTRACT,
            "status": "PROVIDER_ENVIRONMENT_READY",
            "provider_python": str(python_path),
            "provider_venv": str(root),
            "target_thetadata_version": TARGET_LIBRARY_VERSION,
            "observed_thetadata_version": preflight.get("thetadata_version"),
            "python_version": preflight.get("python_version"),
            "provider_environment_fingerprint": preflight.get(
                "environment_fingerprint"
            ),
            "provider_environment_packages": preflight.get(
                "environment_packages"
            ),
            "pip_freeze": frozen,
            "requirements_sha256": hashlib.sha256(
                REQUIREMENTS.read_bytes()
            ).hexdigest(),
            "worker_sha256": hashlib.sha256(
                WORKER_SCRIPT.read_bytes()
            ).hexdigest(),
            "provider_requests": 0,
            "market_data_requests": 0,
        }
        manifest, manifest_action = _persist_manifest(settings, payload)

        print(f"  provider_venv={root}", flush=True)
        print(
            f"  base_python={base_python} "
            f"version={base_version[0]}.{base_version[1]}.{base_version[2]}",
            flush=True,
        )
        print(f"  provider_python={python_path}", flush=True)
        print(f"  setup={action}", flush=True)
        print(
            f"  thetadata={preflight.get('thetadata_version')} "
            f"python={preflight.get('python_version')} "
            f"environment={str(preflight.get('environment_fingerprint'))[:16]}",
            flush=True,
        )
        print(
            f"  auth_source={preflight.get('auth_source')} "
            f"auth_material_present={preflight.get('auth_material_present')}",
            flush=True,
        )
        print(f"  manifest={manifest_action} / {manifest}", flush=True)
        print(
            "  COMPLETE provider_requests=0 market_data_requests=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"THETADATA PROVIDER ENVIRONMENT SETUP STOPPED: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No ThetaData market-data request was attempted.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
