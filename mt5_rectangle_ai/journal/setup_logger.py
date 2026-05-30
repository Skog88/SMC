"""Compatibility wrappers for setup journaling."""

from __future__ import annotations

import json
from typing import Any

from journal.journal import Journal


def upsert_setup(
    connection_or_journal: object,
    setup: dict[str, Any],
    status: str,
    skip_reason: str | None = None,
) -> None:
    journal = connection_or_journal if isinstance(connection_or_journal, Journal) else Journal()
    setup = dict(setup)
    setup["state"] = status
    setup["skip_reason"] = skip_reason
    journal.create_setup(setup)


def setup_as_json(setup: dict[str, Any]) -> str:
    return json.dumps(setup, indent=2, sort_keys=True)
