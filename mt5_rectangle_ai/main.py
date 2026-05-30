"""Local entry point for the MT5 rectangle AI daemon."""

from __future__ import annotations

from pathlib import Path

from journal.db import initialize_database


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    initialize_database(PROJECT_ROOT / "data" / "journal.sqlite")
    print("mt5_rectangle_ai initialized. Phase 1 rule engine modules are ready.")


if __name__ == "__main__":
    main()
