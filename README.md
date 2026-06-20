# reflex-django

**Keep Django. Get a reactive UI in Python. One command, shared cookies, native Reflex dev.**

[![PyPI](https://img.shields.io/pypi/v/reflex-django?color=%23e91e63&label=pypi)](https://pypi.org/project/reflex-django)
[![Python](https://img.shields.io/pypi/pyversions/reflex-django.svg?color=%23ad1457)](https://pypi.org/project/reflex-django)
[![Docs](https://img.shields.io/badge/docs-online-%23ec407a)](https://web7ai.github.io/reflex-django/)
[![License](https://img.shields.io/github/license/web7ai/reflex-django.svg?color=%23f06292)](https://github.com/web7ai/reflex-django/blob/main/LICENSE)

[Documentation](https://web7ai.github.io/reflex-django/) · [LLM guide](https://github.com/web7ai/reflex-django/blob/main/llm.txt) · [GitHub](https://github.com/web7ai/reflex-django) · [PyPI](https://pypi.org/project/reflex-django/)

---

## What is reflex-django?

**reflex-django** is a Reflex plugin that runs your Django project and Reflex UI together. You keep Django for models, admin, auth, and APIs. You build the frontend in Python with Reflex components and state.

One dev command (`reflex run`) starts both sides. Sessions and cookies are shared, so a user logged in through Django is logged in on Reflex pages. Event handlers on Django-aware state read `self.request.user` like a Django view when bridge is enabled and the resolved tier binds request context.

The plugin wires four pieces automatically (embed, mount, proxy, bridge). Set `profile: "integrated"` in `rxconfig.py` and you get port 3000 dev, SPA routing, and Django middleware on bridge-bound Reflex events.

## Install

```bash
uv add reflex-django
```

Or with pip (you also need Django and Reflex):

```bash
pip install reflex-django django reflex
```

New project with uv:

```bash
uv add django reflex reflex-django
```

## Quick start

`rxconfig.py`:

```python
import reflex as rx
from reflex_django.plugins import ReflexDjangoPlugin

config = rx.Config(
    app_name="shop",
    plugins=[
        ReflexDjangoPlugin(config={
            "settings_module": "config.settings",
            "profile": "integrated",
        }),
    ],
)
```

Then:

1. Add `reflex_django` to `INSTALLED_APPS` and put `AsyncStreamingMiddleware` last in `MIDDLEWARE` ([full setup](https://web7ai.github.io/reflex-django/learn/integration/))
2. Create `shop/shop.py` with `app = rx.App()` and `app.add_page(...)` ([pages and state](https://web7ai.github.io/reflex-django/advanced/pages-and-state/))
3. Run `reflex django migrate` and `reflex run`
4. Open **http://localhost:3000/**

[Learn each integration piece step by step →](https://web7ai.github.io/reflex-django/learn/)

**API guides:** [Serializers](https://web7ai.github.io/reflex-django/advanced/serializers/) · [Model state](https://web7ai.github.io/reflex-django/advanced/model-state/) · [Forms/FieldSpec](https://web7ai.github.io/reflex-django/advanced/forms/) · [Live updates](https://web7ai.github.io/reflex-django/advanced/live-updates/) · [Devtools](https://web7ai.github.io/reflex-django/advanced/devtools/) · [Auth](https://web7ai.github.io/reflex-django/advanced/auth/) · [Security](https://web7ai.github.io/reflex-django/advanced/security/) · [Config](https://web7ai.github.io/reflex-django/advanced/config/)

---

## Commands

```bash
reflex run
reflex export
reflex django migrate
reflex django makemigrations
reflex django createsuperuser
reflex django scaffold shop.Product --output shop/product_views.py
```

---

## Requirements

| | Version |
|:---|:---|
| reflex-django | 4.0+ |
| Python | 3.12+ |
| Django | 6.0+ |
| Reflex | >=0.9.4,<1.0 |

---

**Author:** Mohannad Irshedat · [Docs](https://web7ai.github.io/reflex-django/)
