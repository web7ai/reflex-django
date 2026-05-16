# Best practices

Production-oriented patterns for reflex-django applications.

---

## Architecture

- **Models → serializers → states → pages** — keep domain logic in Django apps; Reflex layer orchestrates UI.  
- **One settings module** for `reflex run`, `reflex django migrate`, and deploy env.  
- **Align prefixes** between `ReflexDjangoPlugin` and `ROOT_URLCONF`.

---

## Security

1. Authorize in **event handlers** with `self.user` / `current_user()`, `require_login_user()`, `await self.has_perm(...)`, or `auser_has_perm`.  
2. Use `@login_required` and `@permission_required` on events that return or change private data.  
3. Never trust snapshot fields (`is_authenticated`, `username`, …) alone for permissions—they are for UI.  
4. Scope querysets with `self.user` / `UserScopedMixin` on `ModelState[M]` or `AppState` + `ModelCRUDView` ([Reactive ModelState](reactive_model_state.md)).  
5. After `login()` / `logout()`, sync the browser session cookie when users full-page navigate ([Authentication](authentication.md)).  
6. Keep `SECRET_KEY` stable; disable `SIGNUP_ENABLED` if registrations are admin-only.

Detail: [Authentication](authentication.md).

---

## Imports and startup

- Prefer `from reflex_django import …` **after** `rxconfig` loads in normal Reflex startup.  
- `ModelState` (preferred): `from reflex_django.state import ModelState`.  
- `ModelCRUDView` (explicit serializer): `from reflex_django.state import ModelCRUDView`.  
- `session_auth_mixin`: `from reflex_django.mixins import session_auth_mixin`.  
- Avoid circular imports: do not import models at module level from paths that load before `configure_django()`.

PEP 562 lazy exports defer ORM-heavy submodules until first access.

---

## Async handlers

Use `async def` for handlers calling Django async ORM (`acreate`, `.adata()`, `aget_user` path in bridge).

---

## JSON state

Only JSON-serializable values on `rx.State` fields synced to the client. Processors must not return secrets, ORM objects, or `HttpRequest`.

---

## Performance

- `queryset_select_related` / `queryset_prefetch` on `Meta` (ModelState or ModelCRUDView).  
- Narrow `fields` on `ModelState` or serializer `Meta.fields`.  
- Use `Meta.paginate_by` on ModelState for built-in pagination vars and handlers.  
- `load_context_processors=False` when unused.

---

## Extensibility

- Prefer hooks (`filter_queryset`, `validate_state`) over copying generated handlers.  
- Override generated event names in class body when necessary.  
- Use composed mixins for partial CRUD instead of forking the framework.

---

## Production readiness checklist

- [ ] Custom `settings.py`, not `REFLEX_DJANGO_AUTO_SETTINGS`  
- [ ] `DEBUG=False`, explicit `ALLOWED_HOSTS`  
- [ ] Migrations applied  
- [ ] `collectstatic` run  
- [ ] Event bridge enabled if using session auth  
- [ ] Server-side checks on all mutating events  

---

## Common mistakes

See [FAQ](faq.md) for a consolidated list.

---

## See also

- [Architecture](architecture.md)  
- [Deployment](deployment.md)

---

**Navigation:** [← Testing](testing.md) | [Next: FAQ →](faq.md)
