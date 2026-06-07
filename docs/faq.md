# FAQ

**What you will learn:** Short answers to the questions that come up most often, with links when you need more depth.

**When you need this:**

- You want a quick yes/no or one-paragraph answer.
- You are deciding whether reflex-django fits your project.

For step-by-step fixes (ports, CSRF, WebSockets, bundle errors), see [Troubleshooting](troubleshooting.md).

---

## Getting started

### Do I need to know Reflex first?

No. Start with [How Reflex works in 5 minutes](how_reflex_works.md). Django background: [How Django works in 5 minutes](how_django_works.md).

### Can I add this to an existing Django project?

Yes. See [Add to an existing Django project](existing_django_project.md).

### Can I add this to an existing Reflex project?

Yes. See [Add to an existing Reflex project](existing_reflex_project.md).

### What versions do I need?

Python 3.12+, Django 6.0+, Reflex 0.9.2+.

---

## Architecture and routing

### Is this two servers behind a proxy?

In production, usually **one ASGI process** on one port. In default dev, **two ports**: Vite `:3000` and backend `:8000`. See [Architecture](architecture.md).

### What is the difference between `django_outer` and `reflex_outer`?

**`django_outer` (default):** Django owns the public port; Reflex handles reserved paths like `/_event`.

**`reflex_outer`:** Reflex owns the public port; Django admin/API run on an internal HTTP worker (default `:8001`).

Same pages and state classes; only wiring changes. [Routing comparison](routing.md#choosing-a-mode-django_outer-vs-reflex_outer).

### Do I need CORS?

No for the SPA on the same origin. Keep CORS only for unrelated API clients.

### Do I need `reflex_mount()` in `urls.py`?

Not by default. `REFLEX_DJANGO_AUTO_MOUNT=True` appends the catch-all at startup. Call `reflex_mount()` only for overrides. [The three knobs](mental_model.md).

### Why is there no `rxconfig.py`?

v1.0 uses `REFLEX_DJANGO_RX_CONFIG` in `settings.py`. [Configuration](configuration.md).

### What is `app_name` in `REFLEX_DJANGO_RX_CONFIG`?

Reflex's compile label, not "pages must live in that app folder". [What is app_name](mental_model.md#what-is-app_name).

---

## State and auth

### Why is `self.request.user` missing or anonymous?

Subclass `AppState`, ensure `SessionMiddleware` and `AuthenticationMiddleware` are in `MIDDLEWARE`, and in tests use `begin_event_request`. [State management](state_management.md).

### Snapshot vs live user?

UI: `self.is_authenticated`. Authorization: `self.request.user.is_authenticated`. [Live vs snapshot rule](authentication.md#the-live-vs-snapshot-rule).

### Does CSRF protect Reflex events?

CSRF is skipped on WebSocket events by design. Use login checks and server-side ownership instead. [Authentication](authentication.md).

### Can I use django-allauth or OAuth?

Yes. Session-based auth works for both HTTP and Reflex events once the session is set.

---

## CRUD and forms

### `ModelState` or `ModelCRUDView`?

Start with `ModelState`. Use `ModelCRUDView` when you want explicit serializer classes. [Comparison](model_state_and_crud_view.md).

### Where do I add validation?

`clean_<field>`, then `validate_state`, then `run_model_validation`. [Forms and validation](forms_and_validation.md).

---

## Development

### Which URL do I open, `:3000` or `:8000`?

**`:3000`** for the SPA in default dev. **`:8000`** for admin/API directly, or everything with `run_reflex --env dev`. [Local development](local_development.md).

### Hot reload stopped working?

See [Troubleshooting (ports and proxies)](troubleshooting.md).

### Can I edit models without rebuilding the SPA?

Yes: `python manage.py run_reflex --from-build --skip-rebuild`. [CLI reference](cli.md).

---

## Deployment

### One container or two?

One ASGI app for **`django_outer`**. **`reflex_outer`** may use two supervised processes internally. [Deployment](deployment.md).

### Must I rebuild the SPA every deploy?

Build once in CI with `export_reflex`, not at every container boot.

---

## Errors (short answers)

| Question | Short answer | Details |
|:---|:---|:---|
| `AppRegistryNotReady`? | Move model imports inside handlers. | [Troubleshooting](troubleshooting.md) |
| `SynchronousOnlyOperation`? | Use async ORM in async handlers. | [Database integration](database_integration.md) |
| `Could not find compiled SPA`? | Run `run_reflex` or `export_reflex`. | [Troubleshooting](troubleshooting.md) |
| White page / dispatch errors? | Clean rebuild of `.web/`. | [Troubleshooting](troubleshooting.md) |
| Admin 403 CSRF in dev? | Trust both ports; use dev middleware. | [Troubleshooting](troubleshooting.md) |
| WebSocket disconnects? | Raise proxy idle timeout (300s+). | [Deployment](deployment.md) |

---

## Comparisons

### vs Django + React SPA?

You write Python, not JSX. One process, shared cookies. [Why reflex-django](why_reflex_django.md).

### vs htmx?

htmx enhances server HTML; reflex-django ships a full reactive SPA. Different trade-offs.

### vs Channels + separate SPA?

Channels is plumbing; reflex-django includes SPA, WebSocket, and state in Python.

---

## Compatibility

### Django 5 or 4?

Targets Django 6.0+. Django 5 may work; Django 4 is not supported.

### SQLite in production?

Fine for dev; prefer Postgres under concurrent load.

---

## What just happened?

You got concise Q&A with pointers to topic pages and troubleshooting for anything that needs a longer fix.

## Next up

[Glossary →](glossary.md)