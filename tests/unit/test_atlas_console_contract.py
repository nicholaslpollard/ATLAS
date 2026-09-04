from __future__ import annotations

from pathlib import Path

from packages.control_plane.phase19_http_server import (
    _PHASE19_OBSERVABILITY_BUNDLE,
    _PHASE19_STATIC_ASSETS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "apps" / "web"


def test_console_assets_are_part_of_phase19_read_only_surface() -> None:
    expected_tail = (
        "atlas_console.js",
        "atlas_overview_style.js",
        "atlas_overview.js",
        "atlas_tabs.js",
        "atlas_console_runtime.js",
    )
    assert _PHASE19_OBSERVABILITY_BUNDLE[-5:] == expected_tail
    assert _PHASE19_STATIC_ASSETS["/assets/atlas_console.css"][0] == "atlas_console.css"
    assert _PHASE19_STATIC_ASSETS["/assets/atlas_overview.css"][0] == "atlas_overview.css"
    assert _PHASE19_STATIC_ASSETS["/assets/atlas_tabs.css"][0] == "atlas_tabs.css"
    assert _PHASE19_STATIC_ASSETS["/assets/atlas_status.css"][0] == "atlas_status.css"

    for filename in (
        "atlas_console.js",
        "atlas_console_runtime.js",
        "atlas_console.css",
        "atlas_overview_style.js",
        "atlas_overview.js",
        "atlas_overview.css",
        "atlas_tabs.js",
        "atlas_tabs.css",
        "atlas_status.css",
    ):
        path = WEB_ROOT / filename
        assert path.is_file()
        assert path.stat().st_size > 0


def test_console_groups_operator_pages_by_real_data_domains() -> None:
    source = (WEB_ROOT / "atlas_console.js").read_text(encoding="utf-8")
    expected_pages = (
        "Overview",
        "Market",
        "Research",
        "Portfolio",
        "Execution",
        "Brokers & Data",
        "Operations",
        "Controls",
    )
    for label in expected_pages:
        assert f'"{label}"' in source

    assert "Autonomous Trading, Learning & Analysis System" not in source
    assert "atlas-brand-name\", \"ATLAS\"" in source
    assert "Automatic failover" in source
    assert 'atlasSet("atlas-ctl-failover", "DISABLED")' in source
    assert 'atlasSet("atlas-ctl-live", "DISABLED")' in source
    assert 'atlasSet("atlas-ctl-browser", "READ ONLY")' in source


def test_overview_is_summary_only_and_drills_into_domain_pages() -> None:
    source = (WEB_ROOT / "atlas_overview.js").read_text(encoding="utf-8")
    for label in (
        "DISCOVERY SUMMARY",
        "CANDIDATES",
        "FEATURED CASE",
        "MARKET SNAPSHOT",
        "PORTFOLIO SUMMARY",
        "RECENT AI REVIEWS",
        "OPERATIONS / PIPELINE",
        "DATA FEEDS",
    ):
        assert label in source

    for page in ("market", "portfolio", "research", "operations"):
        assert f'"{page}"' in source

    assert "fetch(" not in source
    assert "XMLHttpRequest" not in source


def test_detail_pages_use_tabs_only_for_existing_data_domains() -> None:
    source = (WEB_ROOT / "atlas_tabs.js").read_text(encoding="utf-8")
    expected_tabs = (
        "Candidates",
        "Live Data",
        "Strategies & Replay",
        "AI Review",
        "Account & Positions",
        "Evidence Health",
        "Decision & Order Lifecycle",
        "Outcomes",
        "Broker Accounts",
        "Market Inputs",
        "Pipeline",
        "Actions",
        "Lineage",
    )
    for label in expected_tabs:
        assert f'"{label}"' in source

    assert "fetch(" not in source
    assert "XMLHttpRequest" not in source
    assert "provider" not in source.lower()
    assert "broker" in source.lower()


def test_codespaces_launcher_adds_console_without_changing_preview_write_boundary() -> None:
    source = (PROJECT_ROOT / "scripts" / "run_phase19_preview.py").read_text(encoding="utf-8")
    assert '"atlas_console.css"' in source
    assert '"atlas_overview.css"' in source
    assert '"atlas_tabs.css"' in source
    assert '"atlas_status.css"' in source
    assert '"atlas_console.js"' in source
    assert '"atlas_overview_style.js"' in source
    assert '"atlas_overview.js"' in source
    assert '"atlas_tabs.js"' in source
    assert '"atlas_console_runtime.js"' in source
    assert 'print("  POST requests: disabled")' in source
    assert 'print("  production loopback guard: unchanged")' in source
