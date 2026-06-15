---
level: beginner
tags: [setup]
---

# Install

**What you will learn:** How to add reflex-django to a Django project and run `reflex run` for local dev.

**When you need this:**

- You are starting a new hybrid Django + Reflex app, or you are about to follow the todo tutorial.
- You already have Django and want the minimum wiring before writing your first `@page`.

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

| You already have | Read |
|:---|:---|
| A **Django** project | [Add to an existing Django project](existing_django_project.md) |
| A **Reflex** project | [Plugin path](existing_reflex_project_plugin.md) |

Both use `ReflexDjangoPlugin` in `rxconfig.py` and `reflex run` for dev.

---

## 1. Install the packages

=== "uv (recommended)"

    ```bash
    uv add django reflex reflex-django
    ```

=== "pip"

    ```bash
    pip install django reflex reflex-django
    ```

---

## 2. Register `reflex_django` in settings

```python
--8<-- "snippets/minimal_settings.py"
```

Append `AsyncStreamingMiddleware` last. See [Async streaming middleware](../internals/streaming_middleware.md).

---

## 3. Add `rxconfig.py`

At the project root (next to `manage.py`):

```python
--8<-- "snippets/minimal_rxconfig.py"
```

---

## 4. Add the Reflex app module

Create `shop/shop.py` (match `app_name` in `rxconfig.py`):

```python
import reflex as rx

app = rx.App()
```

---

## 5. Wire `urls.py`

```python
--8<-- "snippets/minimal_urls.py"
```

---

## 6. Point ASGI at Django

```python
--8<-- "snippets/minimal_asgi.py"
```

---

## 7. Run

--8<-- "snippets/reflex_run_command.md"

The first run compiles the SPA and starts Vite. That can take a minute.

---

## Common bumps

**`AppRegistryNotReady` at import time**
Move Django model imports inside `@rx.event` handlers.

**`ModuleNotFoundError: shop.shop`**
Create `shop/shop.py` with `app = rx.App()` and set `app_name="shop"` in `rxconfig.py`.

---

**Next up:** [Your first app](quickstart.md)
