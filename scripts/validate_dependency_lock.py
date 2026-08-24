from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"
LOCK_PATH = ROOT / "requirements.lock"
_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_EXACT_PIN_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]+\])?==([^\s;]+)(?:\s*;.*)?$"
)


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _declared_direct_dependencies() -> dict[str, str]:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project = data.get("project", {})
    specs: list[str] = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        specs.extend(group)

    declared: dict[str, str] = {}
    for spec in specs:
        match = _NAME_RE.match(spec)
        if match is None:
            raise ValueError(f"unparseable declared dependency: {spec!r}")
        name = _canonical_name(match.group(1))
        if name in declared:
            raise ValueError(f"duplicate declared dependency: {name}")
        declared[name] = spec
    return declared


def _locked_dependencies() -> tuple[dict[str, str], list[str]]:
    locked: dict[str, str] = {}
    invalid_lines: list[str] = []
    for raw_line in LOCK_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _EXACT_PIN_RE.match(line)
        if match is None:
            invalid_lines.append(line)
            continue
        name = _canonical_name(match.group(1))
        if name in locked:
            raise ValueError(f"duplicate locked dependency: {name}")
        locked[name] = match.group(2)
    return locked, invalid_lines


def validate_dependency_lock() -> dict[str, object]:
    declared = _declared_direct_dependencies()
    locked, invalid_lines = _locked_dependencies()
    missing = sorted(set(declared) - set(locked))
    extras = sorted(set(locked) - set(declared))
    passed = not missing and not invalid_lines
    return {
        "pass": passed,
        "declared_direct_count": len(declared),
        "locked_count": len(locked),
        "missing_direct_pins": missing,
        "extra_locked_dependencies": extras,
        "invalid_lock_lines": invalid_lines,
    }


def main() -> int:
    result = validate_dependency_lock()
    print("ATLAS dependency lock validation")
    print(f"  declared direct/optional dependencies: {result['declared_direct_count']}")
    print(f"  exact locked dependencies: {result['locked_count']}")
    extras = result["extra_locked_dependencies"]
    print(f"  extra explicit transitive pins: {', '.join(extras) if extras else 'none'}")
    if result["missing_direct_pins"]:
        print(f"  missing direct pins: {', '.join(result['missing_direct_pins'])}")
    if result["invalid_lock_lines"]:
        print("  invalid non-exact lock entries:")
        for line in result["invalid_lock_lines"]:
            print(f"    {line}")
    print(f"Dependency lock validation: {'PASS' if result['pass'] else 'FAIL'}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
