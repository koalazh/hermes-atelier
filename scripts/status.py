from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from plugin.atelier.services.profiles import ProfileService  # noqa: E402
from plugin.atelier.store import AtelierStore  # noqa: E402


def main() -> int:
    store = AtelierStore()
    profiles = ProfileService(store)
    statuses = [profiles.status(item["profile"]) for item in store.list_endpoints()]
    print(json.dumps(statuses, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
