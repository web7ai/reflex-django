"""Django HTTP middleware for ASGI-safe streaming responses."""

from __future__ import annotations

from typing import Any

from asgiref.sync import sync_to_async
from django.utils.deprecation import MiddlewareMixin


def _is_asgi_request(request: Any) -> bool:
    """True when the request was created by Django's ASGI handler."""
    return getattr(request, "scope", None) is not None


class AsyncStreamingMiddleware(MiddlewareMixin):
    """Convert sync :class:`~django.http.StreamingHttpResponse` iterators for ASGI.

    Django's ASGI handler warns when ``send_response`` must adapt a synchronous
    streaming iterator via ``sync_to_async``. This middleware marks those
    responses as async before they reach the handler (same approach as
    :class:`django.contrib.staticfiles.handlers.ASGIStaticFilesHandler`).

    Uses :class:`~django.utils.deprecation.MiddlewareMixin` so the class works
    in both sync and async middleware chains (``sync_capable`` and
    ``async_capable``). Conversion runs only for ASGI requests; WSGI
    responses are left unchanged.
    """

    def process_response(self, request: Any, response: Any) -> Any:
        if not _is_asgi_request(request):
            return response
        if not getattr(response, "streaming", False):
            return response
        if getattr(response, "is_async", False):
            return response

        sync_iter = response.streaming_content

        async def async_iter():
            for part in await sync_to_async(list)(sync_iter):
                yield part

        response.streaming_content = async_iter()
        return response
