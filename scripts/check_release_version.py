from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sciplot.version import APP_VERSION  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_release_version.py <tag>")
    tag_version = sys.argv[1].lstrip("v")
    if tag_version != APP_VERSION:
        raise SystemExit(f"Release tag {tag_version} does not match APP_VERSION {APP_VERSION}.")
    print(APP_VERSION)


if __name__ == "__main__":
    main()
