# Media files

User-uploaded files (profile photos, attachments, product images) are **Django media files**. reflex-django routes `/media/...` to Django in development, but **does not serve the files for you** — you must configure `MEDIA_URL`, `MEDIA_ROOT`, and mount the URL pattern yourself.

---

## Required Django settings

```python
# settings.py
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

Use a relative `MEDIA_URL` (no `http://` scheme) so the SPA can load images with `/media/avatars/alice.jpg` on any origin.

---

## Serve media in development

Add Django's static helper to `urls.py` when `DEBUG=True`:

```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

Without this mount, uploads may save to disk but **`/media/...` returns 404** in the browser.

---

## What reflex-django already does

In DEBUG mode, `prefix_discovery` adds your `MEDIA_URL` prefix (default `/media`) to the django prefix list. The SPA catch-all does not swallow `/media/...` requests, and two-port dev can reach media on `:8000` via `env.json`.

**Routing is not serving.** Prefix discovery only ensures requests reach Django; you still need `static(MEDIA_URL, ...)` in dev or nginx/S3 in production.

---

## Two-port dev

Browse the SPA on **`http://localhost:3000/`**. Relative URLs like `/media/photo.jpg` are routed to **`http://localhost:8000`** by the compiled SPA config.

If images 404, confirm `urlpatterns += static(...)`, the file exists under `MEDIA_ROOT`, and `MEDIA_URL` is relative. See [Local development](local_development.md).

---

## Production

```nginx
location /media/ {
    alias /app/media/;
    expires 7d;
}
```

For object storage, set `MEDIA_URL` to your CDN URL and use `django-storages`.

In **`reflex_outer`**, the Django HTTP worker needs the same media configuration. See [Deployment](deployment.md).

---

## Displaying uploads in Reflex

Use the model field's `.url` property after save (e.g. `/media/avatars/user_1.jpg`). For browser uploads, see [File uploads](file_uploads.md).

---

## Related

- [Configuration](configuration.md)
- [FAQ](faq.md)
- [Deployment](deployment.md)