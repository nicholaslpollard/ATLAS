from __future__ import annotations

"""Deprecated compatibility shim for the retired ThetaData Terminal preflight."""


def main(argv: list[str] | None = None) -> int:
    print("ATLAS THETADATA TERMINAL PREFLIGHT — SUPERSEDED", flush=True)
    print(
        "  The active ATLAS ThetaData path uses the direct ThetaData Python library. "
        "Theta Terminal and Java are not required.",
        flush=True,
    )
    print(
        "  Use scripts/preflight_thetadata_python_library_v1.py after the "
        "ThetaData subscription/API key is available.",
        flush=True,
    )
    print("  provider_requests=0", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
