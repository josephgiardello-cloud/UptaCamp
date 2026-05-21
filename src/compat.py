"""Compatibility entry points during staged migration.

This module centralizes calls into legacy runtime modules so top-level
entry points can depend on src/ rather than importing legacy modules directly.
"""

from __future__ import annotations


def run_classic_client() -> int:
    """Run the legacy classic client entry point."""
    import cribbage_pygame as classic_client

    return int(classic_client.main() or 0)
