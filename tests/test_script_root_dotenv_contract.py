from __future__ import annotations

"""Repository-wide credential ordering guard for workstation scripts."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def test_scripts_reading_marketdata_token_load_root_dotenv_first():
    checked = []
    for path in sorted(SCRIPTS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "MARKETDATA_TOKEN" not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        setting_lines = []
        token_lines = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = _name(node.func)
            if called == "load_settings":
                setting_lines.append(node.lineno)
            if (
                called == "os.getenv"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "MARKETDATA_TOKEN"
            ):
                token_lines.append(node.lineno)
        if not token_lines:
            continue
        assert setting_lines, (
            f"{path.relative_to(ROOT)} reads MARKETDATA_TOKEN without load_settings(); "
            "ATLAS workstation credentials belong in ROOT/.env"
        )
        assert min(setting_lines) < min(token_lines), (
            f"{path.relative_to(ROOT)} reads MARKETDATA_TOKEN before load_settings(); "
            "load ROOT/.env first"
        )
        checked.append(path.name)
    assert checked, "expected at least one direct MarketData workstation credential reader"
