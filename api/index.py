"""Vercel Python Function entrypoint for the FastAPI routes under /api."""

from src.app.api import app

__all__ = ["app"]
