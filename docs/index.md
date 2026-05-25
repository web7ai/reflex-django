<style>
.md-content .md-typeset h1 { display: none; }
</style>

<p align="center">
  <a href="https://github.com/mohannadirshedat/reflex-django">
    <img src="assets/logo.png" alt="reflex-django logo" width="220" style="border-radius: 16px; margin-bottom: 8px;">
  </a>
</p>

<p align="center">
  <h1 align="center" style="border-bottom: none; font-size: 3.2rem; font-weight: 850; margin-bottom: 0px; background: linear-gradient(135deg, #3f51b5, #00b0ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px;">reflex-django</h1>
</p>

<p align="center">
  <em>Django ORM, admin, and sessions — plus Reflex reactive UI — in one Python process.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/v/reflex-django?color=%2334D058&label=pypi%20package" alt="PyPI"></a>
  <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/pyversions/reflex-django.svg" alt="Python"></a>
  <a href="https://github.com/mohannadirshedat/reflex-django/blob/main/LICENSE"><img src="https://img.shields.io/github/license/mohannadirshedat/reflex-django.svg?color=blue" alt="License"></a>
</p>

---

## What is reflex-django?

**reflex-django** is a **Django-first** integration layer for [Reflex](https://reflex.dev). Django and Reflex run as **one ASGI application on one port**. You configure Reflex in **`urls.py`** with `reflex_mount()`, define pages in **`{app}/views.py`**, and run **`python manage.py run_reflex`**.

- **Django** is the outer ASGI app — it handles `/admin`, `/api`, ORM, migrations, sessions, and serves the compiled SPA from disk.
- **Reflex** is mounted under Django — Socket.IO event channel (`/_event`), upload endpoint, health probes, and the SPA shell.
- **Full middleware chain** runs on every Reflex event — `request.user`, `session`, `messages`, `csrf_token`, and your custom middleware are bound to every `@rx.event` handler.
- **`django_led_app`** replaces `{app}/{app}.py` — no extra Reflex package boilerplate.
- **One Python process, one port, one origin.** No CORS, no token bridge, no second dev server.

---

## Choose your path

<div class="path-grid">
  <a href="quickstart/" class="path-card">
    <h3>🚀 New project</h3>
    <p>Django project + shop/views.py pages + run_reflex in ~15 minutes.</p>
  </a>
  <a href="existing_django_project/" class="path-card">
    <h3>🔌 Existing Django app</h3>
    <p>Add reflex_mount() and views.py pages without touching your models.</p>
  </a>
</div>

---

## Install

```bash
uv add django reflex reflex-django
```

```python
# settings.py — INSTALLED_APPS includes "reflex_django"

# urls.py
urlpatterns += [
    reflex_mount(app_name="myapp", rx_config={"backend_port": 8000}),
]

# config/asgi.py — single ASGI entry point
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from reflex_django.asgi_entry import application  # noqa: E402,F401
```

```bash
python manage.py run_reflex
```

---

## Core guides

| Topic | Guide |
|:---|:---|
| Concepts | [Introduction](introduction.md) |
| Install | [Installation](installation.md) |
| **`reflex_mount()` & settings** | [Configuration](configuration.md) |
| Tutorial | [Quickstart](quickstart.md) |
| Runtime architecture | [Architecture](architecture.md) |
| Single-port reference | [Single-port architecture](single_port_django_outer.md) |
| Routing | [Routing & dispatching](routing.md) |
| `/_event` & WebSockets | [WebSocket event pipeline](websocket_event_pipeline.md) |
| Pages & `@template` | [Pages in views.py](pages_in_views.md) |
| ASGI streaming | [AsyncStreamingMiddleware](async_streaming_middleware.md) |
| Brownfield | [Existing Django project](existing_django_project.md) |
| Folder layout | [Project structure](project_structure.md) |
| URLs & `django_led_app` | [Django-led URL routing](django_urls.md) |
| CLI | [CLI](cli.md) |

---

## Learning path

1. **Start here** — [Introduction](introduction.md) → [Installation](installation.md) → [Quickstart](quickstart.md)
2. **Routing & pages** — [Django-led URL routing](django_urls.md) → [Pages in views.py](pages_in_views.md)
3. **State & auth** — [State management](state_management.md) → [Authentication](authentication.md)
4. **Data** — [Database integration](database_integration.md) → [Reactive ModelState](reactive_model_state.md)
5. **Ship** — [Deployment](deployment.md) → [FAQ](faq.md)

---

## Task index

| I want to… | Read |
|:---|:---|
| Set ports and app name | [Configuration](configuration.md) |
| Understand how Django + Reflex compose | [Architecture](architecture.md) |
| See the dispatcher routing rules | [Routing & dispatching](routing.md) |
| Trace a `/_event` WebSocket end-to-end | [WebSocket event pipeline](websocket_event_pipeline.md) |
| Put pages in Django apps | [Pages in views.py](pages_in_views.md) |
| Fix admin streaming warnings | [AsyncStreamingMiddleware](async_streaming_middleware.md) |
| Use `request.user` / messages / CSRF in events | [Authentication](authentication.md) |
| Build the SPA bundle | [CLI](cli.md) |
| Deploy one process | [Deployment](deployment.md) |

---

**Navigation:** [Introduction →](introduction.md)
