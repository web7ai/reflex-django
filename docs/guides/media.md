---
level: beginner
tags: [media, uploads]
---

# Media files

**What you'll learn:** How to configure Django user uploads so `/media/...` URLs work in dev and production alongside the Reflex SPA.

**When you need this:**

- Profile photos, attachments, or product images 404 under `/media/...`.
- You are not sure what reflex-django handles versus what you must configure in Django.

---

User-uploaded files are **Django media files**. reflex-django routes `/media/...` to Django in development, but **does not serve the files for you**. You configure `MEDIA_URL`, `MEDIA_ROOT`, and mount the URL pattern yourself.

---

## Required Django settings

```python
# settings.py
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

Use a relative `MEDIA_URL` (no `http://` scheme) so the SPA can load `/media/avatars/alice.jpg` on any origin.

---

## Serve media in development

Add Django's static helper to `urls.py` when `DEBUG=True`:

```python
--8<-- "snippets/media_urls.py"
```

Without this mount, uploads may save to disk but **`/media/...` returns 404** in the browser.

!!! warning "Routing is not serving"
    In DEBUG, reflex-django adds your `MEDIA_URL` prefix to the django prefix list so the SPA catch-all does not swallow `/media/...`. That only ensures requests reach Django. You still need `static(MEDIA_URL, ...)` in dev or nginx/S3 in production.

---

## What reflex-django already does

In DEBUG, prefix discovery includes `MEDIA_URL` (default `/media`). Two-port dev can reach media on `:8000` via the compiled SPA `env.json`.

reflex-django does **not** create `MEDIA_ROOT`, validate upload sizes, or serve files. That stays standard Django (or django-storages).

---

## Two-port dev

Browse the SPA on **`http://localhost:3000/`**. Relative URLs like `/media/photo.jpg` proxy to **`http://localhost:8000`**.

If images 404, confirm:

1. `urlpatterns += static(...)` is present when `DEBUG=True`.
2. The file exists under `MEDIA_ROOT`.
3. `MEDIA_URL` is relative (starts with `/`).

See [Local development](../getting-started/local_development.md).

---

## Production

Serve files from disk or object storage:

```nginx
location /media/ {
    alias /app/media/;
    expires 7d;
}
```

For S3 or similar, set `MEDIA_URL` to your CDN URL and use `django-storages`.

When using optional split-process dev (`RXDJANGO_PROXY_SERVER`), configure media on the Django `runserver` process as well. See [Deployment](../operations/deployment.md).

---

## Displaying uploads in Reflex

Use the model field's `.url` property after save (for example `/media/avatars/user_1.jpg`). For browser uploads from the SPA, see [File uploads](uploads.md).

```python
@rx.event
async def on_load(self):
    if self.request.user.is_authenticated:
        profile = await Profile.objects.aget(user=self.request.user)
        self.avatar_url = profile.avatar.url if profile.avatar else ""
```

Keep URLs as strings in state fields, not `FileField` instances.

---

## What just happened?

You configured Django media settings, mounted the dev URL pattern, and learned that reflex-django only reserves the `/media` prefix in DEBUG while Django (or your reverse proxy) actually serves the files.

---

**Next up:** [CRUD manual](crud.md#manual)