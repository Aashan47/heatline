"""Vercel entrypoint.

Vercel builds a Python framework app into one function from its resolved
entrypoint, so this just re-exports the same FastAPI app the container and the
local server use. There is no Vercel-specific code path: whatever is true of
the app here is true everywhere.
"""

from heatline.service import app

__all__ = ["app"]
