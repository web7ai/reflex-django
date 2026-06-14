# Best practices

**What you will learn:** Sensible defaults for layout, state, security, and dev workflow so you avoid the mistakes most teams hit in week one.

**When you need this:**

- You are starting a new reflex-django app and want a short checklist.
- You are reviewing code and want shared team conventions.

These are defaults that work well for most projects, not hard rules.

---

## Project layout

**Put pages in `{app}/views.py`.** Keeping pages next to their models is the biggest readability win.

**Use one page registry hub.** Import every `@page` module from `{app_name}/views.py` (or list them in `RX_PAGE_PACKAGES`). Keep `{app_name}/{app_name}.py` as a thin entry stub. See [App entry module and page registration](../guides/app_entry_and_pages.md).

**One settings module with env overrides.** Use environment variables for secrets and host-specific values.

**Group state classes with the page that uses them.**

---

## State

**Default to `AppState`, not `rx.State`.** You will likely need `self.request.user` soon.

**Use plain `rx.State` only for UI-local concerns** (modals, filters, theme).

**Never authorize from the reactive snapshot.** Check `self.request.user` in handlers. Snapshots are for UI only.

**Store dicts in state fields, not model instances.** JSON serialization will fail on Django models.

**Paginate large lists.** Reactive vars ship to the browser.

---

## Async and ORM

**Use `async def` event handlers.**

**Use the async ORM** (`acreate`, `aget`, `asave`, `adelete`, `async for`).

**Wrap sync-only libraries in `sync_to_async`.**

**Slice querysets:** `qs[:50]`, not `list(qs)`.

---

## URLs and routing

**Import page modules in `urls.py`.** `@page` runs at import time.

**Let prefix auto-detection work.** Override with `reflex_mount(django_prefix=...)` only when needed.

**Do not add Django `path()` entries for SPA pages.** Routes live in `@page(route=...)`.

**Do not register routes under reserved Reflex prefixes** (`/_event`, `/_upload`, `/_health`, `/ping`).

---

## Security

**Re-check permissions on every mutation.** Decorators help; ownership filters in handlers are the boundary.

**Validate on the server** even when the UI validates for UX.

**Production:** real `SECRET_KEY`, `ALLOWED_HOSTS`, secure cookies over HTTPS.

!!! warning "Snapshot vs live user"
    `self.is_authenticated` is UI-safe. `self.request.user.is_authenticated` is what you use for authorization.

---

## Forms, CRUD, middleware

**Validation order:** `clean_<field>`, then `validate_state`, then `run_model_validation`.

**Start with `ModelState` for standard CRUD.** Drop to plain `AppState` for wizards and multi-model flows.

**Put `AsyncStreamingMiddleware` last** in `MIDDLEWARE`.

**Custom middleware runs on Reflex events by default.** Skip expensive pieces via `RX_EVENT_MIDDLEWARE_SKIP`.

---

## Performance and CI

**Paginate lists. Prefetch aggressively.** N+1 is the most common slowdown.

**Tune the event bridge from `settings.py`** for high-frequency UI: `RX_EVENT_BRIDGE_MODE = "smart"`, `_rx_bridge` on hot State classes, `RX_PERFORMANCE_PRESET = "lean"`. See [Scaling and performance](scaling.md).

**Pre-build the SPA in CI**, not at container boot.

**Run `migrate` as a deploy step**, not from every worker at startup.

**Health-check `/_health`**, not `/`.

---

## Dev workflow

**`run_reflex`** when iterating on Reflex pages (Vite HMR on `:3000`).

**`run_reflex --from-build --skip-rebuild`** when you only touch Django models or admin.

**`run_reflex --env prod --skip-rebuild`** to validate the production bundle locally before ship (browse `:8000`). See [Deployment](deployment.md).

**Keep `.web/` and `.reflex/` in `.gitignore`.**

---

## Testing and docs

**Test handlers with `begin_event_request`.** Test ownership boundaries explicitly.

**Document why, not what.** Link to these docs instead of duplicating tutorials in README.

---

## When in doubt

- Standard CRUD? → `ModelState`.
- Weird workflow? → plain `AppState`.
- SPA button click? → Reflex event. External client? → HTTP endpoint.

---

## What just happened?

You have a compact set of defaults for structure, security, async ORM usage, and deploy hygiene.

## Next up

[Best practices](best_practices.md)