# Public API at a glance

**What you will learn:** Where to find importable symbols and which topic page explains how to use each area.

**When you need this:**

- You know what you want to do but not which module to import from.
- You are scanning the package surface without rereading tutorials.

This page is an index only. For walkthroughs, follow the links.

---

## Typical imports

```python
from reflex_django.states import AppState, ModelState, DjangoUserState
from reflex_django.pages.decorators import page
from reflex_django.pages.decorators.templates import centered_template as template
from reflex_django.django.urls import reflex_mount
from reflex_django.auth import add_auth_pages, login_required, permission_required
from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django import request, current_request, current_user
from reflex_django.asgi.app import build_django_asgi, make_dispatcher
from reflex_django import app, create_app
from reflex_django.bridge.context import begin_event_request, end_event_request
from reflex_django.bridge import resolve_bridge_tier, invalidate_event_cache
```

Most projects import little beyond this list. Full paths are in the tables below.

---

## Package layout (v2)

```text
reflex_django/
  asgi/          build_django_asgi, make_dispatcher
  runtime/       app factory, integration, reflex_app
  bridge/        request bridge, event middleware, context
  django/        apps, urls, admin, model
  dev/           dev proxy, Vite, internal runners
  setup/         conf, routing, rxconfig bridge
  states/        public State classes (AppState, …)
  auth_state.py  DjangoUserState (canonical for event handler keys)
  state/         internal model-state framework
  auth/          auth pages and decorators
```

---

## Topic index

| Area | Key symbols | Guide |
|:---|:---|:---|
| **Pages** | `page`, `centered_template`, `reflex_mount`, `admin_urlpatterns` | [Pages in views](../guides/pages.md), [Configuration](../getting-started/configuration.md) |
| **State** | `AppState`, `ModelState`, `ModelCRUDView`, `ModelListView`, `DjangoUserState`, `DjangoAuthState` | [State management](../guides/state.md), [Reactive model state](../guides/crud.md#modelstate), [CRUD with mixins](../guides/crud.md#modelcrudview) |
| **Mixins** | `LoginRequiredMixin`, `UserScopedMixin`, `PermissionMixin`, CRUD mixins | [Mixins](../guides/mixins.md) |
| **Serializers** | `ReflexDjangoModelSerializer`, `serialize_model_row` | [Serializers](../guides/serializers.md) |
| **Auth** | `add_auth_pages`, `login_required`, `permission_required`, auth page classes | [Authentication](../guides/authentication.md), [Auth branding](../guides/authentication.md#make-it-yours) |
| **Request access** | `self.request`, `request` proxy, `current_*` helpers | [State management](../guides/state.md#reading-the-request) |
| **Testing** | `begin_event_request`, `end_event_request` | [Testing](../operations/testing.md) |
| **ASGI / bootstrap** | `application`, `build_application`, `install_reflex_django_integration` | [Architecture](../internals/architecture.md), [Deployment](../operations/deployment.md) |
| **Middleware** | `AsyncStreamingMiddleware`, `DEFAULT_DEV_MIDDLEWARE` | [Middleware in events](../guides/middleware.md), [Local development](../getting-started/local_development.md) |
| **Performance** | `RX_EVENT_BRIDGE_MODE`, `resolve_bridge_tier`, `invalidate_event_cache` | [Scaling and performance](../operations/scaling.md) |
| **CLI** | `run_reflex`, `export_reflex`, `reflex django ...` | [CLI reference](../operations/cli.md) |
| **Settings** | All `RX_*` keys | [Settings reference](settings.md) |
| **Routing** | `UrlRoutingMode`, `resolve_url_routing` | [Routing](../internals/routing.md) |
| **Uploads / media** | `rx.upload`, Django `FileField` | [File uploads](../guides/uploads.md), [Media files](../guides/media.md) |
| **i18n** | `DjangoI18nState` | [i18n](../guides/i18n.md) |
| **Admin** | `register_admin` | Django admin docs + [Configuration](../getting-started/configuration.md) |

---

## Lazy imports

The top-level `reflex_django` package uses PEP 562 lazy access so importing it does not touch Django's app registry:

```python
import reflex_django

reflex_django.add_auth_pages
reflex_django.ReflexDjangoPlugin  # deprecated in v1.0; use settings-based config
```

State classes and page decorators live in dedicated modules (see typical imports above).

---

## Versioning

Public symbols linked from topic pages follow semantic versioning. Names under `reflex_django._*` or deep private helpers may change between releases.

```bash
python -c "import importlib.metadata; print(importlib.metadata.version('reflex-django'))"
```

---

## What just happened?

You got a map from feature area to import names and the right deep-dive page, without duplicated tutorials.

## Next up

[FAQ →](faq.md)