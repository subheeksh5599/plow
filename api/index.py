"""Vercel serverless entrypoint — imports the Plow ASGI app.

The app itself parses scope["headers"] for BYOK (Authorization/x-api-key wins over
env KH_API_KEY) — never call handlers directly from a wrapper (the keepersense
serverless trap).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from plow import app  # noqa: E402,F401
