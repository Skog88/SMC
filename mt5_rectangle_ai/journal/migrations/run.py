"""Apply pending SQL migration files to the journal database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent
DB_PATH = MIGRATIONS_DIR.parent.parent / "data" / "journal.sqlite"


def run_migrations(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"Database not found at {db_path} — nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    for path in migration_files:
        print(f"Applying {path.name}...")
        statements = [s.strip() for s in path.read_text(encoding="utf-8").split(";") if s.strip()]
        for stmt in statements:
            if stmt.startswith("--"):
                continue
            try:
                conn.execute(stmt)
                conn.commit()
            except sqlite3.OperationalError as exc:
                if "duplicate column name" in str(exc).lower():
                    print(f"  already applied: {stmt[:60]}...")
                else:
                    raise

    conn.close()
    print("Migrations complete.")


if __name__ == "__main__":
    run_migrations()
