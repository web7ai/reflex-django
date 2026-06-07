# FAQ

Short answers to the questions that come up most often. Each one links to the longer treatment if you want detail.

---

## Getting started

### Do I need to know Reflex before using this?

No. If you're a Django developer, [How Reflex works in 5 minutes](how_reflex_works.md) gives you enough to read the rest of these docs. The official Reflex docs at [reflex.dev](https://reflex.dev) are excellent for deeper learning.

### Do I need to know Django?

A little helps. [How Django works in 5 minutes](how_django_works.md) is enough for the rest of these docs. If you've used FastAPI or Flask, the concepts are familiar.

### Can I use this with an existing Django project?

Yes — that's a primary use case. See [Add to an existing Django project](existing_django_project.md). Add `REFLEX_DJANGO_RX_CONFIG` to `settings.py`, import page modules in `urls.py`, and start dropping pages into any app's `views.py`. The SPA catch-all is automatic.

### Can I use this with an existing Reflex project?

Yes. See [Add to an existing Reflex project](existing_reflex_project.md). You wrap your Reflex app in a Django project shell, move config from `rxconfig.py` to `settings.py`, switch to `manage.py run_reflex`, and optionally upgrade `rx.State` to `AppState` when you need the ORM or `request.user`.

### What versions do I need?

Python 3.12+, Django 6.0+, Reflex 0.9.2+. Older Reflex versions don't have the plugin hooks we depend on.

---

## Architecture and routing

### Is this just running two servers behind a reverse proxy?

Not quite — and it depends on your routing mode.

