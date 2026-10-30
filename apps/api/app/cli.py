"""TasteOS CLI — diagnostic commands.

Usage (from apps/api with venv active, or via editable install):
  python -m app.cli mode
  python -m app.cli check-qloo

Never prints QLOO_API_KEY or other secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from urllib.parse import urlparse

from app.core.config import get_settings
from app.services.qloo.client import HACKATHON_BASE_URL, QlooClient, QlooError


def cmd_mode(_: argparse.Namespace) -> int:
    settings = get_settings()
    payload = {
        "mode": settings.tasteos_mode,
        "qloo_key_configured": settings.qloo_configured,
        "qloo_base_url_host": urlparse(settings.qloo_base_url).netloc,
        "expected_hackathon_host": urlparse(HACKATHON_BASE_URL).netloc,
        "key_length": (
            len(settings.qloo_api_key.strip()) if settings.qloo_api_key else 0
        ),
        "timeout_seconds": settings.qloo_timeout_seconds,
        "max_retries": settings.qloo_max_retries,
    }
    print(json.dumps(payload, indent=2))
    return 0


async def _check_qloo() -> int:
    settings = get_settings()
    configured = settings.qloo_configured
    host = urlparse(settings.qloo_base_url).netloc
    print(
        f"QLOO_API_KEY configured: {configured} (length={len(settings.qloo_api_key.strip()) if configured else 0})"
    )
    print(f"QLOO_BASE_URL host: {host}")
    print(f"Expected hackathon host: {urlparse(HACKATHON_BASE_URL).netloc}")
    if not configured:
        print(
            "BLOCKED: Set QLOO_API_KEY to run a live connectivity check. "
            "Mocked unit tests still validate request construction and parsing. "
            "Use TASTEOS_MODE=demo for labeled sample data."
        )
        print(
            "Key form: "
            "https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide#getting-your-api-key"
        )
        return 2
    try:
        async with QlooClient(settings) as client:
            result = await client.health_probe()
        # Defensive: never dump unexpected secret-like keys if schema grows.
        sanitized = {
            k: v
            for k, v in result.items()
            if "key" not in k.lower() or k in {"key_configured"}
        }
        print(json.dumps(sanitized, indent=2))
        if result.get("ok"):
            print("OK: Live Qloo probe succeeded (search -> insights).")
            return 0
        print("FAIL: Probe completed but returned ok=false.")
        return 1
    except QlooError as exc:
        print(f"FAIL: {exc} (status={exc.status_code})")
        return 1


def cmd_check_qloo(_: argparse.Namespace) -> int:
    return asyncio.run(_check_qloo())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tasteos", description="TasteOS diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)

    p_mode = sub.add_parser("mode", help="Show configured TasteOS mode without secrets")
    p_mode.set_defaults(func=cmd_mode)

    p_check = sub.add_parser(
        "check-qloo",
        help="Probe live Qloo connectivity (requires QLOO_API_KEY); prints sanitized summary",
    )
    p_check.set_defaults(func=cmd_check_qloo)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
