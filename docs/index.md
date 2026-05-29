<style>
  .md-content .md-typeset > h1:first-of-type { display: none; }
</style>

<div class="rd-hero" markdown>
  <h1 class="rd-hero__brand">reflex-django</h1>
  <p class="rd-hero__tagline">Keep Django. Get a reactive UI in Python. Same process, same port, same cookies.</p>
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

You keep writing Django. You write your UI in Python using [Reflex](https://reflex.dev). They run as **one program, on one port**, and your Django session is the same session your buttons see. No CORS, no token gymnastics, no second dev server in another terminal.

---

## What you'll actually write

Three files. That's the whole shape of a `reflex-django` project:

```python
# config/settings.py — register reflex_django like any other app
INSTALLED_APPS = [..., "reflex_django", "shop"]
```

```python
# config/urls.py — one line wires Reflex in
from reflex_django.urls import reflex_mount

urlpatterns = [path("admin/", admin.site.urls)]
urlpatterns += [reflex_mount(app_name="shop")]
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

That's it. Open `http://localhost:8000/`. Your admin is at `/admin/`. Your reactive UI is at `/`. They share cookies, sessions, and the same Python process.

---

## Pick a path

<div class="path-grid">
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
    <p>Add a reflex-django page to a real, brownfield Django project without touching your models.</p>
  </a>
</div>

---

## A suggested reading order

If you're new and you'd like a guided tour, this is the path most people find easiest:

1. **[Why reflex-django exists](why_reflex_django.md)** — the one-page story
2. **[How Django works in 5 minutes](how_django_works.md)** — skip this if Django is your day job
3. **[How Reflex works in 5 minutes](how_reflex_works.md)** — skip this if Reflex is your day job
4. **[How the two fit together](how_they_fit.md)** — the bridge, in plain English
5. **[Install](installation.md)** and **[Your first app](quickstart.md)**
6. **[The Essentials](configuration.md)** — pages, state, the database, auth

Then drop into the build guides when you actually need them — CRUD pages, forms, i18n, deployment.

---

## Looking for something specific?

| I want to… | Read |
|:---|:---|
| Configure ports, app name, prefixes | [Configuration](configuration.md) |
| Put pages next to my Django models | [Pages live in views.py](pages_in_views.md) |
| Read `request.user` inside a button handler | [AppState: your bridge to Django](state_management.md) |
| Build a list/edit/delete page fast | [CRUD with ModelState](reactive_model_state.md) |
| Understand the WebSocket plumbing | [The WebSocket event pipeline](websocket_event_pipeline.md) |
| Deploy to one container | [Deployment](deployment.md) |
| Look up a `REFLEX_DJANGO_*` setting | [Settings reference](settings_reference.md) |
| See every public symbol | [Public API at a glance](public_api.md) |

---

**Next:** [Why reflex-django exists →](why_reflex_django.md)
