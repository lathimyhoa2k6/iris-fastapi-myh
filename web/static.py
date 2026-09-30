"""Static files of the web module, served so a new deploy is picked up on the next page load."""

from __future__ import annotations

from fastapi.staticfiles import StaticFiles


class WebStaticFiles(StaticFiles):
    """StaticFiles with `Cache-Control: no-cache`.

    Without it browsers cache app.js and the page modules heuristically and keep
    running the previous version after a deploy (a new sidebar page stays hidden).
    no-cache still allows caching: every load revalidates with the ETag, and an
    unchanged file costs only a 304.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response
