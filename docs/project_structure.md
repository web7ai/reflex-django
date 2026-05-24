# Project structure

Recommended layout for a **Django-first** reflex-django application: one repo, one `manage.py`, pages beside Django apps, configuration in `urls.py`.

---

## Standard layout

```text
myproject/                         # Git root (parent of manage.py)
├── manage.py
├── pyproject.toml
├── rxconfig.py                    # optional auto stub (not source of truth)
├── db.sqlite3
│
├── config/                        # Django project package
│   ├── settings.py                # INSTALLED_APPS, MIDDLEWARE, REFLEX_DJANGO_*
│   ├── urls.py                    # reflex_mount() — last urlpatterns entry
│   ├── asgi.py
│   └── wsgi.py
│
├── shop/                          # Django app (domain + Reflex pages)
│   ├── migrations/
│   ├── models.py
│   ├── views.py                   # @template pages (/, /about, …)
│   ├── serializers.py             # optional ReflexDjangoModelSerializer
│   └── admin.py
│
├── blog/                          # another app — blog/views.py auto-imported
│   └── views.py
│
└── .web/                          # Reflex frontend (generated; gitignore)
```

---

## What goes where

| Location | Purpose |
|:---|:---|
| **`config/settings.py`** | Django apps, database, `REFLEX_DJANGO_*` overrides |
| **`config/urls.py`** | Django routes + **`reflex_mount(...)`** |
| **`{app}/models.py`** | Django ORM — unchanged |
| **`{app}/views.py`** | Reflex page functions (`@template`, `@page`) |
| **`{app}/serializers.py`** | Model → JSON helpers for state |
| **No `{app}/{app}.py`** | App instance loaded via `reflex_django.django_led_app` |

---

## Configuration flow

```text
  urls.py
    └── reflex_mount(app_name="shop", rx_config={...})
            └── register_mount_rx_config()
                    └── merged at runtime by get_config()

  shop/views.py
    └── @template(route="/")  →  registers page on import

  django_led_app.app
    └── ensure_django_led_app_ready()
            ├── import shop.views, blog.views, ...
            ├── rx.App()
            └── apply decorated pages
```

---

## `app_name` naming

| Source | Example |
|:---|:---|
| `reflex_mount(app_name="shop")` | Explicit |
| `rx_config={"app_name": "shop"}` | Alternative |
| Default | Folder containing `manage.py` (`my-project` → `my_project`) |

The label must match a Django app in `INSTALLED_APPS` that contains your pages (usually in `views.py`).

---

## Optional: separate UI package

Some teams prefer a dedicated package:

```text
frontend/
  views.py       # or pages/home.py
```

Set `REFLEX_DJANGO_PAGE_PACKAGES = ["frontend.views"]` or import submodules from `shop/views.py`. Auto-discovery defaults to `{app_label}.views` per installed app.

---

## Generated / ignored paths

| Path | Notes |
|:---|:---|
| **`.web/`** | Reflex/Vite frontend; recreated by compile/run |
| **`.reflex/`** | Reflex user dir (may be global on your machine) |
| **`rxconfig.py` stub** | Layout check for Reflex CLI; syncs `app_name` + `django_led_app` |

---

## Static files

| Environment | Mechanism |
|:---|:---|
| **Development** | `ASGIStaticFilesHandler` when `staticfiles` in `INSTALLED_APPS`; Vite dev server on `frontend_port` |
| **Production** | `collectstatic` + same ASGI dispatcher; see [Deployment](deployment.md) |

---

## Next steps

- [Django-led URL routing](django_urls.md) — `reflex_mount` details
- [Pages in views.py](pages_in_views.md) — decorators and discovery
- [Architecture](architecture.md) — runtime topology

---

**Navigation:** [← Existing Django project](existing_django_project.md) | [Architecture →](architecture.md)
