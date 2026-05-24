# Pages in `views.py`

Django-first projects can define Reflex pages in any Django app's `views.py`.
reflex-django **auto-imports** `{app}.views` for every app in `INSTALLED_APPS`
(except `django.*` and `reflex_django`) when you use `@template` or `@page` — no
`urls.py` import and no page list in `rxconfig.py`.

> **Note:** These are **Reflex page render functions**, not Django `HttpResponse` views. Django does not need a `path()` per page; the client router and ASGI dispatcher handle `/`, `/about`, etc.

## Minimal example

```python
# myapp/views.py
import reflex as rx
from reflex_django import template

@template(route="/", title="Home")
def index() -> rx.Component:
    return rx.text("Hello")

@template(route="/about", title="About")
def about() -> rx.Component:
    return rx.text("About this app")
```

```python
# myproject/urls.py
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]
urlpatterns += [reflex_mount(django_prefix=("/admin",))]
```

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "myapp",
    "blog",  # blog/views.py pages are discovered automatically
]
# Reflex app_name is set on reflex_mount() in urls.py (defaults to project folder name)
```

```python
# urls.py
urlpatterns += [reflex_mount(app_name="myapp")]
```

### Multiple apps

Put `@template` pages in each app's `views.py` (for example `myapp/views.py` and
`blog/views.py`). They are imported at startup via `INSTALLED_APPS`.

Optional overrides:

| Setting | Purpose |
|:---|:---|
| `REFLEX_DJANGO_PAGE_PACKAGES` | Explicit module list (disables auto-discovery) |
| `REFLEX_DJANGO_PAGE_APPS` | Allowlist of app labels to scan |
| `REFLEX_DJANGO_AUTO_DISCOVER_PAGES` | Set `False` to only load `{app_name}.views` from `reflex_mount()` |
| `REFLEX_DJANGO_PAGE_MODULE` | Module name suffix (default `views`) |

## Built-in `@template`

`reflex_django.template` wraps your content in a centered container and registers the route via `@rx.page`. For pages without a layout, use `from reflex_django.decorators import page` or `from reflex_django import page`.

```python
from reflex_django import page

@page(route="/bare")
def bare() -> rx.Component:
    return rx.text("No layout wrapper")
```

## Run

```bash
python manage.py run_reflex
```

Open `http://localhost:3000/` (frontend) or `http://localhost:8000/` (backend). Django admin stays at `/admin/`.

See also [Django-led URL routing](django_urls.md).
