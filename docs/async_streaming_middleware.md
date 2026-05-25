# AsyncStreamingMiddleware explained

This is the small Django middleware you added at the bottom of `MIDDLEWARE`:

```python
MIDDLEWARE = [
    ...,
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

This page explains what it does, why it's there, and when you'd actually need to think about it. Short answer: leave it on, place it last, and never think about it again.

---

## What problem it solves

When Django serves a `StreamingHttpResponse` — for example, the admin's static file streaming, large file downloads, or some third-party views — it gives you an *iterator* of byte chunks.

Under WSGI (the old sync server), Django expects this iterator to be a regular Python iterator. The WSGI server walks it synchronously and writes each chunk to the socket. Easy.

Under ASGI (the modern async server), the response is consumed by an `async for`. If the iterator is sync, the ASGI server has to call `__next__()` from the event loop — which blocks the loop for every chunk. Django emits warnings, and in some setups, the response just hangs.

`AsyncStreamingMiddleware` wraps sync streaming responses so they become async-iterable. The admin happily streams under ASGI; you don't see warnings; nothing hangs.

---

## What it actually does

Inside `process_response` (the part of a Django middleware that runs on the way out):

1. Look at the response. Is it a `StreamingHttpResponse`?
2. If yes, is the underlying iterator sync (a regular generator)?
3. If yes, wrap it in an async-iterable adapter that runs each chunk through `sync_to_async`.
4. Otherwise, do nothing.

That's it. About 30 lines of code.

```python
# Simplified
def process_response(self, request, response):
    if not isinstance(response, StreamingHttpResponse):
        return response
    if isinstance(response.streaming_content, AsyncIterable):
        return response
    response.streaming_content = sync_iter_to_async(response.streaming_content)
    return response
```

---

## When you need it

You need it if any of these are true:

- You serve the Django admin.
- You have views that return `StreamingHttpResponse` directly.
- You use any third-party library that streams responses (whitenoise, sendfile, etc.).

In other words: pretty much every project. That's why it's listed in every example `settings.py` in these docs.

---

## When you don't need it

You don't need it if:

- You only serve plain `HttpResponse` and `JsonResponse`.
- You're running under WSGI (then the middleware is a no-op anyway).
- You don't use the admin.

It's still safe to leave on — the middleware does nothing on non-streaming responses or under WSGI. The cost is one `isinstance()` check per response.

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
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",   # ← last
]
```

Why last? Middleware on the way out runs in *reverse* order from how it's listed. The last entry is the first to see the response on the way back. Putting `AsyncStreamingMiddleware` last means it sees and adapts the response **before** any other middleware tries to read or modify it. By the time anything else runs, the iterator is already async.

If you place it earlier, other middleware might already have consumed (or tried to consume) the sync iterator.

---

## Why it's skipped on Reflex events

The bridge skips `AsyncStreamingMiddleware` on WebSocket events (alongside `CsrfViewMiddleware`). WebSocket events never produce a `StreamingHttpResponse` — the response is an in-memory diff, not a streaming download. Running the middleware would be a no-op anyway, and skipping it is one less function call per event.

The skip list:

```python
REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP = (
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
)
```

Override if you need to.

---

## Warning signs

You'll hear about this middleware in one of two ways:

### Warning in the dev server

Without this middleware, you might see warnings in `manage.py run_reflex` like:

```text
StreamingHttpResponse must consume its content asynchronously
or the content will be consumed synchronously, blocking the event loop.
```

Add `reflex_django.streaming_middleware.AsyncStreamingMiddleware` at the bottom of `MIDDLEWARE`. Warning goes away.

### Admin hangs or returns truncated content

Without the middleware, some admin endpoints (large change-list pages, big media downloads) might hang under ASGI. Adding the middleware fixes it.

---

## How it interacts with whitenoise / static-file serving

`AsyncStreamingMiddleware` is *response-side* — it adapts responses on their way out. Static-file serving middleware (whitenoise, etc.) usually returns sync streaming responses, which this middleware then adapts. They coexist fine.

The order:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # if you use it
    "django.contrib.sessions.middleware.SessionMiddleware",
    ...,
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",   # last
]
```

WhiteNoise creates the streaming response. `AsyncStreamingMiddleware` adapts it on the way back. Both happy.

---

## Source

The whole file is small. If you want to read it:

```
src/reflex_django/streaming_middleware.py
```

It's roughly:

- An old-style `def process_response` middleware (so it has full control over the response on the way out).
- A `sync_iter_to_async` helper that wraps a sync iterator with `sync_to_async` per chunk.
- Some `isinstance` checks to skip non-streaming responses and already-async iterators.

No special configuration, no environment variables, no settings — it just works.

---

## Summary

- Add `"reflex_django.streaming_middleware.AsyncStreamingMiddleware"` at the bottom of `MIDDLEWARE`.
- It adapts sync streaming responses (admin, downloads) for ASGI.
- It's a no-op on non-streaming responses and under WSGI.
- It's skipped on Reflex WebSocket events (where streaming responses don't exist).
- That's the entire story.

---

**Next:** [CLI reference →](cli.md)
