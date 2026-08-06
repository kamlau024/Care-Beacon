"""REST API module for Care-Beacon.

Provides FastAPI endpoints for the RAG system.

This package intentionally does NOT import ``app`` at package level. Vercel's
Python runtime loads ``src/api/main.py`` directly by file path, so this
``__init__`` has not run when ``main`` starts executing. ``main`` then does
``from src.api.models import ...``, which triggers this module — and an eager
``from src.api.main import app`` here fails with ImportError, because ``app``
is not defined until roughly 70 lines further down ``main``.

Import the app from its own module instead::

    from src.api.main import app
"""
