from __future__ import annotations

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
    for endpoint in store.list_endpoints():
        try:
            status = profiles.stop(endpoint["profile"])
            print(f"{endpoint['profile']}: {status['status']}")
        except Exception as exc:
            print(f"{endpoint['profile']}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

