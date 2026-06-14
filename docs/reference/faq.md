# FAQ

**What you will learn:** Short answers to the questions that come up most often, with links when you need more depth.

**When you need this:**

- You want a quick yes/no or one-paragraph answer.
- You are deciding whether reflex-django fits your project.

For step-by-step fixes (ports, CSRF, WebSockets, bundle errors), see [Troubleshooting](../operations/troubleshooting.md).

---

## Getting started

### Do I need to know Reflex first?

No. Start with [How Reflex works in 5 minutes](../overview/concepts.md). Django background: [How Django works in 5 minutes](../overview/concepts.md).

### Can I add this to an existing Django project?

Yes. See [Add to an existing Django project](../getting-started/existing_django_project.md).

### Can I add this to an existing Reflex project?

Yes. Two integration paths:

- **Settings path** — move config to `RX_CONFIG`, use `python manage.py run_reflex`. See [Add to an existing Reflex project](../getting-started/existing_reflex_project.md).
- **Plugin path** — add `ReflexDjangoPlugin` to `rxconfig.py`, keep `reflex run`. See [Plugin path for existing Reflex](../getting-started/existing_reflex_project_plugin.md).

Both require a Django shell (`manage.py`, `settings.py`, `urls.py`).

### What versions do I need?

Python 3.12+, Django 6.0+, Reflex 0.9.2+.

---

## Architecture and routing

### Is this two servers behind a proxy?

In production, usually **one ASGI process** on one port. In default dev, **two ports**: Vite `:3000` and backend `:8000`. See [Architecture](../internals/architecture.md).

### How does routing work in dev?

Default: `run_reflex` runs Vite on `:3000` and the Reflex backend on `:8000`. Django admin/API are mounted **in-process** inside the Reflex backend. Vite proxies all backend paths there. Set `RX_PROXY_SERVER` only when Django runs separately. See [Routing](../internals/routing.md) and [Local development](../getting-started/local_development.md).

!!! note "Legacy modes removed"
    **`django_outer`** and **`reflex_outer`** were removed in v3. Older docs may still mention them; use the mount-only model instead.

### Do I need CORS?

No for the SPA on the same origin. Keep CORS only for unrelated API clients.

### Do I need `reflex_mount()` in `urls.py`?

Not by default. `RX_AUTO_MOUNT=True` appends the catch-all at startup. Call `reflex_mount()` only for overrides. [The three knobs](../overview/concepts.md).

### Why is there no `rxconfig.py`?

v1.0 uses `RX_CONFIG` in `settings.py`. [Configuration](../getting-started/configuration.md).

### What is `app_name` in `RX_CONFIG`?

Reflex's compile label, not "pages must live in that app folder". [What is app_name](../overview/concepts.md#what-is-app_name).

---

## State and auth

### Why is `self.request.user` missing or anonymous?

Subclass `AppState`, ensure `SessionMiddleware` and `AuthenticationMiddleware` are in `MIDDLEWARE`, and in tests use `begin_event_request`. [State management](../guides/state.md).

### Snapshot vs live user?

UI: `self.is_authenticated`. Authorization: `self.request.user.is_authenticated`. [Live vs snapshot rule](../guides/authentication.md#the-live-vs-snapshot-rule).

### Does CSRF protect Reflex events?

CSRF is skipped on WebSocket events by design. Use login checks and server-side ownership instead. [Authentication](../guides/authentication.md).

### Can I use django-allauth or OAuth?

Yes. Session-based auth works for both HTTP and Reflex events once the session is set.

---

## CRUD and forms

### `ModelState` or `ModelCRUDView`?

Start with `ModelState`. Use `ModelCRUDView` when you want explicit serializer classes. [Comparison](../guides/crud.md#choosing).

### Where do I add validation?

`clean_<field>`, then `validate_state`, then `run_model_validation`. [Forms and validation](../guides/forms.md).

---

## Development

### Which URL do I open, `:3000` or `:8000`?

**`:3000`** for the SPA in default dev. **`:8000`** for admin/API directly, or everything with `run_reflex --env dev`, `--from-build`, or `--env prod`. [Local development](../getting-started/local_development.md).

### How do I run production locally?

After `export_reflex` + `collectstatic`, run `python manage.py run_reflex --env prod --skip-rebuild` and browse `:8000`. For split Django ASGI + Reflex + proxy, see [Deployment](../operations/deployment.md).

### Hot reload stopped working?

See [Troubleshooting (ports and proxies)](../operations/troubleshooting.md).

### Can I edit models without rebuilding the SPA?

Yes: `python manage.py run_reflex --from-build --skip-rebuild`. [CLI reference](../operations/cli.md).

---

## Deployment

### One container or two?

**Path A (single-process):** one `run_reflex --env prod` process for SPA, admin, API, and `/_event`. **Path B (split):** Django ASGI for HTTP plus a separate Reflex backend behind your proxy. In dev, the Reflex backend serves both Reflex and Django routes in one process. [Deployment](../operations/deployment.md).

### Must I rebuild the SPA every deploy?

Build once in CI with `export_reflex`, not at every container boot.

---

## Errors (short answers)

| Question | Short answer | Details |
|:---|:---|:---|
| `AppRegistryNotReady`? | Move model imports inside handlers. | [Troubleshooting](../operations/troubleshooting.md) |
| `SynchronousOnlyOperation`? | Use async ORM in async handlers. | [Database integration](../guides/database.md) |
| `Could not find compiled SPA`? | Run `run_reflex` or `export_reflex`. | [Troubleshooting](../operations/troubleshooting.md) |
| White page / dispatch errors? | Clean rebuild of `.web/`. | [Troubleshooting](../operations/troubleshooting.md) |
| Admin 403 CSRF in dev? | Trust both ports; use dev middleware. | [Troubleshooting](../operations/troubleshooting.md) |
| WebSocket disconnects? | Raise proxy idle timeout (300s+). | [Deployment](../operations/deployment.md) |

---

## Comparisons

### vs Django + React SPA?

You write Python, not JSX. One process, shared cookies. [Why reflex-django](../overview/concepts.md).

### vs htmx?

htmx enhances server HTML; reflex-django ships a full reactive SPA. Different trade-offs.

### vs Channels + separate SPA?

Channels is plumbing; reflex-django includes SPA, WebSocket, and state in Python.

---

## Compatibility

### Upgrading to 3.0?

See [Migrating to v3](migration/v3_cleanup.md) for removed plugin APIs, page discovery changes, and import renames. If you still have `REFLEX_DJANGO_*` settings, also read [RX settings rename](migration/rx_settings_rename.md).

### Django 5 or 4?

Targets Django 6.0+. Django 5 may work; Django 4 is not supported.

### SQLite in production?

Fine for dev; prefer Postgres under concurrent load.

---

## What just happened?

You got concise Q&A with pointers to topic pages and troubleshooting for anything that needs a longer fix.

## Next up

[Glossary →](glossary.md)