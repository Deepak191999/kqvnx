"""Vercel serverless entrypoint.

Vercel treats every file under /api as a function and forwards the original
request path to an exported ASGI `app`, so the FastAPI routers keep their
/api prefix unchanged and no rewriting is needed on the Python side.

The backend package lives in ./backend, which is not on the function's import
path by default, so it is added here before importing the application.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# The deployment bundle is mounted read-only, so the snapshot must be opened
# without SQLite trying to create a journal next to it.
os.environ.setdefault("READ_ONLY_DB", "1")
os.environ.setdefault("DB_PATH", str(BACKEND / "data" / "wind.db"))

from app.main import app  # noqa: E402

__all__ = ["app"]