- **`django_outer` (default):** One Python process on one port. An outer dispatcher sends each request to Django or Reflex's inner ASGI. ([Details](architecture.md).)
- **`reflex_outer`:** Reflex owns the public port; Django admin/API HTTP runs in a separate worker that Reflex proxies to internally. Reflex events and the ORM still run in the main process. Still one origin for the browser. ([Comparison with examples](routing.md#choosing-a-mode-django_outer-vs-reflex_outer).)

### What's the difference between `django_outer` and `reflex_outer`?

**`django_outer`** — Django answers the door. Almost all HTTP goes through Django (`/admin`, `/api`, the SPA catch-all). Reflex only handles reserved paths like `/_event`. One process, simplest setup. **Default for new projects.**

**`reflex_outer`** — Reflex answers the door. Your SPA and WebSocket events stay in the main process; `/admin` and `/api` are forwarded to a Django-only HTTP worker (port `8001` by default). Use this when heavy Django HTTP work was slowing down live Reflex sessions.

Same `urls.py`, same `@page` routes, same `AppState` — only the wiring changes. Full side-by-side examples: [Routing — Choosing a mode](routing.md#choosing-a-mode-django_outer-vs-reflex_outer).

### What about CORS?

You don't need it. The SPA, the API, the admin, and the WebSocket all share an origin. The browser sees them as the same site.

### Can I still use Django Channels?

`reflex-django` doesn't use Channels. Reflex owns the one WebSocket on `/_event`. If you need additional WebSocket protocols (chat, multiplayer game state, etc.) and the Reflex event model doesn't fit, Channels is fine to add alongside — but you'll need to route its WebSocket scopes around the outer dispatcher. Most projects don't need this.

### Do I need `reflex_mount()` in `urls.py`?

No — not for a default project. With `REFLEX_DJANGO_AUTO_MOUNT=True` (default), reflex-django appends the SPA catch-all at startup from `settings.py`. Call `reflex_mount()` only when you need URL overrides (`mount_prefix`, explicit `django_prefix`). See [The three knobs](mental_model.md).

### What is `app_name` in `REFLEX_DJANGO_RX_CONFIG`?

Reflex's **compile label** — like a project id for build artifacts. It is **not** "all pages must live in `{app_name}/views.py`". Multi-package projects can use `app_name: "core"` while pages live in `modules.ai.studio.views`. See [The three knobs — `app_name`](mental_model.md#what-is-app_name).

### Why does my app work without `import myapp.views` in `urls.py`?

Auto-discover (`REFLEX_DJANGO_AUTO_DISCOVER_PAGES=True`, default) imports every `{app}.views` from `INSTALLED_APPS` at compile time. That still works today but is deprecated — add explicit imports in `urls.py` or `REFLEX_DJANGO_PAGE_PACKAGES` before the next major release.

### Why isn't all Reflex config in `{app_name}/views.py`?

`views.py` is for pages and state. Ports, redis, plugins, and the compile label belong in `settings.py` (`REFLEX_DJANGO_RX_CONFIG`, `REFLEX_DJANGO_PLUGINS`) so Django, CI, and `run_reflex` share one source of truth. See [Configuration](configuration.md).

### Why is there no `rxconfig.py`?

`REFLEX_DJANGO_RX_CONFIG` and `REFLEX_DJANGO_PLUGINS` in `settings.py` replace it. If you have legacy tooling that reads `rxconfig.py`, set `REFLEX_DJANGO_USE_RXCONFIG_FILE = True` to merge it in.

### Why is there no `{app}/{app}.py`?

Use `from reflex_django import app` instead of `app = rx.App()` in a project file. Import your page modules (or rely on deprecated auto-discover) so `@page` decorators register routes on that singleton. See [Pages in views](pages_in_views.md).

---

## State and the request

### Why don't I see `self.request.user` in my handler?

Three things to check:

1. Does your state subclass `AppState` (not plain `rx.State`)?
2. Is `SessionMiddleware` in `MIDDLEWARE`?
3. Is `AuthenticationMiddleware` in `MIDDLEWARE`?

Without all three, the bridge can't populate the user. ([State Management](state_management.md).)

### Can I read `request.user` from a plain `rx.State`?

Yes — use the module-level proxy:

```python
from reflex_django import request

class FilterState(rx.State):
    @rx.event
    async def apply(self):
        if request.user.is_authenticated:
            ...
```

Or the functional helpers (`current_user()`, `current_request()`). All return the same per-event request. ([Details](state_management.md#reading-the-request).)

### `self.is_authenticated` vs `self.request.user.is_authenticated` — which one?

`self.is_authenticated` is a reactive snapshot, safe for UI rendering. `self.request.user.is_authenticated` is the live server-side check, the one to use for authorization. Never base security decisions on the snapshot alone. ([Live vs snapshot rule](authentication.md#the-live-vs-snapshot-rule-read-this-once).)

### Why is `self.request` `None` in my test?

Outside an event, there's no request. In tests, set one up:

```python
from reflex_django.context import begin_event_request, end_event_request

token = begin_event_request(user=test_user)
try:
    await state.my_handler()
finally:
    end_event_request(token)
```

([Testing](testing.md).)

### Why is `self.request.user` `AnonymousUser` even though I'm logged in?

Most likely: the SPA opened its WebSocket before you logged in, with the *anonymous* session cookie. After login, the browser has the new cookie, but the WebSocket is still using the old one. Either:

- Use the built-in login flow (`add_auth_pages()`) — it handles the cookie sync.
- After your custom login, redirect through an HTTP response that carries the fresh `Set-Cookie` header. ([Details](authentication.md#a-note-on-cookie-sync-after-login).)

---

## CRUD

### `ModelState` or `ModelCRUDView` — which one?

`ModelState` for new projects. It's shorter and auto-builds the serializer. Reach for `ModelCRUDView` when you want explicit serializer classes (e.g. sharing with DRF) or verb-noun handler names (`save_post` instead of `save`). ([Side by side](model_state_and_crud_view.md).)

### Can I mix `ModelState` and manual `AppState` handlers in the same project?

Absolutely. Use `ModelState` for standard CRUD pages, plain `AppState` for unusual workflows. They share the same Django context, the same auth, the same everything.

### How do I scope a list to the current user?

Three options, all in `ModelState`/`ModelCRUDView`:

1. Override `get_queryset`, `get_object_lookup`, `get_create_kwargs` manually.
2. Add `UserScopedMixin` and set `Meta.owner_field = "owner"`.
3. In a manual handler, filter with `Model.objects.filter(owner=self.request.user)`.

([Details](reactive_model_state.md#user-scoped-crud-only-show-my-rows).)

### Why isn't my list refreshing after save?

Three common causes:

1. `class Meta: list_var = "..."` is missing — the default name is `data`.
2. You're using `ModelCRUDView` but didn't call `on_load=YourState.on_load_<list_var>` on the page.
3. You overrode `save` without calling `super()` or `self.dispatch(ACTION_SAVE)`.

---

## Forms and validation

### Where do I add custom validation?

Three stages in order: `clean_<field>` for per-field, `validate_state` for cross-field, `run_model_validation = True` for Django's own validators (`unique=True`, `validators=[...]`). ([Details](forms_and_validation.md).)

### Why doesn't my form clear after save?

You need both `Meta.reset_after_save = True` (default) **and** `key=YourState.form_reset_key` on the `<rx.form>` element. The `key` triggers a React remount, which resets uncontrolled input state.

### My field-level errors aren't showing

Two things:

1. `Meta.structured_errors = True` (defaults to `True` on `ModelState`/`ModelCRUDView`).
2. Bind to `YourState.<list_var>_field_errors[field_name]` — not `YourState.error`.

---

## Auth

### Does CSRF protect Reflex events?

CSRF is intentionally skipped on Reflex WebSocket events. CSRF protects HTML form submissions where a third-party site could trigger a request with the user's cookies. WebSockets opened by your own SPA don't have that attack shape. For mutations, prefer `@login_required`, `@permission_required`, and server-side ownership checks. ([Details](authentication.md#what-about-csrf-on-reflex-events).)

### Can I use `django-allauth` or OAuth?

Yes. `reflex-django` builds on Django sessions. Once your OAuth flow completes, `request.user.is_authenticated` is `True` for both HTTP requests and Reflex events. No special setup is needed — wire up `django-allauth` (or `social-auth-app-django`) as you normally would.

### Can I use JWT instead of sessions?

Not for the SPA. The bridge is session-based — `request.user` is resolved from the session cookie. You can absolutely have a JWT endpoint alongside (for your mobile app); the SPA just uses the session.

### How do I gate a whole page?

Wrap the page function:

```python
from reflex_django.auth import login_required

@page(route="/account")
@login_required
def account() -> rx.Component:
    ...
```

For permission-based gating, use `permission_required("app.codename")`.

---

## Performance

### Is the per-event middleware chain slow?

The bridge runs your full `settings.MIDDLEWARE` for each Reflex event. For most apps that's microseconds of overhead per event (session lookup, user resolution). If you have expensive custom middleware that doesn't apply to events, add it to `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`.

### Can I have multiple ASGI workers?

Yes. Default rule of thumb: `2 * cores + 1`. State is stored per-process by default, so enable sticky session affinity on your load balancer, or point Reflex at Redis for shared state:

```python
# settings.py
REFLEX_DJANGO_RX_CONFIG = {
    "redis_url": os.environ["REDIS_URL"],
}
```

### Why is my page slow on first load?

The compiled SPA might not be on disk yet, so `manage.py run_reflex` is building it. After the first build, reloads are fast. In production, the SPA is built in CI and shipped in the container.

---

## Development workflow

### Hot reload doesn't work for Reflex page edits

The default `python manage.py run_reflex` already runs Vite for hot-module reload — editing a Reflex page recompiles the SPA and Vite hot-reloads the frontend, with the backend left running. If hot reload isn't firing, make sure you didn't pass `--from-build` (which serves a static bundle from disk) or `--no-reload` (which disables the watch loop), and that `watchfiles` is installed (`pip install "uvicorn[standard]"`).

### My state / event-handler edit didn't take effect

In the default Vite mode the backend boots once and stays up, so server-side Python (states, event handlers, models) is only re-read when you restart the command. Stop `run_reflex` and run it again to pick up backend changes. Pure UI/page edits don't need a restart — they hot-reload through Vite.

### Can I edit a Django model without rebuilding the SPA?

Yes — use `--from-build --skip-rebuild`:

```bash
python manage.py run_reflex --from-build --skip-rebuild
```

In that mode the uvicorn server restarts on Python changes, but the slow SPA export step is skipped.

### Where does the compiled SPA live?

`STATIC_ROOT/_reflex/` in production. In development, `manage.py run_reflex` builds and stages it there automatically. The source bundle lives in `.web/` (gitignored).

### The SPA loads but crashes with `TypeError: t is not a function` / `d is not a function`

You're hitting a Vite/Rolldown bundler regression — usually a CJS-interop bug in Vite 8.0.x that emits `var r=r(), t=t(), n=n(), i=i();` inside memoized factory wrappers. Pin the last Rollup-based Vite from your Django settings:

```python
# settings.py
REFLEX_DJANGO_VITE_VERSION = "7.3.3"
```

Then wipe `.web/` and `STATIC_ROOT/_reflex/` and rebuild. See [`REFLEX_DJANGO_VITE_VERSION`](settings_reference.md#frontend-toolchain) for the full rundown.

---

## Deployment

### One container or two?

One. The whole point of `reflex-django` is single-process: Django and Reflex live in the same uvicorn worker. Your deploy is one ASGI app.

### Can I deploy to Heroku / Railway / Fly / ECS / Cloud Run?

Yes — anywhere that supports WebSockets and an ASGI server (uvicorn / granian / hypercorn / gunicorn-uvicorn-worker). See platform-specific notes in the [Deployment guide](deployment.md).

### Does the SPA need to be rebuilt for every deploy?

Yes — but only once, in CI, not at every container boot:

```bash
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
python manage.py collectstatic --noinput
```

Bake those into your image build. The runtime container then serves the pre-built bundle.

### How long should the WebSocket idle timeout be on my proxy?

At least 300 seconds. The SPA holds the WebSocket open for the user's whole session. Default Nginx 60s timeout drops the connection too aggressively.

---

## Errors and debugging

### `AppRegistryNotReady`

You're touching a Django model at module import time (in a class-level default, a module-level query, or the top of a file imported very early). Move the model import inside an event handler:

```python
@rx.event
async def load(self):
    from shop.models import Product
    ...
```

### `SynchronousOnlyOperation`

You used a sync ORM call in an async event handler. Replace with `aget`, `acreate`, `asave`, `adelete`, `async for`. ([Database integration](database_integration.md).)

### `ModuleNotFoundError: shop.shop`

A leftover `rxconfig.py` is pointing at the old layout. Delete `rxconfig.py` and put `app_name` in `REFLEX_DJANGO_RX_CONFIG` in `settings.py`.

### `Could not find compiled SPA`

The SPA hasn't been built yet. Run `python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root`, or just `python manage.py run_reflex` and let it build automatically.

### Browser console: `dispatch is not a function` / `h[M] is not a function` (page stuck on loading skeleton)

The compiled SPA's state dispatcher map is missing an entry for a substate the running backend is sending deltas for. Two distinct causes:

**Cause 1 — drift between build and runtime.** `.web/` was generated against an older set of Python imports than the process is now serving (added/renamed a substate, switched branches, edited a `class XxxState(rx.State)`). Recovery: stop the server, delete `.web/` (or `.web/build/` + `.web/utils/state.js`), restart `python manage.py run_reflex`, hard-refresh the browser (Ctrl+Shift+R).

**Cause 2 — runtime-attached substates that the frontend codegen missed.** Some `reflex_django` state classes (for example `DjangoAuthState`) are exposed via :pep:`562` lazy attribute access and were historically first imported after the SPA had already been compiled. Since 0.5.x, `reflex_django.app_factory.prepare_pages_for_compile` (and `ensure_django_led_app_ready`) eagerly imports these classes before Reflex walks the state tree. A clean rebuild (`rm -rf .web && python manage.py run_reflex`) fixes stale bundles.

**Defensive fallback.** As of 0.5.x `reflex-django` also patches Reflex's `utils/state.js` template at boot so the WebSocket event handler *tolerates* unknown substates: instead of throwing and freezing the page, it logs

```
[reflex-django] No dispatcher for substate '<name>' — skipping delta.
Known dispatchers: …
```

…and continues rendering. If you ever see that warning after a clean rebuild, share the substate name — that's a real registration-timing bug we can fix upstream by extending the eager-import list in `_ensure_runtime_state_classes_registered`.

### Tasks/middleware silently doesn't run on events

You probably set `REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN = False` somewhere (or your middleware is in `REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP`). Remove the override.

---

## Comparisons

### How is this different from running Django + a React SPA?

You don't write React. You don't write JSX. You don't run a Node build server. Pages, state, and event handlers are all in Python. The SPA still exists — it's just compiled for you.

### How is this different from htmx / Unpoly?

htmx and Unpoly add reactivity to *server-rendered HTML* by intercepting form submissions and link clicks. `reflex-django` ships a real React SPA backed by a persistent WebSocket. Different trade-off: htmx is lighter and works with any backend; `reflex-django` is heavier but gives you a fully reactive client without writing JavaScript.

### How is this different from Django Channels + a separate SPA?

Channels gives you WebSocket *plumbing*, but you still write the SPA yourself. `reflex-django` gives you the SPA, the WebSocket, the state management, and the bridge — all in Python.

### Why not just use `django-htmx` or live-reload?

If those fit your needs, use them. They're great for adding selective interactivity to a server-rendered Django app. `reflex-django` makes sense when you want a *full SPA* but don't want to write React.

---

## Development (Vite port and CSRF)

### Which URL do I open in dev — `localhost:8000` or `3000`?

**`http://localhost:3000/`** for frontend work. `python manage.py run_reflex` starts **both** Vite (`:3000`, SPA + hot reload) and the Django/Reflex backend (`:8000`, admin, API, `/_event`). Vite proxies backend paths to `:8000` so cookies still work.

Use **`http://localhost:8000/`** directly when you want admin or API without going through Vite. Pass **`--single-port`** to `run_reflex` if you prefer browsing only `:8000` (Django reverse-proxies Vite). Full setup: [Local development](local_development.md).

### "Reflex SPA bundle not found" on `:8000`

In default two-port dev, `:8000` does not serve the SPA shell — open **`http://localhost:3000/`**. If you use `--single-port` and still see this, start dev with `python manage.py run_reflex --single-port` (not `runserver`). If port `3000` is busy, free it and restart. See [Local development — troubleshooting](local_development.md#troubleshooting).

### Django admin returns 403 CSRF

Add both `:8000` and `:3000` to `CSRF_TRUSTED_ORIGINS`, set `USE_X_FORWARDED_HOST = True`, and put `reflex_django.django_dev_middleware.DEFAULT_DEV_MIDDLEWARE` at the top of `MIDDLEWARE` in dev settings. See [Local development](local_development.md).

### `useContext is not a function or its return value is not iterable`

Reflex’s generated `EventLoopContext` default and array destructuring can throw before the provider mounts. **reflex-django** patches `.web` after compile (`frontend_stability`). Restart `run_reflex`, hard-refresh the browser, and check the compile log for “frontend stability patches”. Do not add Vite aliases that map `react` to `react/index.js` — that breaks `react/jsx-runtime`. Details: [Local development](local_development.md#troubleshooting).

### Should I copy dev middleware into my project?

No — import from `reflex_django.django_dev_middleware` (or use `DEFAULT_DEV_MIDDLEWARE`). Older project-local copies are deprecated in favor of the package module.

---

## Compatibility

### Does this work with Django 5? Django 4?

The library targets Django 6.0+. Django 5 may work but isn't officially supported. Django 4 won't work — we depend on async ORM features added in later versions.

### Does this work with PyPy?

Untested. CPython 3.12+ is what we test against.

### Does this work with SQLite?

For development, yes. For production, prefer Postgres (or MySQL). SQLite's locking model becomes a bottleneck under any concurrent load.

---

## Where to learn more

If you can't find your question here:

- [Glossary](glossary.md) — definitions of every term in these docs.
- [Public API at a glance](public_api.md) — every importable symbol.
- [Architecture overview](architecture.md) — the full plumbing picture.
- [GitHub](https://github.com/web7ai/reflex-django) — issues and discussions.

---

**Next:** [Glossary →](glossary.md)
