"""Fail if a configured QLOO_API_KEY appears in the Next.js build output."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_key() -> str:
    for path in (ROOT / ".env", ROOT / "apps" / "api" / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("QLOO_API_KEY=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def main() -> int:
    key = load_key()
    print(f"key_configured={bool(key)} len={len(key)}")
    root = ROOT / "apps" / "web" / ".next"
    if not root.exists():
        print("no_next_build skip")
        return 0
    if not key:
        print("no_key_to_scan skip")
        return 0

    leaks: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".map"} or path.name.endswith(".nft.json"):
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if key.encode("utf-8") in data:
            leaks.append(str(path.relative_to(ROOT)))

    print(f"bundle_leaks={len(leaks)}")
    for item in leaks[:20]:
        print(f"LEAK {item}")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
