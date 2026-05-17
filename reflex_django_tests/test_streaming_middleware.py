"""Tests for reflex_django.streaming_middleware.AsyncStreamingMiddleware."""

from __future__ import annotations

import warnings
from unittest import mock

from reflex_django.conf import configure_django

configure_django()

from django.core.handlers.asgi import ASGIRequest  # noqa: E402
from django.http import StreamingHttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from reflex_django.streaming_middleware import AsyncStreamingMiddleware  # noqa: E402


def _sync_streaming_response() -> StreamingHttpResponse:
    def generate():
        yield b"chunk-a"
        yield b"chunk-b"

    return StreamingHttpResponse(generate(), content_type="application/octet-stream")


def _asgi_request(path: str = "/media/test.jpg") -> ASGIRequest:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return ASGIRequest(scope, receive)


def test_sync_request_leaves_streaming_iterator_sync() -> None:
    captured: list[StreamingHttpResponse] = []

    def get_response(request):
        del request
        response = _sync_streaming_response()
        captured.append(response)
        return response

    middleware = AsyncStreamingMiddleware(get_response)
    request = RequestFactory().get("/media/test.jpg")
    response = middleware(request)

    assert captured
    assert response.streaming is True
    assert response.is_async is False
    assert list(response.streaming_content) == [b"chunk-a", b"chunk-b"]


async def test_async_streaming_middleware_marks_response_async() -> None:
    captured: list[StreamingHttpResponse] = []

    async def get_response(request):
        del request
        response = _sync_streaming_response()
        captured.append(response)
        return response

    middleware = AsyncStreamingMiddleware(get_response)
    request = _asgi_request()
    response = await middleware(request)

    assert captured
    assert response.streaming is True
    assert response.is_async is True

    chunks: list[bytes] = []
    async for part in response:
        chunks.append(part)
    assert chunks == [b"chunk-a", b"chunk-b"]


async def test_async_streaming_middleware_no_warning_on_aiter() -> None:
    async def get_response(request):
        del request
        return _sync_streaming_response()

    middleware = AsyncStreamingMiddleware(get_response)
    request = _asgi_request()
    response = await middleware(request)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        chunks = [part async for part in response]

    sync_stream_warnings = [
        w
        for w in caught
        if "synchronous iterators" in str(w.message).lower()
        or "asynchronous iterator" in str(w.message).lower()
    ]
    assert chunks == [b"chunk-a", b"chunk-b"]
    assert not sync_stream_warnings


def test_sync_middleware_call_returns_http_response_not_coroutine() -> None:
    """Regression: async-only __call__ broke sync middleware chains (e.g. media)."""

    def get_response(request):
        del request
        return mock.Mock(status_code=200, streaming=False)

    middleware = AsyncStreamingMiddleware(get_response)
    request = RequestFactory().get("/")
    response = middleware(request)

    assert not hasattr(response, "__await__")
