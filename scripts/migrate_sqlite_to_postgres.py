"""Migrate existing data from SQLite (tasteos.db) to PostgreSQL.

Usage:
  python scripts/migrate_sqlite_to_postgres.py [--sqlite-path PATH] [--pg-url URL]

Default sqlite-path: apps/api/data/tasteos.db
Default pg-url: from DATABASE_URL in .env
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Add apps/api to path so app models are importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import get_settings
from app.models.profile import TasteProfile
from app.models.recommendation import RecommendationRecord


def _safe_json(val: str | None) -> list | dict:
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def migrate(sqlite_path: Path, pg_url: str) -> None:
    if not sqlite_path.exists():
        print(f"Error: SQLite database not found at {sqlite_path}")
        sys.exit(1)

    # Convert async psycopg URL to sync for straightforward batch insert
    sync_pg_url = pg_url.replace("postgresql+psycopg://", "postgresql+psycopg://")
    if sync_pg_url.startswith("postgresql://") and not sync_pg_url.startswith("postgresql+"):
        sync_pg_url = "postgresql+psycopg://" + sync_pg_url[len("postgresql://") :]

    print(f"Reading from SQLite: {sqlite_path}")
    print(f"Target PostgreSQL:   {sync_pg_url.split('@')[-1] if '@' in sync_pg_url else sync_pg_url}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    pg_engine = create_engine(sync_pg_url, echo=False)

    # 1. Migrate TasteProfiles
    profiles_migrated = 0
    profiles_skipped = 0
    try:
        sqlite_cur.execute("SELECT * FROM taste_profiles")
        sqlite_profiles = sqlite_cur.fetchall()
        print(f"\nFound {len(sqlite_profiles)} profile(s) in SQLite.")

        with Session(pg_engine) as session:
            for row in sqlite_profiles:
                existing = session.scalar(
                    select(TasteProfile).where(TasteProfile.id == row["id"])
                )
                if existing:
                    profiles_skipped += 1
                    continue

                profile = TasteProfile(
                    id=row["id"],
                    display_name=row["display_name"],
                    favorites=_safe_json(row["favorites"]) if isinstance(row["favorites"], str) else (row["favorites"] or []),
                    preferred_domains=_safe_json(row["preferred_domains"]) if isinstance(row["preferred_domains"], str) else (row["preferred_domains"] or []),
                    exclusions=_safe_json(row["exclusions"]) if isinstance(row["exclusions"], str) else (row["exclusions"] or []),
                    explicit_preferences=_safe_json(row["explicit_preferences"]) if isinstance(row["explicit_preferences"], str) else (row["explicit_preferences"] or []),
                    notes=row["notes"],
                    is_demo=bool(row["is_demo"]),
                )
                session.add(profile)
                profiles_migrated += 1
            session.commit()
    except sqlite3.OperationalError as e:
        print(f"Note: taste_profiles table in SQLite: {e}")

    # 2. Migrate Recommendations
    recs_migrated = 0
    recs_skipped = 0
    try:
        sqlite_cur.execute("SELECT * FROM recommendations")
        sqlite_recs = sqlite_cur.fetchall()
        print(f"Found {len(sqlite_recs)} recommendation record(s) in SQLite.")

        with Session(pg_engine) as session:
            for row in sqlite_recs:
                existing = session.scalar(
                    select(RecommendationRecord).where(RecommendationRecord.id == row["id"])
                )
                if existing:
                    recs_skipped += 1
                    continue

                rec = RecommendationRecord(
                    id=row["id"],
                    kind=row["kind"],
                    mode=row["mode"],
                    request_payload=_safe_json(row["request_payload"]) if isinstance(row["request_payload"], str) else (row["request_payload"] or {}),
                    response_payload=_safe_json(row["response_payload"]) if isinstance(row["response_payload"], str) else (row["response_payload"] or {}),
                    rejected_entity_ids=_safe_json(row["rejected_entity_ids"]) if isinstance(row["rejected_entity_ids"], str) else (row["rejected_entity_ids"] or []),
                )
                session.add(rec)
                recs_migrated += 1
            session.commit()
    except sqlite3.OperationalError as e:
        print(f"Note: recommendations table in SQLite: {e}")

    sqlite_conn.close()
    print("\nMigration Summary:")
    print(f"  Profiles:        {profiles_migrated} inserted, {profiles_skipped} skipped (already present)")
    print(f"  Recommendations: {recs_migrated} inserted, {recs_skipped} skipped (already present)")
    print("\nMigration complete!")


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=ROOT / "apps" / "api" / "data" / "tasteos.db",
        help="Path to source SQLite tasteos.db",
    )
    parser.add_argument(
        "--pg-url",
        type=str,
        default=settings.database_url,
        help="Target PostgreSQL DATABASE_URL",
    )
    args = parser.parse_args()
    migrate(args.sqlite_path, args.pg_url)


if __name__ == "__main__":
    main()
