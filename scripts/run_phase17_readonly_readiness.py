from __future__ import annotations

import json

from packages.control_plane.phase17_readiness import Phase17ProviderReadiness
from packages.core.settings import load_settings


def main() -> None:
    report = Phase17ProviderReadiness(load_settings()).run()
    print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
