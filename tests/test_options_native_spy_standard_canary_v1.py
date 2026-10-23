from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from packages.data.options_native_spy_standard_canary_v1 import (
    canary_design, run_single_canary, PilotQuoteSourceError,
)
from packages.providers.thetadata.client import ThetaDataError
from tests.test_options_native_spy_thetadata_quote_qualification_v1 import make_response


class FakeSettings:
    def __init__(self, root):
        self.root = root
    def assert_external_storage_binding(self, category):
        assert category == "options"
    def resolved_path(self, relative):
        return self.root / relative


def test_reuses_one_exact_2025_original_anchor_without_2018_fallback():
    from packages.data.options_native_spy_thetadata_quote_qualification_v1 import quote_design
    full = quote_design()
    canary = canary_design()
    assert canary["source_design_fingerprint"] == (
        "73369c3d84d35ac90fea4abb2abec0a72dd858065add7d0613c3c79c7d44167e"
    )
    assert canary["selected_anchor"] in full["quote_source_calls"]
    assert canary["selected_anchor"]["reason"] == "2025_MIDDLE"
    assert canary["maximum_provider_quote_method_calls"] == 1
    assert canary["paid_access_confirmed_by_design"] is False
    assert canary["provider_requests"] == 0


@pytest.mark.parametrize("flags", [
    {},
    {"authorize_one_standard_quote": True},
    {"confirm_thetadata_standard": True},
    {"acknowledge_one_quote_method_call": True},
    {"authorize_one_standard_quote": True, "confirm_thetadata_standard": True},
    {"authorize_one_standard_quote": True, "acknowledge_one_quote_method_call": True},
    {"confirm_thetadata_standard": True, "acknowledge_one_quote_method_call": True},
])
def test_source_call_requires_three_explicit_flags_even_with_injected_reader(tmp_path,flags):
    seen = []
    with pytest.raises(PilotQuoteSourceError, match="NOT_AUTHORIZED"):
        run_single_canary(FakeSettings(tmp_path), reader=lambda **kwargs: seen.append(kwargs), **flags)
    assert seen == [] and list(tmp_path.iterdir()) == []


def test_one_successful_2025_call_preserves_receipt_without_promotion(tmp_path):
    seen = []
    def reader(**kwargs):
        seen.append(kwargs)
        return make_response({"start_date": kwargs["date_et"]})
    result = run_single_canary(
        FakeSettings(tmp_path), reader=reader,
        authorize_one_standard_quote=True,confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    assert len(seen) == 1
    assert seen[0]["right"] == "both"
    assert seen[0]["max_dte"] == 45
    assert seen[0]["strike_range"] == 2
    assert seen[0]["time_of_day_et"] == "10:00:00.000"
    assert result["provider_result"] == "OBSERVED_BOTH_RIGHTS_CLOCK_DIAGNOSTIC"
    assert result["requests_attempted"] == 1
    assert result["quote_diagnostics"]["clock_qualified_common_pairs"] == 1
    assert result["source_accepted"] is result["historical_replay_authority"] is False
    assert result["protected_outcomes_read"] == 0
    stored = json.loads(Path(result["report_path"]).read_text())
    assert stored["report_fingerprint"] == result["report_fingerprint"]
    assert Path(stored["source_receipt_path"]).is_file()


def test_entitlement_denial_is_one_attempt_only_and_never_leaks_text(tmp_path):
    attempts = []
    def denied(**kwargs):
        attempts.append(kwargs)
        raise ThetaDataError("SECRET_VALUES_MUST_NOT_LEAK",http_status=403)
    result = run_single_canary(
        FakeSettings(tmp_path), reader=denied,
        authorize_one_standard_quote=True,confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    assert len(attempts) == 1
    assert result["provider_result"] == "METHOD_TRANSPORT_OR_ENTITLEMENT_ERROR"
    assert result["provider_http_status"] == 403
    assert "SECRET_VALUES_MUST_NOT_LEAK" not in Path(result["report_path"]).read_text()
    assert result["sdk_normalized_response_bytes_retained"] is False
    assert result["source_accepted"] is False


@pytest.mark.parametrize("direct", [True, False])
def test_cli_defaults_to_zero_provider_and_partial_auth_is_blocked(direct):
    root = Path(__file__).resolve().parents[1]
    module = "scripts.probe_options_native_spy_standard_canary_v1"
    cmd = ([sys.executable, str(root/"scripts"/"probe_options_native_spy_standard_canary_v1.py")]
           if direct else [sys.executable,"-m",module])
    result = subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stderr
    assert "ONE_ANCHOR_DESIGN_ZERO_READS" in result.stdout
    stopped = subprocess.run([*cmd,"--confirm-thetadata-standard"],cwd=root,
                             capture_output=True,text=True,timeout=30)
    assert stopped.returncode == 2
    assert "BLOCKED_PARTIAL_ONE_QUOTE_AUTHORIZATION" in stopped.stdout
