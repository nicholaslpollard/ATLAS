from __future__ import annotations

"""Offline source-original SPY five-session exit fault census.

Reads the frozen V9-derived query identities and immutable V19 receipts.
Verifies original stored gzip bodies and SHA hashes through V19 state gates,
then checks observed quote ROWS for archived invalid-schema sources.
No SDK, network, provider request, repair, retry, fills or source promotion.

V19 terminal receipts retain exception TYPE but not original exception
message; original SDK transport metadata are not in the compressed body.
Row-only rechecks may therefore isolate original bad fields or report that
the error was metadata-dependent. Do not misrepresent reconstruction as
historical provider provenance.
"""

from collections import Counter
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    PINNED_MANIFEST_FINGERPRINT, _load_full_manifest,
)
from packages.data.options_native_exit_source_campaign_v1 import (
    _demand, _diagnose_rows, _path, _receipt, _state,
)
from scripts.run_options_native_spy_exit_source_campaign_v1 import (
    DEFAULT_MANIFEST, DEFAULT_CANDIDATE,
)

ABNORMAL_STATES = frozenset({
    "RAW_ARCHIVED_INVALID_SCHEMA",
    "PROVIDER_OR_STORAGE_ERROR_NO_RETRY",
    "UNCERTAIN_PRIOR_ATTEMPT_NO_RETRY",
})


def audit(settings, manifest: Path, candidate_plan: Path) -> dict:
    settings.assert_external_storage_binding("options")
    plan = _demand(_load_full_manifest(settings, manifest, candidate_plan))
    stats = Counter()
    findings = []
    for req in plan["requests"]:
        qid = req["query_id"]
        state = _state(settings, req, plan["plan_fingerprint"])
        stats[state] += 1
        if state not in ABNORMAL_STATES:
            continue
        terminal = _receipt(
            settings, req, plan["plan_fingerprint"], "terminal",
        )
        result = {
            "session_et": req["session_et"],
            "query_id": qid,
            "state": state,
            "recorded_error_type": (
                None if terminal is None else terminal.get("error_type")
            ),
            "provider_failure_class": (
                None if terminal is None else terminal.get("provider_failure_class")
            ),
            "provider_grpc_status": (
                None if terminal is None else terminal.get("provider_grpc_status")
            ),
            "archive_present": (
                terminal is not None and terminal.get("archive") is not None
            ),
            "row_only_diagnostic": "NO_ORIGINAL_ROWS_RETAINED",
        }
        if state == "RAW_ARCHIVED_INVALID_SCHEMA":
            # _state has ALREADY verified compressed/original SHA, bounds
            # and canonical raw bytes. Only now parse the original again.
            archive = terminal["archive"]
            path = _path(settings, qid, "sources")
            rows = json.loads(gzip.decompress(path.read_bytes()))
            try:
                rows_state = _diagnose_rows(req, rows)
                result["row_only_diagnostic"] = (
                    "ROWS_PASS_LOCAL_CHECK_METADATA_CAUSE_UNRESOLVED"
                    f" local_classification={rows_state}"
                )
            except Exception as exc:
                if type(exc).__name__ == "SpyExitSourceError":
                    code = str(exc)
                else:
                    # Do not print raw provider values or exception messages.
                    code = type(exc).__name__
                result["row_only_diagnostic"] = (
                    f"ORIGINAL_ROW_CHECK_FAILED code={code}"
                )
            result["archived_rows"] = archive["observed_rows"]
            result["original_sha256"] = archive["original_sha256"]
        findings.append(result)
    return {
        "contract": "atlas-spy-exit-frozen-source-fault-audit-v21",
        "plan_fingerprint": plan["plan_fingerprint"],
        "total_new_exit_ids": len(plan["requests"]),
        "source_states": dict(sorted(stats.items())),
        "abnormal_identities": findings,
        "provider_requests": 0,
        "broker_requests": 0,
        "files_written": 0,
        "simulations_run": 0,
        "source_promoted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    args = parser.parse_args(argv)
    print("ATLAS V21 EXIT ORIGINAL-RECEIPT FAULT AUDIT", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        result = audit(settings, args.manifest, args.candidate_plan)
        print(
            f"  source_states={result['source_states']}"
            f" abnormal_count={len(result['abnormal_identities'])}"
            f" plan_fp={result['plan_fingerprint']}", flush=True,
        )
        for issue in result["abnormal_identities"]:
            print(
                f"  ABNORMAL date={issue['session_et']}"
                f" query_id={issue['query_id']}"
                f" state={issue['state']}"
                f" error_type={issue['recorded_error_type']}"
                f" provider_class={issue['provider_failure_class']}"
                f" grpc_status={issue['provider_grpc_status']}"
                f" archive_present={issue['archive_present']}"
                f" row_check={issue['row_only_diagnostic']}",
                flush=True,
            )
        print(
            "  COMPLETE: provider_requests=0 files_written=0"
            " original_hashes_checked=True source_promoted=False"
            " simulations_run=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"  BLOCKED: {type(exc).__name__}"
            " no_automatic_retry=True files_written=0", flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
