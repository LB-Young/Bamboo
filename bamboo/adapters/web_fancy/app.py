"""Alternative FastAPI application entry for the Bamboo fancy web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from bamboo.adapters.web.app import create_app as create_web_app

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create the Bamboo fancy web application."""
    return create_web_app(static_dir=STATIC_DIR, title="Bamboo Fancy Web")


app = create_app()
