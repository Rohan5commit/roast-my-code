"""Vercel serverless function entry point."""
import sys
import os

# Ensure web/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web.api.roast import handler  # noqa: F401, E402
