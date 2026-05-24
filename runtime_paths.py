from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundle_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(str(meipass)).resolve()
    return app_root()


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def writable_path(*parts: str) -> Path:
    return app_root().joinpath(*parts)


def resolve_runtime_path(value: str | Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate

    search_roots = [bundle_root(), app_root(), Path.cwd()]
    for root in search_roots:
        resolved = root / candidate
        if resolved.exists():
            return resolved

    return bundle_root() / candidate
