# Best practices

The patterns below are things you'll figure out yourself after a week or two. Reading them now saves time. None of these are rules — they're defaults that work well for most projects.

---

## Project layout

**Put pages in `{app}/views.py`.** Don't create a separate `frontend/` folder unless you have a real reason. Keeping pages next to their models is the single biggest readability win.

**One `settings.py` with environment-driven overrides.** Don't ship five settings modules. Use environment variables for the things that change between environments (DB, SECRET_KEY, ALLOWED_HOSTS).

**Group related state classes near the page that uses them.** If `CartState` is only used by `cart_page`, they belong in the same file.

---

## State

**Default to `AppState`, not `rx.State`.** Even if you don't need `self.request.user` today, you probably will tomorrow. The overhead is one extra context binding per event — negligible.

**Use plain `rx.State` only for UI-local concerns.** Filter bars, modals, theme toggles. Things that genuinely don't care about Django.

**Never base authorization on the reactive snapshot.** `self.is_authenticated`, `self.username`, etc. are shipped to the browser. Always check `self.request.user` in handlers.

**Don't store model instances in state fields.** Always convert to dicts. JSON serialization will fail on `Product` and other Django model instances.

**Keep state fields small.** Lists of 10,000 dicts ship 10,000 dicts to the browser. Paginate.

---

## Async / sync

**Always `async def` your event handlers.** Even if the body is simple. Reflex schedules them on the event loop either way; consistent style avoids surprises later.

**Use the async ORM (`acreate`, `aget`, `asave`, `adelete`, `async for`).** A sync ORM call in an event handler stalls every connection. The methods all exist; use them.

**Wrap sync-only libraries in `sync_to_async`.** Some Django utilities (transactions, `Site.objects.get_current()`) are sync. Wrap them once, await the wrapper.

**Slice querysets.** `qs[:50]`, not `list(qs)`. A `LIMIT` in SQL costs almost nothing; loading everything costs a lot.

---

## URLs and routing

**Django routes go above `reflex_mount()`.** Always.

**Let prefix auto-detection do its job.** If you list routes in `urlpatterns` and append `reflex_mount()` last, reflex-django infers `django_prefix` for you. Override manually only when you use `re_path()` or have an unusual layout — drift between routes and an explicit prefix list is still the #1 cause of routing 404s.

**Don't add Django `path()` entries for SPA pages.** SPA routes live in `@page(route=...)`. Adding a Django path shadows them.

**Don't add Django routes under reserved Reflex prefixes** (`/_event`, `/_upload`, `/_health`, `/ping`).

**Use `Meta.ordering` on models.** Stable ordering everywhere — admin, API, Reflex lists — without thinking.

---

## Forms and validation

**Three stages, in order:** `clean_<field>` for per-field cleaning, `validate_state` for cross-field rules, `run_model_validation = True` to lean on Django's own validators.

**Set `structured_errors = True`** if you want per-field error messages. Bind them to `<list_var>_field_errors[<field>]` in the UI.

**Always show the global error too.** A `rx.cond(MyState.error != "", rx.callout(...))` at the top of the form catches edge cases the per-field display misses.

**Reset form on success.** `Meta.reset_after_save = True` + `key=form_reset_key` on the `<rx.form>`.

---

## ORM patterns

**Scope queries by user inside the handler.** `Model.objects.filter(owner=self.request.user)` is your security boundary.

**Scope edits by user too.** `await Model.objects.aget(pk=id, owner=self.request.user)` — never `aget(pk=id)` alone. If the user tampers with an ID, `aget` raises `DoesNotExist` instead of returning a foreign row.

**Use `select_related` / `prefetch_related` aggressively.** N+1 is the most common performance bug in any Django app.

**Use `only()`** on wide tables when you only need a few fields.

**Use `ModelState`'s `Meta.queryset_select_related`/`Meta.queryset_prefetch`** to apply joins consistently across all generated CRUD operations.

---

## CRUD style

**Start with `ModelState`.** It's shorter and just as capable. Reach for `ModelCRUDView` only when you specifically want explicit serializers or named handlers.

**Drop to plain `AppState` for weird workflows.** Wizards, multi-model forms, computed lists — the manual style is fine. Don't twist `ModelState` to fit.

**Use `UserScopedMixin` instead of manually overriding three hooks.** If `owner_field` covers your case, the mixin is one line; the manual override is six.

---

## Middleware

