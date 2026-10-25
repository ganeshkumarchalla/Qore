"""Vercel ASGI entrypoint for QORE's backend API."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from qore.main import app  # noqa: E402
