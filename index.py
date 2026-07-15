"""Vercel serverless function entry point."""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "roast_handler",
    os.path.join(os.path.dirname(__file__), "web", "api", "roast.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

handler = _mod.handler
