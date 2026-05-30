"""SQLite journal connection, schema bootstrap, and lightweight migrations."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "journal.sqlite"
SCHEMA_PATH = PROJECT_ROOT / "journal" / "schema.sql"


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_database(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    ensure_data_folders(PROJECT_ROOT)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(db_path) as connection:
        connection.executescript(schema_sql)
        _migrate_existing_tables(connection, schema_sql)


def ensure_data_folders(project_root: Path = PROJECT_ROOT) -> None:
    folders = [
        "data/screenshots",
        "data/exports",
        "data/reports/daily",
        "data/reports/weekly",
        "data/reports/model_feedback",
        "data/emergency_logs",
        "data/backups",
    ]
    for folder in folders:
        (project_root / folder).mkdir(parents=True, exist_ok=True)


def _migrate_existing_tables(connection: sqlite3.Connection, schema_sql: str) -> None:
    """Add missing columns when an older V0.1 draft table already exists."""
    for table_name, column_defs in _parse_create_tables(schema_sql).items():
        existing = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if not existing:
            continue
        for column_name, column_def in column_defs.items():
            if column_name not in existing:
                connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")


def _parse_create_tables(schema_sql: str) -> dict[str, dict[str, str]]:
    tables: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(schema_sql):
        table = match.group(1)
        body = match.group(2)
        columns: dict[str, str] = {}
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            upper = line.upper()
            if upper.startswith(("PRIMARY ", "FOREIGN ", "UNIQUE ", "CHECK ", "CONSTRAINT ")):
                continue
            column_name = line.split()[0]
            columns[column_name] = line
        tables[table] = columns
    return tables
