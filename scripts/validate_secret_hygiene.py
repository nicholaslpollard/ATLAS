from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ENV_FILES = {".env.example"}
FORBIDDEN_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
FORBIDDEN_SECRET_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials.json"}
_PRIVATE_KEY_PREFIXES = ("", "RSA ", "EC ", "OPENSSH ")
PRIVATE_KEY_MARKERS = tuple(
    "-----BEGIN " + prefix + "PRIVATE KEY-----" for prefix in _PRIVATE_KEY_PREFIXES
)
TOKEN_PATTERNS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "openai_style_token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
}
SENSITIVE_ENV_NAME = re.compile(
    r"(?:^|_)(?:API_KEY|KEY|SECRET|TOKEN|PASSWORD|SECURITY_CODE|PRIVATE_KEY)$",
    re.IGNORECASE,
)


def _tracked_paths() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / item.decode("utf-8") for item in raw.split(b"\0") if item]


def _text_content(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _nonempty_env_secret_violations(path: Path, text: str) -> list[str]:
    if path.name not in ALLOWED_ENV_FILES:
        return []
    violations: list[str] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        normalized_value = value.strip().strip('"').strip("'")
        if key.upper() == "DATABASE_URL" or SENSITIVE_ENV_NAME.search(key):
            if normalized_value:
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: populated {key}")
    return violations


def validate_secret_hygiene() -> dict[str, object]:
    violations: list[str] = []
    scanned_text_files = 0
    tracked = _tracked_paths()

    for path in tracked:
        relative = path.relative_to(ROOT)
        name = path.name
        lower_name = name.lower()

        if lower_name == ".env" or (
            lower_name.startswith(".env.") and name not in ALLOWED_ENV_FILES
        ):
            violations.append(f"tracked environment file forbidden: {relative}")

        if (
            path.suffix.lower() in FORBIDDEN_SECRET_SUFFIXES
            or lower_name in FORBIDDEN_SECRET_NAMES
        ):
            violations.append(f"tracked credential/private-key file forbidden: {relative}")

        text = _text_content(path)
        if text is None:
            continue
        scanned_text_files += 1

        for marker in PRIVATE_KEY_MARKERS:
            if marker in text:
                violations.append(f"private-key material marker found: {relative}")
                break

        for label, pattern in TOKEN_PATTERNS.items():
            if pattern.search(text):
                violations.append(f"{label} pattern found: {relative}")

        violations.extend(_nonempty_env_secret_violations(path, text))

    return {
        "pass": not violations,
        "tracked_file_count": len(tracked),
        "scanned_text_file_count": scanned_text_files,
        "violations": sorted(set(violations)),
    }


def main() -> int:
    result = validate_secret_hygiene()
    print("ATLAS secret hygiene validation")
    print(f"  tracked files: {result['tracked_file_count']}")
    print(f"  UTF-8 text files scanned: {result['scanned_text_file_count']}")
    if result["violations"]:
        print("  violations:")
        for violation in result["violations"]:
            print(f"    {violation}")
    print(f"Secret hygiene validation: {'PASS' if result['pass'] else 'FAIL'}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
