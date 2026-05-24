# AsyncStreamingMiddleware

`AsyncStreamingMiddleware` is a small Django middleware included in **reflex-django**. It makes **streaming HTTP responses** work cleanly when you run Django under **ASGI** (which is what `python manage.py run_reflex` uses).

---

## Why you need it

`run_reflex` runs **one ASGI process** for both Django and Reflex. Traffic to Django routes — especially **`/admin/`** and **static files** — often returns a `StreamingHttpResponse` (body sent in chunks).

Django’s ASGI handler expects streaming content to be **async**. Many views still provide a **sync** generator. Without adaptation, Django warns and does extra work adapting the iterator at send time.

`AsyncStreamingMiddleware` converts those sync streaming iterators to async **in `process_response`**, before the response leaves Django.

---

## What it does (step by step)

For each HTTP response:

1. **Skip** if the request is not ASGI (no `request.scope`) — WSGI is unchanged.
2. **Skip** if the response is not streaming.
3. **Skip** if the response is already async (`is_async=True`).
4. **Otherwise** wrap `streaming_content` in an async generator that reads the sync iterator via `sync_to_async`.

```text
  Django view returns StreamingHttpResponse (sync generator)
           │
           ▼
  AsyncStreamingMiddleware.process_response
           │
           ▼
  Response with async streaming_content
           │
           ▼
  ASGI handler sends body without sync-iterator warnings
```

Implementation: `reflex_django.streaming_middleware.AsyncStreamingMiddleware`.

---

## What it does not do

| Not covered | Handled by |
|:---|:---|
| Reflex WebSockets (`/_event`) | Reflex / event bridge |
| Reflex SPA pages (`@template`) | Reflex client router |
| Non-streaming JSON/HTML responses | Normal Django responses (unchanged) |
| CSRF, auth, sessions | Standard Django `MIDDLEWARE` |

---

## How to enable it

Add the class **at the end** of `MIDDLEWARE` in `settings.py`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Keep this last — adapts streaming responses for ASGI
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
]
```

`reflex_django.default_settings` and the [Quickstart](quickstart.md) include this line by default.

---

## When you notice it matters

- Opening **Django admin** at `/admin/` under `run_reflex`
- Serving **large or chunked downloads** from Django views
- **Static/media** responses that use streaming

If you remove the middleware, the app may still work, but you can see ASGI warnings in the console during admin or static requests.

---

## WSGI vs ASGI

| Server style | Middleware effect |
|:---|:---|
| **ASGI** (`run_reflex`, Uvicorn, Granian) | Converts sync streaming → async |
| **WSGI** (`runserver` in pure WSGI mode) | No-op (request has no `scope`) |

reflex-django targets ASGI for full-stack dev so WebSockets and the unified dispatcher work.

---

## Related reading

- [Quickstart](quickstart.md) — full minimal `settings.py`
- [Configuration](configuration.md) — other `REFLEX_DJANGO_*` settings
- [CLI](cli.md) — `run_reflex` and ASGI entry points

---

**Navigation:** [← Configuration](configuration.md) | [Quickstart →](quickstart.md)
