from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from packages.backtesting.b35_development_source import (
    B35DevelopmentSourceError,
    _load_frozen_minute_plan,
)
from packages.data.alpaca_v2_rebuild import V2Layout


def test_native_plan_manifest_symlink_is_rejected_before_read(tmp_path: Path) -> None:
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    layout.create()

    external = tmp_path / "outside-native-plan-manifest.json"
    external.write_text(
        json.dumps(
            {
                "contract": "external-not-trusted",
                "status": "FROZEN",
                "v1_ancestry": "FORBIDDEN",
            }
        ),
        encoding="utf-8",
    )
    manifest = layout.manifests / "native_acquisition_plan.json"
    try:
        manifest.symlink_to(external)
    except OSError:
        pytest.skip("symlink creation is not permitted on this platform")

    with pytest.raises(B35DevelopmentSourceError, match="symlink"):
        _load_frozen_minute_plan(
            layout,
            start_session=date(2026, 4, 1),
            end_session=date(2026, 4, 30),
        )
