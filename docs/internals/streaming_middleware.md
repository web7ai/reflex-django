---
level: intermediate
tags: [middleware, asgi, django]
---

# AsyncStreamingMiddleware explained

**What you'll learn:** Why reflex-django adds a small middleware at the bottom of `MIDDLEWARE`, what it fixes under ASGI, and why it is skipped on WebSocket events.

**When you need this:**

- You see streaming warnings from uvicorn or granian when opening Django admin.
- You are reviewing `settings.py` and wonder why `AsyncStreamingMiddleware` must be last.

---

This is the small Django middleware you add at the bottom of `MIDDLEWARE`:

```python
--8<-- "snippets/minimal_settings.py"
```

Short answer: leave it on, place it last, and forget about it until a streaming warning appears.

---

## What problem it solves

When Django serves a `StreamingHttpResponse` (admin static streaming, large downloads, some third-party views), it gives you an **iterator** of byte chunks.

Under WSGI, the server walks that iterator synchronously. Under ASGI, the response is consumed with `async for`. If the iterator is sync, the ASGI server calls `__next__()` from the event loop and **blocks the loop** for every chunk. Django emits warnings. In some setups the response hangs.

`AsyncStreamingMiddleware` wraps sync streaming responses so they become async-iterable. Admin streams happily under ASGI. Warnings go away.

<div class="rd-instructor">

Think of it like adding a subtitle track to a video file the player already knows how to play. The content is the same; the wrapper format changed so the async player does not stall.

</div>

---

## What it actually does

Inside `process_response` (on the way out):

1. Is this an ASGI request? (Check `request.scope`. WSGI requests pass through unchanged.)
2. Is the response a streaming response?
3. Is the underlying iterator still sync?
4. If yes, wrap chunks with `sync_to_async` and mark the response async.

```python
# Simplified from reflex_django/bridge/streaming.py
def process_response(self, request, response):
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
```

About 40 lines total. No settings knobs.

---

## When you need it

You need it if any of these are true:

- You serve the Django admin.
- You have views that return `StreamingHttpResponse` directly.
- You use a library that streams responses (some static-file or sendfile helpers).

That covers most reflex-django projects. Every example `settings.py` in these docs includes it.

---

## When you do not need it

You can skip it only if:

- Every view returns plain `HttpResponse` or `JsonResponse`, **and**
- You never use the admin or streaming third-party views, **and**
- You run under WSGI only.

It is still safe to leave on. Non-streaming responses cost one `isinstance()` check.

---

## Where to place it in `MIDDLEWARE`

**Last.**

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",  # last
]
```

Middleware on the way **out** runs in reverse order from the list. The last entry is the first to see the response on the way back. Putting `AsyncStreamingMiddleware` last means it adapts the response **before** any other middleware tries to read or modify the body.

If you place it earlier, another middleware might consume the sync iterator first.

!!! warning "Keep it last"
    Moving this middleware up the list is the most common misconfiguration. Symptoms look like truncated downloads or admin pages that never finish loading.

---

## Why it is skipped on Reflex events

`DjangoEventBridge` skips `AsyncStreamingMiddleware` on WebSocket events (alongside `CsrfViewMiddleware`). Events never produce a `StreamingHttpResponse`. The synthetic middleware response is an in-memory empty 200. Skipping saves one no-op call per click.

Default skip list:

```python
RX_EVENT_MIDDLEWARE_SKIP = (
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
)
```

Override only if you have a unusual reason to run it on events.

See [The WebSocket event pipeline](event_pipeline.md) and [Custom middleware in events](../guides/middleware.md).

---

## Warning signs

### Streaming warning in the dev server

Without this middleware you might see:

```text
StreamingHttpResponse must consume its content asynchronously
or the content will be consumed synchronously, blocking the event loop.
```

Add `reflex_django.bridge.streaming.AsyncStreamingMiddleware` at the bottom of `MIDDLEWARE`. Restart the server.

### Admin hangs or truncated content

Some admin endpoints (large changelist exports, big media downloads) may hang under ASGI without the middleware. Adding it fixes the symptom.

---

## How it interacts with WhiteNoise / static-file middleware

`AsyncStreamingMiddleware` is **response-side**. Static-file middleware (WhiteNoise, etc.) often returns sync streaming responses. This middleware adapts them on the way out. They coexist fine.

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # if you use it
    "django.contrib.sessions.middleware.SessionMiddleware",
    # ...
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",  # last
]
```

WhiteNoise creates the streaming response. `AsyncStreamingMiddleware` adapts it before the ASGI handler sends bytes to the client.

---

## Source

The whole implementation lives in:

```text
src/reflex_django/bridge/streaming.py
```

- Old-style `MiddlewareMixin` (`sync_capable` and `async_capable`).
- `sync_to_async` per chunk for sync iterators.
- Early returns for WSGI, non-streaming, and already-async responses.

No environment variables. No extra settings beyond placement in `MIDDLEWARE`.

---

## What just happened?

You learned why `AsyncStreamingMiddleware` belongs at the end of `MIDDLEWARE`, how it adapts sync streams for ASGI, and why the event bridge skips it on `/_event`.

**Next up:** [CLI reference →](../operations/cli.md)
