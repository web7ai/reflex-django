<style>
  .md-content .md-typeset > h1:first-of-type { display: none; }
</style>

<div class="rd-hero" markdown>
  <h1 class="rd-hero__brand">reflex-django</h1>
  <p class="rd-hero__tagline">Keep Django. Get a reactive UI in Python. One process, shared cookies, native Reflex dev.</p>
  <p class="rd-hero__badges">
    <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/v/reflex-django?color=%23e91e63&label=pypi" alt="PyPI"></a>
    <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/pyversions/reflex-django.svg?color=%23ad1457" alt="Python"></a>
    <a href="https://github.com/web7ai/reflex-django/blob/main/LICENSE"><img src="https://img.shields.io/github/license/web7ai/reflex-django.svg?color=%23ec407a" alt="License"></a>
  </p>
</div>

---

## Hi, welcome.

You're probably here because you love Django — the ORM, the admin, the migrations, the way it just works — but you also want a modern, reactive frontend without writing React, Vue, or shipping a separate Node app.

That's exactly what **reflex-django** is for.

You keep writing Django. You write your UI in Python using [Reflex](https://reflex.dev). They run as **one program** — one port in production; in dev, `run_reflex` starts Vite (`:3000`) and the backend (`:8000`) together. Your Django session is the same session your buttons see. No CORS, no token gymnastics.

---

## What you'll actually write

Three places. That's the whole shape of a `reflex-django` project. See [The three knobs (start here)](mental_model.md) for the full map.

```python
# config/settings.py — Reflex config + Django apps
INSTALLED_APPS = [..., "reflex_django", "shop"]

REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "shop",
    "frontend_port": 3000,
    "backend_port": 8000,
}
```

```python
# config/urls.py — Django routes + import pages (catch-all is automatic)
import shop.views  # noqa: F401

urlpatterns = [path("admin/", admin.site.urls)]
```

```python
# shop/views.py — your pages live here, next to your models
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState

class HomeState(AppState):
    @rx.event
    async def on_load(self):
        if self.request.user.is_authenticated:
            self.greeting = f"Hi, {self.request.user.get_username()}!"

@page(route="/", title="Home")
def index() -> rx.Component:
    return rx.heading(HomeState.greeting)
```

Then:

```bash
python manage.py run_reflex
```

One command starts **two dev servers**:

- **Vite on `:3000`** — open this for your Reflex UI and hot reload (`http://localhost:3000/`)
- **Django + Reflex backend on `:8000`** — admin, API, and the `/_event` WebSocket

The SPA's `env.json` points `/admin`, `/api`, and `/_event` at `:8000`, so cookies and session still line up on `localhost`. Edit a page in `views.py`, save, and the browser updates in place. Most other Python changes restart the backend automatically.

Prefer one URL in the address bar? Use `python manage.py run_reflex --env dev` and browse `:8000` instead. See [Local development](local_development.md).

> In production there's no Vite: you build the SPA and serve everything from your ASGI server on a single port. See [Deployment](deployment.md).

---

## Pick a path

<div class="path-grid">
  <a href="integration_guides/" class="path-card">
    <h3>Brownfield integration</h3>
    <p>Already have Django or Reflex? Pick the guide that matches your codebase.</p>
  </a>
  <a href="why_reflex_django/" class="path-card">
    <h3>I want to understand first</h3>
    <p>Read why reflex-django exists, how Django and Reflex actually work, and where they meet. ~10 minutes, no code.</p>
  </a>
  <a href="quickstart/" class="path-card">
    <h3>Just show me the code</h3>
    <p>Build a small todo app from scratch in about 15 minutes. You'll touch pages, state, auth, and the database.</p>
  </a>
  <a href="existing_django_project/" class="path-card">
    <h3>I have a Django app already</h3>
    <p>Add Reflex pages to a brownfield Django project — keep your models, admin, and API.</p>
  </a>
  <a href="existing_reflex_project/" class="path-card">
    <h3>I have a Reflex app already</h3>
    <p>Wrap your Reflex project in Django — ORM, admin, and sessions without rewriting your UI.</p>
  </a>
</div>

---

## A suggested reading order

If you're new and you'd like a guided tour, this is the path most people find easiest:

1. **[The three knobs (start here)](mental_model.md)** — settings, app, URLs; page registration vs catch-all
2. **[Why reflex-django exists](why_reflex_django.md)** — the one-page story
3. **[How Django works in 5 minutes](how_django_works.md)** — skip this if Django is your day job
4. **[How Reflex works in 5 minutes](how_reflex_works.md)** — skip this if Reflex is your day job
5. **[How the two fit together](how_they_fit.md)** — the bridge, in plain English
6. **[Install](installation.md)** and **[Your first app](quickstart.md)**
7. **[Configuration](configuration.md)** — pages, state, the database, auth

Then drop into the build guides when you actually need them — CRUD pages, forms, i18n, deployment.

---

## Looking for something specific?

| I want to… | Read |
|:---|:---|
| Add Reflex to my Django project | [Existing Django project](existing_django_project.md) |
| Add Django to my Reflex project | [Existing Reflex project](existing_reflex_project.md) |
| Configure ports, app name, prefixes | [Configuration](configuration.md) |
| Dev on `:8000`, ports, admin CSRF, `useContext` errors | [Local development](local_development.md) |
| Put pages next to my Django models | [Pages live in views.py](pages_in_views.md) |
| Read `request.user` inside a button handler | [AppState: your bridge to Django](state_management.md) |
| Build a list/edit/delete page fast | [CRUD with ModelState](reactive_model_state.md) |
| Understand the WebSocket plumbing | [The WebSocket event pipeline](websocket_event_pipeline.md) |
| Deploy to one container | [Deployment](deployment.md) |
| Look up a `REFLEX_DJANGO_*` setting | [Settings reference](settings_reference.md) |
| See every public symbol | [Public API at a glance](public_api.md) |

---

**Next:** [Why reflex-django exists →](why_reflex_django.md)
