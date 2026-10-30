"""Helpers for validating Qloo entity IDs used as insight signals."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Qloo entity IDs are UUIDs. Demo/local/unresolved placeholders must never be sent live.
_QLOO_ENTITY_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_qloo_entity_id(value: str | None) -> bool:
    """Return True when value looks like a real Qloo entity UUID."""
    if not value or not isinstance(value, str):
        return False
    return bool(_QLOO_ENTITY_UUID_RE.match(value.strip()))


def filter_qloo_entity_ids(entity_ids: Iterable[str | None]) -> tuple[list[str], int]:
    """Keep UUID-shaped IDs only.

    Returns ``(valid_ids, skipped_count)`` with order preserved and duplicates removed.
    """
    valid: list[str] = []
    seen: set[str] = set()
    skipped = 0
    for raw in entity_ids:
        if raw is None:
            skipped += 1
            continue
        eid = raw.strip()
        if not eid:
            skipped += 1
            continue
        if is_qloo_entity_id(eid):
            if eid not in seen:
                seen.add(eid)
                valid.append(eid)
            continue
        skipped += 1
    return valid, skipped


def skipped_favorites_note(skipped_count: int) -> str | None:
    """Limitation / notes text when favorites could not be used as Qloo signals."""
    if skipped_count <= 0:
        return None
    noun = "favorite" if skipped_count == 1 else "favorites"
    return (
        f"Skipped {skipped_count} {noun} without a valid Qloo entity ID; "
        "they will not influence recommendations."
    )
