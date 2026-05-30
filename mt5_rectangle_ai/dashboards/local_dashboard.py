"""Minimal local dashboard placeholder.

Phase 4 should replace this with a real dashboard once journal data exists.
"""

from __future__ import annotations

from journal.db import connect
from journal.reports import setup_counts_by_status


def print_summary() -> None:
    with connect() as connection:
        for row in setup_counts_by_status(connection):
            print(f"{row['status']}: {row['count']}")


if __name__ == "__main__":
    print_summary()
