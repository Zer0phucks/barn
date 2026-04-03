"""Vercel entrypoint shim. Vercel's Flask framework detection expects index.py."""
from app import app  # noqa: F401 — re-export for Vercel
