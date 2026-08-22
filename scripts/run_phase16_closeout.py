from __future__ import annotations

import json

from packages.control_plane.phase16_closeout import Phase16Closeout
from packages.core.settings import load_settings


def main() -> None:
    report = Phase16Closeout(load_settings()).run()
    print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
