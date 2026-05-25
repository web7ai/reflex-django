# `REFLEX_DJANGO_*` settings

Every knob the library exposes, organized by what it controls. Defaults are sensible — most projects don't change any of these.

For *how* to use them in context, see [Configuration with `reflex_mount()`](configuration.md).

---

## Routing

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_URL_ROUTING` | `str` | `"auto"` → `"django_outer"` | Routing mode. Almost never change. Other values: `"reflex_led"` (legacy two-port), `"django_led"`. |
| `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES` | `tuple[str, ...]` | `()` | Extra path prefixes always routed to Reflex (added to the built-in list: `/_event`, `/_upload`, `/_health`, `/ping`, `/_all_routes`, `/auth-codespace`). |

---

## Serving

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_SERVE_FROM_BUILD` | `bool` | `True` | `run_reflex` auto-builds the SPA and serves it from disk. Set `False` for `--with-vite` HMR. |
| `REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE` | `bool` | `True` | Pipe `STATIC_ROOT/_reflex/index.html` through Django's template engine so `{{ request.user }}`, `{% csrf_token %}` work in the SPA shell. |
| `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX` | `bool` | `False` | Show or hide the "Built with Reflex" footer. |
| `REFLEX_DJANGO_DEV_PROXY` | `bool` | `False` | Auto-managed by `run_reflex --with-vite`. Don't set manually. |

---

## Event middleware chain

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN` | `bool` | `True` | Run the full `settings.MIDDLEWARE` chain on every Reflex event. |
| `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP` | `tuple[str, ...]` | `("django.middleware.csrf.CsrfViewMiddleware", "reflex_django.streaming_middleware.AsyncStreamingMiddleware")` | Middleware classes (by import path) to skip on WebSocket events. |
| `REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE` | `bool` | `True` | Convert 3xx responses from middleware into `rx.redirect(...)` automatically. |
| `REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD` | `bool` | `False` | Feed event handler kwargs into the synthetic `request.POST`. |
| `REFLEX_DJANGO_ACTIVATE_LANGUAGE_ON_EVENT` | `bool` | `True` | Run `translation.activate(...)` on each event using the bridge's language selection. |

---

## Reactive mirrors

These control which Django values appear as reactive variables on `DjangoUserState` (so you can bind them in components).

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_MIRROR_MESSAGES` | `bool` | `True` | Mirror `django.contrib.messages` to `DjangoUserState.messages`. |
| `REFLEX_DJANGO_MIRROR_CSRF` | `bool` | `True` | Mirror the CSRF token to `DjangoUserState.csrf_token`. |
| `REFLEX_DJANGO_MIRROR_LANGUAGE` | `bool` | `True` | Mirror language to `DjangoUserState.language` and `language_bidi`. |
| `REFLEX_DJANGO_AUTH_AUTO_SYNC` | `bool` | `True` | Refresh `AppState` user snapshot fields (`is_authenticated`, `username`, …) on every event. |

---

## Page discovery

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_AUTO_DISCOVER_PAGES` | `bool` | `True` | Walk `INSTALLED_APPS` and import `{app}.views` for `@template`/`@page` decorators. |
| `REFLEX_DJANGO_PAGE_PACKAGES` | `list[str]` | `[]` | Explicit list of page modules. When non-empty, disables auto-discovery. |
| `REFLEX_DJANGO_PAGE_APPS` | `list[str] \| None` | `None` | Allowlist of app labels for auto-discovery. `None` = scan all. |
| `REFLEX_DJANGO_PAGE_MODULE` | `str` | `"views"` | Which submodule to import per app. |

---

## Context processors

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_AUTO_LOAD_CONTEXT` | `bool` | `True` | Run context processors on every Reflex event. |
| `REFLEX_DJANGO_CONTEXT_PROCESSORS` | `tuple[str, ...]` | `()` | Dotted paths of `f(request) -> dict` callables. |
| `REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS` | `bool` | `True` | If `REFLEX_DJANGO_CONTEXT_PROCESSORS` is empty, fall back to Django's template context processors. |

---

## Plugin and rxconfig

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_USE_RXCONFIG_FILE` | `bool` | `False` | Merge an existing on-disk `rxconfig.py` into the runtime config. |
| `REFLEX_DJANGO_MATERIALIZE_RXCONFIG` | `bool` | `False` | Write a stub `rxconfig.py` to disk for tooling compatibility. |
| `REFLEX_DJANGO_PLUGIN` | `dict` | `{}` | Extra kwargs for the built-in `ReflexDjangoPlugin`. |
| `REFLEX_DJANGO_AUTO_PLUGIN` | `bool` | `True` | Always-on. Kept for backwards compatibility. |

---

## Auth

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_LOGIN_URL` | `str` | `"/login"` | Where `@login_required` / `@permission_required` redirect to. |
| `REFLEX_DJANGO_AUTH` | `dict` | see [Login & sessions](authentication.md#customizing-them) | Configuration for the built-in auth pages (URLs, titles, password rules, …). |

---

## Default skip list, in full

The built-in default value of `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`:

```python
(
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
)
```

When you set the setting yourself, your value **replaces** the default. To extend rather than replace:

```python
from reflex_django.config import DEFAULT_EVENT_MIDDLEWARE_SKIP

REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP = (
    *DEFAULT_EVENT_MIDDLEWARE_SKIP,
    "myapp.middleware.SomethingYouDontWantOnEvents",
)
```

---

## Reading order for new projects

If you're scanning for the first time:

1. Most projects need **zero** of these. The defaults are good.
2. The first ones you'll touch are usually `REFLEX_DJANGO_AUTH` (built-in login pages) and `REFLEX_DJANGO_CONTEXT_PROCESSORS` (feature flags / site info).
3. Performance tuning: `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`, then `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN`.
4. Page layout: `REFLEX_DJANGO_PAGE_PACKAGES` if you want pages outside `INSTALLED_APPS`.

---

**Next:** [Public API at a glance →](public_api.md)
