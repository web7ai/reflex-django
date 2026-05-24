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

**reflex-django** is a **Django-first** integration layer for [Reflex](https://reflex.dev). You configure Reflex in **`urls.py`** with `reflex_mount()`, define pages in **`{app}/views.py`**, and run **`python manage.py run_reflex`**.

- **Django** handles `/admin`, `/api`, ORM, migrations, sessions  
- **Reflex** handles the SPA, client routes, and WebSocket events  
- **`django_led_app`** replaces `{app}/{app}.py` — no extra Reflex package boilerplate  

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
    reflex_mount(app_name="myapp", rx_config={"frontend_port": 3000, "backend_port": 8000}),
]
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
| Brownfield | [Existing Django project](existing_django_project.md) |
| Folder layout | [Project structure](project_structure.md) |
| URLs & `django_led_app` | [Django-led URL routing](django_urls.md) |
| Pages in `views.py` | [Pages in views.py](pages_in_views.md) |
| Runtime | [Architecture](architecture.md) |
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
| Put pages in Django apps | [Pages in views.py](pages_in_views.md) |
| Understand `django_led_app` | [Django-led URL routing](django_urls.md) |
| Use `request.user` in events | [Authentication](authentication.md) |
| Run migrations | [CLI](cli.md) |
| Deploy one process | [Deployment](deployment.md) |

---

**Navigation:** [Introduction →](introduction.md)
