"""CSV export helpers for journal datasets."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def export_query(connection: sqlite3.Connection, query: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = connection.execute(query).fetchall()
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        if not rows:
            handle.write("")
            return output_path
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return output_path


def export_ai_training_view(connection: sqlite3.Connection, output_path: Path) -> Path:
    return export_query(connection, "SELECT * FROM ai_training_view", output_path)
