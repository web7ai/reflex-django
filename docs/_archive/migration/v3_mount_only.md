# Migrating to mount-only architecture (v3)

reflex-django v3 removes composed ASGI routing modes (`django_outer`, `reflex_outer`) and the `reflex_django.asgi.entry:application` entry point. Production Django uses plain `get_asgi_application()` with `reflex_mount()` in URLconf. Dev uses `manage.py run_reflex`, which runs Vite plus the native Reflex backend with Django mounted in-process.

## Summary

| Before (v2) | After (v3) |
|:---|:---|
| `REFLEX_DJANGO_URL_ROUTING = "django_outer"` | Removed  -  mount-only |
| `REFLEX_DJANGO_URL_ROUTING = "reflex_outer"` | Removed  -  optional split-process dev via `RXDJANGO_PROXY_SERVER` |
| `from reflex_django.asgi.entry import application` | `get_asgi_application()` in `config/asgi.py` |
| `python manage.py run_reflex` starts composed outer ASGI | `run_reflex` → `reflex run` (Vite + Reflex backend; Django in-process) |
| `REFLEX_DJANGO_HTTP_UPSTREAM` | Deprecated alias → `RXDJANGO_PROXY_SERVER` |
| `make_dispatcher` removed | Restored for in-process Django on the Reflex backend during dev |

## Update `config/asgi.py`

```python
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

application = get_asgi_application()
```

## Local development (default  -  one terminal)

```bash
python manage.py run_reflex
```

Browse `http://localhost:3000/` for the SPA. Vite proxies admin, API, `/_event`, and related paths to the **Reflex backend** (`:8000` by default). Django admin and API are served from Django ASGI mounted inside that backend process.

Admin is auto-wired when `django.contrib.admin` is installed and `/admin` is not already in `urlpatterns`. You can also add it explicitly:

```python
from reflex_django.django.urls import admin_urlpatterns

urlpatterns = [
    *admin_urlpatterns("/admin"),
    # ... your routes ...
]
```

## Optional split-process dev

Use this when you want Django on `runserver` and Reflex separately:

**Terminal 1  -  Django:**

```bash
python manage.py runserver
```

**Terminal 2  -  Reflex/Vite:**

```python
# settings.py
RXDJANGO_PROXY_SERVER = "http://127.0.0.1:8000"
```

```bash
python manage.py run_reflex
```

Vite proxies Django prefixes to `RXDJANGO_PROXY_SERVER` and Reflex paths to the Reflex backend.

## Production

1. Django serves admin, API, static, and the compiled SPA shell (`ReflexMountView`).
2. Run a Reflex backend process (or export-only static UI).
3. Put a reverse proxy in front: forward `/_event`, `/_upload`, etc. to Reflex; everything else to Django.

See [Deployment](../../operations/deployment.md) and [Routing](../../internals/routing.md).
