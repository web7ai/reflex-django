---
level: beginner
tags: [setup]
---

# Install

**What you will learn:** How to add reflex-django to a Django project so one command runs Vite and the ASGI backend together.

**When you need this:**

- You are starting a new hybrid Django + Reflex app, or you are about to follow the todo tutorial.
- You already have Django and want the minimum wiring before writing your first `@page`.

If you want the "why" before the "how", read [Why reflex-django exists](why_reflex_django.md) first. Otherwise, dive in. (Three packages and you are most of the way there.)

---

## What you need

| | Version |
|:---|:---|
| **Python** | 3.12 or newer |
| **Django** | 6.0 or newer |
| **Reflex** | 0.9.4 or newer |

!!! tip "No Django project yet?"
    The [Your first app](quickstart.md) tutorial creates one from scratch in about 15 minutes.

**Brownfield?** Pick the guide that matches what you already have:

- [Add to an existing Django project](existing_django_project.md): models, admin, API; you want Reflex pages
- [Add to an existing Reflex project](existing_reflex_project.md): `rxconfig.py` and `reflex run`; you want Django ORM and admin

---

## 1. Install the packages

We recommend [`uv`](https://github.com/astral-sh/uv), but `pip` works fine too.

=== "uv (recommended)"

    ```bash
    uv add django reflex reflex-django
    ```

=== "pip"

    ```bash
    pip install django reflex reflex-django
    ```

That installs Django, Reflex, and reflex-django. Nothing else to install.

---

## 2. Register `reflex_django` in settings

Add `"reflex_django"` to `INSTALLED_APPS`, your app, and append streaming middleware last in `MIDDLEWARE`:

```python
--8<-- "snippets/minimal_settings.py"
```

**Why the streaming middleware?** Django admin sometimes streams large responses. Under ASGI, that needs a small shim at the end of the middleware stack. It is harmless on plain HTTP servers. See [Async streaming middleware](async_streaming_middleware.md) if you are curious.

---

## 3. Wire `urls.py` and import pages

Import your page module so `@page` decorators register at startup. The SPA catch-all mounts automatically when `REFLEX_DJANGO_AUTO_MOUNT=True` (the default):

```python
--8<-- "snippets/minimal_urls.py"
```

`REFLEX_DJANGO_RX_CONFIG` in settings tells reflex-django which Django app owns the Reflex pages and which dev ports to use. See [Configuration](configuration.md) for every option.

---

## 4. Point ASGI at reflex-django

```python
--8<-- "snippets/minimal_asgi.py"
```

This is the single ASGI callable for `manage.py run_reflex` and for production (uvicorn, granian, hypercorn, and so on). Django and Reflex share one process in `django_outer` mode (the default).

---

## 5. Run

--8<-- "snippets/run_reflex_command.md"

The first run compiles the SPA and starts Vite. That can take a minute. After that, edits hot-reload on `:3000`.

!!! warning "Production settings"
    In production, always set `DJANGO_SETTINGS_MODULE` to your real settings module. Do not rely on `reflex_django.setup.default_settings` (insecure dev `SECRET_KEY`). See [Deployment](deployment.md).

---

## Common bumps

**`AppRegistryNotReady` at import time**
You imported a Django model at the top of `views.py`. Move the import inside your `@rx.event` handler.

**Settings seem ignored**
`DJANGO_SETTINGS_MODULE` from your shell wins over everything. Run `python -c "import os; print(os.environ.get('DJANGO_SETTINGS_MODULE'))"` to see what is set.

**`ModuleNotFoundError: shop.shop`**
Delete any leftover `rxconfig.py`. Set `"app_name": "shop"` in `REFLEX_DJANGO_RX_CONFIG` and import `shop.views` in `urls.py`. You do not need `{app}/{app}.py`.

---

## What just happened?

You installed three packages, registered one Django app, pointed ASGI at `reflex_django.asgi.entry.application`, and started the default two-port dev loop. Vite serves the SPA on `:3000`; Django and the Reflex backend listen on `:8000`. When `REFLEX_DJANGO_SEPARATE_DEV_PORTS=True`, Vite proxies admin, API, and `/_event` to the backend so cookies stay on one origin while you browse `:3000`.

---

**Next up:** [Your first app](quickstart.md)
