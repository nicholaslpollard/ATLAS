from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "apps" / "web"


def _text(name: str) -> str:
    return (WEB_ROOT / name).read_text(encoding="utf-8")


def test_cleanup_ui_exposes_exact_review_and_safe_abandon_only() -> None:
    html = _text("index.html")
    js = _text("app.js")

    assert 'id="cleanup-dialog"' in html
    assert "Exact broker cleanup review" in html
    assert "Cancel-order and flatten-position provider writes are disabled" in html
    assert "Confirming a plan does not change the broker account" in html
    assert 'id="cleanup-targets"' in html
    assert 'id="cleanup-result"' in html
    assert "Abandon pre-write" in js
    assert "/cleanup-plan/confirm" in js
    assert "/cleanup-plan/close-review" in js
    assert "/abandon" in js
    assert "Confirm exact resources — no broker changes" in js


def test_cleanup_ui_has_no_provider_cleanup_execution_path() -> None:
    html = _text("index.html")
    js = _text("app.js")
    combined = html + "\n" + js

    assert "/cleanup-plan/process" not in combined
    assert "cancel_order(" not in combined
    assert "cancel_order_by_id(" not in combined
    assert "close_position(" not in combined
    assert "close_all_positions(" not in combined
    assert "provider_write_authorized !== false" in js
    assert "provider_write_endpoints_present !== false" in js
    assert "provider_write_attempted !== false" in js
    assert "provider_write_endpoint_invoked !== false" in js


def test_cleanup_ui_static_assets_remain_bounded() -> None:
    for name in ("index.html", "app.css", "app.js"):
        path = WEB_ROOT / name
        assert path.is_file()
        assert 0 < path.stat().st_size <= 1024 * 1024
