from __future__ import annotations

"""Run a changing strategy's historical option source demands through cache."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.simulation.strategy_options_source_runtime_v39 import (
    resolve_strategy_source_demands,
)

MAX_LINE_BYTES = 16 * 1024


def demands_from_jsonl(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("STRATEGY_SOURCE_DEMAND_STREAM_NOT_FOUND")
    # Stream a demand file; do not impose a file-size or requirement-count cap.
    # Every individual query remains bounded to prevent pathological input.
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                raise ValueError(f"STRATEGY_SOURCE_DEMAND_LINE_TOO_LARGE:{line_number}")
            obj = json.loads(line)
            yield obj


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-version", required=True)
    parser.add_argument("--demands-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args(argv)

    print("ATLAS V39 DYNAMIC STRATEGY HISTORICAL SOURCE RESOLUTION")
    print("  mode=ON_DEMAND_CACHE_THEN_PROVIDER_AND_PERSIST")
    print("  provider activity determined by requested sources and cached evidence")
    try:
        if args.output.is_symlink() or args.output.exists():
            raise ValueError("OUTPUT_EXISTS_OR_LINKED")
        settings = load_settings(ROOT, "development")
        result = resolve_strategy_source_demands(
            settings, args.strategy_version,
            demands_from_jsonl(args.demands_jsonl),
            continue_on_error=args.continue_on_error,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, sort_keys=True)
            out.write("\n")
        print(
            f"  requirements={result['source_uses_requested']}"
            f" present={result['source_uses_resolved']}"
            f" explicitly_unavailable={result['source_uses_explicit_no_data']}"
            f" failed_or_pending={result['source_uses_failed_or_unresolved']}"
        )
        print(
            f"  fetched_and_saved={result['provider_fetch_successes']}"
            f" reused_cached={result['persisted_cache_hits']}"
        )
        print(f"  {result['status']}")
        print(f"  saved={args.output}")
        return 0 if result["status"] == "ALL_REQUESTED_SOURCES_PRESENT" else 2
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        # No historical source is fabricated or silently bypassed on failure.
        print(f"  STOPPED: {type(exc).__name__}: {str(exc)[:240]}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