**Custom middleware works on Reflex events too — by default.** You don't need to do anything special.

**Skip `CsrfViewMiddleware` and `AsyncStreamingMiddleware` on events.** They're already in the default skip list. Leave it alone.

**Put `AsyncStreamingMiddleware` last** in `MIDDLEWARE`. Always.

**Custom middleware that redirects becomes `rx.redirect(...)`** on events. Useful for `LoginRequiredMiddleware` patterns.

---

## Security

**Never trust the snapshot.** `self.is_authenticated`, `self.username` — UI only.

**Always re-check on the server.** Permissions, ownership, "is this the right user?" — every mutation. The decorators (`@login_required`, `@permission_required`) help, but they're aids, not replacements for thinking.

**Validate on the server.** Even if you also validate in the UI for UX. The UI can be bypassed.

**Don't reuse the dev `SECRET_KEY`** in production. `os.environ["DJANGO_SECRET_KEY"]` is the answer.

**Set `ALLOWED_HOSTS`** in production. `["*"]` is a footgun.

**Set `SESSION_COOKIE_SECURE = True`** and `CSRF_COOKIE_SECURE = True` once you have HTTPS.

---

## Performance

**Paginate everything.** Lists, tables, even "small" tables.

**Cache expensive context-processor calls.** If a processor hits the database, memoize the result per-request.

**Use a real database in dev.** Postgres > SQLite for catching missing indexes early.

**Profile before optimizing.** Reflex's docs have a profiling section. Most "slow" pages are slow because of one N+1 query, not the framework.

**Pre-build the SPA in CI.** Don't run `export_reflex` on the production server every time the app boots.

---

## Logging

**Log at module level.** Use the standard `logging.getLogger(__name__)`. Pipe everything to stdout/stderr in production; let your platform aggregate.

**Don't `print()` in production.** It works, but it's not structured. Use logging with a JSON formatter.

**Log enough context.** `logger.info("checkout completed", extra={"user_id": user.id, "order_id": order.id})` is far more debuggable than `logger.info("done")`.

---

## Testing

**Test the handler, not the framework.** Use `begin_event_request` / `end_event_request` to set up the context, then call the handler directly. Don't try to open a real WebSocket for unit tests.

**Test the ownership boundary.** Write a test where one user tries to edit another user's row. The handler should refuse.

**Run migrations in CI** so schema drift gets caught.

**Use `@pytest.mark.django_db`** liberally. The cost is small compared to the bugs it catches.

---

## Dev workflow

**`run_reflex`** (the default) when you're iterating on Reflex pages — Vite hot-reloads the frontend on every edit; restart the command to pick up state/backend edits.

**`run_reflex --from-build --skip-rebuild`** when you're only editing Django models, migrations, or admin and want the backend to auto-restart without re-exporting the SPA.

**Keep the `.web/` and `.reflex/` directories in `.gitignore`.** Both are caches; nothing in them is yours.

**Don't delete `.web/` casually.** Rebuilding is fast but not instant. Delete it only when you have a *real* reason (corrupted bundle, version upgrade).

---

## i18n

**`gettext_lazy` for component literals.** `gettext` for handler output.

**Always `compilemessages` after editing `.po` files.** `makemessages` alone doesn't update what's loaded at runtime.

**Test RTL.** Set the cookie and make sure your layout doesn't break.

---

## CI/CD

**Build the SPA in the image, not at boot.** Faster cold starts, more predictable behavior.

**Run `migrate` as a release/deploy step**, not as part of the boot sequence. Multiple workers running migrate at the same time is a classic foot-gun.

**Health-check `/_health`**, not `/`. It doesn't touch the DB.

---

## Documentation hygiene

**Document the *why*, not the *what*.** Why this state class has a custom `get_queryset` matters; *that* it has one is obvious from the code.

**Keep your `README.md` to one screen.** Link out to docs. Don't duplicate.

**Update the docs when you change behavior.** Stale docs are worse than no docs.

---

## When in doubt

- "Will this scale?" → Probably yes for the next year. Ship it. Profile later.
- "Should I add a new state class?" → If it has its own data, yes. If it shares everything with an existing state, no.
- "Should I write this as a Reflex event or an HTTP endpoint?" → Who's calling it? SPA → event. Anything else → HTTP.
- "Should I use `ModelState` or write it manually?" → If it's standard CRUD, `ModelState`. If it's weird, manual.

---

**Next:** [Migrating from older versions →](migration_django_outer.md)
