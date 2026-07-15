"""Vercel serverless function: re-exports handler from web/api/roast.py."""
import importlib.util
import os
import sys

# Load web/api/roast.py as a module (no __init__.py needed)
_spec = importlib.util.spec_from_file_location(
    "web_api_roast",
    os.path.join(os.path.dirname(__file__), "..", "web", "api", "roast.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

handler = _mod.handler  # noqa: F841
