# `REFLEX_DJANGO_*` settings

Every knob the library exposes, organized by what it controls. Defaults are sensible — most projects don't change any of these.

For *how* to use them in context, see [Configuration](configuration.md) and [The three knobs](mental_model.md).

---

## Routing

Who handles which URL path — Django views vs the Reflex SPA catch-all vs reserved WebSocket prefixes.

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_AUTO_MOUNT` | `bool` | `True` | Append the Reflex SPA catch-all to `ROOT_URLCONF` at startup (`ReflexDjangoConfig.ready()` and ASGI bootstrap). Set `False` for Django-only installs, tests, or custom URL layouts. Env `REFLEX_DJANGO_AUTO_MOUNT=0` also disables it. Skipped automatically in `REFLEX_LED` routing mode. |
| `REFLEX_DJANGO_URL_ROUTING` | `str` | `"auto"` → `"django_outer"` | Routing mode. Almost never change. Other values: `"reflex_led"` (legacy two-port), `"django_led"`. |
| `REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES` | `tuple[str, ...]` | `()` | Extra path prefixes always routed to Reflex (added to the built-in list: `/_event`, `/_upload`, `/_health`, `/ping`, `/_all_routes`, `/auth-codespace`). |

---

## Serving

How the compiled SPA is built, proxied in dev, and served in production.

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_SERVE_FROM_BUILD` | `bool` | `False` | When `False` (default), `run_reflex` runs Vite for HMR. Set `True` (or pass `--from-build`) to auto-build the SPA and serve it from disk. |
| `REFLEX_DJANGO_AUTO_EXPORT_ON_START` | `bool` | `True` | When the ASGI entry point (`reflex_django.asgi_entry:application`) boots and finds no compiled SPA on disk, build it once (equivalent to `export_reflex --frontend-only --no-zip --stage-to-static-root`). Lets a bare `uvicorn backend.asgi:application` deploy work without a separate `reflex export` step. Set `False` (or env `REFLEX_DJANGO_AUTO_EXPORT_ON_START=0`) when the bundle is pre-built in CI / the filesystem is read-only. `run_reflex` disables it automatically (it builds itself). Requires Node/npm on the host. |
| `REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE` | `bool` | `True` | Pipe `STATIC_ROOT/_reflex/index.html` through Django's template engine so `{{ request.user }}`, `{% csrf_token %}` work in the SPA shell. |
| `REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX` | `bool` | `False` | Show or hide the "Built with Reflex" footer. |
| `REFLEX_DJANGO_DEV_PROXY` | `bool` | `True` when `DEBUG=True` | Auto-managed by `run_reflex` (forced on in the default Vite mode, off for `--from-build`/`--env prod`). When on, Django reverse-proxies SPA routes to Vite instead of serving a disk bundle. When you run a bare ASGI server with `DEBUG=True` and Vite is down, the entry point disables the proxy once at startup. Set env `REFLEX_DJANGO_DEV_PROXY=1` to force it on, or `0` to force it off. |
| `REFLEX_DJANGO_FRONTEND_PORT` | `int` | `3000` | Vite dev server port. Prefer `REFLEX_DJANGO_RX_CONFIG["frontend_port"]`; also env `REFLEX_DJANGO_FRONTEND_PORT`. |
| `REFLEX_DJANGO_BACKEND_PORT` | `int` | `8000` | ASGI server port — the URL you open in dev (`http://localhost:8000/`). Prefer `REFLEX_DJANGO_RX_CONFIG["backend_port"]`; also env `REFLEX_DJANGO_BACKEND_PORT`. |

There are no other `REFLEX_DJANGO_*` keys for Vite CSRF or `EventLoopContext` patches — use Django settings (`CSRF_TRUSTED_ORIGINS`, `USE_X_FORWARDED_HOST`) and optional [`django_dev_middleware`](local_development.md#django-dev-middleware-recommended). Frontend stability patches run automatically in `post_compile`.

---

## Reflex runtime (`rx.Config`)

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_RX_CONFIG` | `dict` | `{}` | Reflex `rx.Config` overrides: **`app_name`** ([compile label](mental_model.md#what-is-app_name), not "pages must live in `{app_name}/views.py`"), `frontend_port`, `backend_port`, `redis_url`, `frontend_packages`, `db_url`, CORS, log level, telemetry, etc. **Preferred home for `app_name`, ports, and Redis** — not `urls.py`. Merged with any per-mount `rx_config=` passed to `reflex_mount()`. |
| `REFLEX_DJANGO_PLUGINS` | `list` | `[]` | Reflex plugins as dotted import paths or instances (e.g. `"reflex.plugins.RadixThemesPlugin"`). |
| `REFLEX_DJANGO_CREATE_APP` | `str \| None` | `None` | Dotted path to a zero-arg callable returning a custom `rx.App` (e.g. `"myapp.reflex.create_app"`). Used by `get_or_create_app()` before the built-in default. |

`django_prefix` is **not** a setting — it is auto-detected from your `urlpatterns` when you append `reflex_mount()` last. Pass `django_prefix=(...)` to `reflex_mount()` only to override.

---

## Frontend toolchain

| Setting | Type | Default | Purpose |
|:---|:---|:---|:---|
| `REFLEX_DJANGO_VITE_VERSION` | `str \| None` | `None` | Override the `vite` devDependency Reflex writes into `.web/package.json`. When unset (the default), the version that ships with the installed `reflex_base` package is used as-is. Also readable from the env var of the same name; the Django setting wins if both are present. See [When to use it](#when-to-pin-vite) below. |

### When to pin Vite

You usually don't need this — the version `reflex_base` ships with is the version Reflex tested against. Reach for it when a Reflex release pins a Vite version that has a known frontend regression. The typical symptom is the SPA loading but throwing an exception inside the Reflex Socket.IO dispatcher or inside a third-party chart library:

```
[Reflex Frontend Exception] TypeError: t is not a function
    at .../assets/es6-<hash>.js
[Reflex Frontend Exception] TypeError: d is not a function
    at Socket.<anonymous> (.../assets/theme-<hash>.js)
```

That pattern (single-letter local variable that should be a function, called inside a memoized factory wrapper) is the Rolldown CJS-interop bug shipped with Vite 8.0.x. Pin to the latest Rollup-based release (Vite 7.3.3) until upstream ships a fix:

```python
# settings.py
REFLEX_DJANGO_VITE_VERSION = "7.3.3"
```

Or, equivalently, from the shell:

```bash
export REFLEX_DJANGO_VITE_VERSION=7.3.3
python manage.py run_reflex
```

Then wipe and rebuild:

```bash
rm -rf .web staticfiles/_reflex
python manage.py run_reflex
```

The override is applied during `install_reflex_django_integration()` — i.e. before Reflex regenerates `.web/package.json` — so the new version sticks across every `reflex export` / `reflex_mount` call in that process.

> Stay within `@react-router/dev`'s supported peer range (currently `^5.1.0 || ^6.0.0 || ^7.0.0 || ^8.0.0`). Vite 6 and 7 still use Rollup; Vite 5 is too old to honour the `unstable_optimizeDeps` flag `@react-router/dev` emits and breaks transitive-package resolution at build time.

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
| `REFLEX_DJANGO_AUTO_DISCOVER_PAGES` | `bool` | `True` | Walk `INSTALLED_APPS` and import `{app}.views` for `@page` decorators. |
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
