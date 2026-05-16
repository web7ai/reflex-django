# Authentication

Django **session authentication** from Reflex events, canned auth pages, and server-side authorization.

---

## Prerequisites

- [Django middleware to Reflex](django_middleware_to_reflex.md)  
- [State management](state_management.md)

---

## Server-side authorization

```python
from reflex_django import current_user, require_login_user
from reflex_django.auth import login_required, auser_has_perm

@rx.event
async def delete_item(self, item_id: int):
    user = require_login_user()
    if not await auser_has_perm(user, "shop.delete_product"):
        return rx.toast.error("Permission denied")
    ...
```

```python
@rx.event
@login_required
async def members_only_data(self):
    ...
```

> **Warning:** `@login_required` on **pages** redirects in the UI only. Protect **event handlers** that return private data, or use `require_login_user()`.

---

## `DjangoUserState` (UI snapshot)

Sync display fields to the client—not for authorization:

```python
from reflex_django import DjangoUserState

class MyState(DjangoUserState):
    @rx.event
    async def on_load(self):
        await self.sync_from_django()
```

Use `current_user()` for permission and ownership checks.

---

## Session cookie sync after login

Reflex events do not run `SessionMiddleware`; `alogin` may not set the browser cookie. **`session_auth_mixin`** and canned auth call `session_cookie_set_js` via `rx.call_script` after `await request.session.asave()`.

Helpers: `session_cookie_set_js`, `session_cookie_clear_js` from `reflex_django`.

---

## Declarative session login (`session_auth_mixin`)

```python
from reflex_django import DjangoUserState
from reflex_django.mixins import SessionAuthConfig, session_auth_mixin

cfg = SessionAuthConfig(
    post_login_redirect="/",
    post_logout_redirect="/login",
)

class LoginState(session_auth_mixin(cfg, base=DjangoUserState)):
    pass
```

Requires **event bridge** enabled. Uses Django async auth (`aauthenticate`, `alogin`, `alogout`).

---

## Canned auth pages

**Settings** (`backend/settings.py`):

```python
REFLEX_DJANGO_AUTH = {
    "SIGNUP_ENABLED": True,
    "PASSWORD_RESET_ENABLED": True,
    "LOGIN_URL": "/login",
    "SIGNUP_URL": "/register",
    "LOGIN_REDIRECT_URL": "/",
    "LOGIN_FIELDS": ["username"],
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@localhost"
```

**App module:**

```python
from reflex_django.auth import add_auth_pages, login_required

app = rx.App()
add_auth_pages(app)

@rx.page()
@login_required
def dashboard():
    return rx.heading("Members only")
```

Pages: `LoginPage`, `RegisterPage`, `PasswordResetPage`, `PasswordResetConfirmPage`. Customize via `BaseAuthPage` hooks or `REFLEX_DJANGO_AUTH["MESSAGES"]`.

`get_auth_settings()` resolves `AuthSettings` dataclass from Django settings.

---

## `REFLEX_DJANGO_AUTH` keys (summary)

| Key | Purpose |
|-----|---------|
| `ENABLED` | Master switch |
| `SIGNUP_ENABLED` / `PASSWORD_RESET_ENABLED` | Feature flags |
| `LOGIN_URL`, `SIGNUP_URL`, password reset URLs | Routes |
| `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`, … | Redirects |
| `LOGIN_FIELDS` | `username`, `email`, or both |
| `EMAIL_REQUIRED`, `PASSWORD_MIN_LENGTH`, `USERNAME_MIN_LENGTH` | Validation |
| `MESSAGES` | UI copy overrides |

Legacy: `REFLEX_DJANGO_LOGIN_URL` when `LOGIN_URL` omitted from dict.

---

## Security notes

- Password reset uses Django’s token generator; use stable **`SECRET_KEY`** in production.  
- Registration creates **active** users; set `SIGNUP_ENABLED=False` if only admins create accounts.  
- Never trust client state for mutations.

---

## Advanced usage

- Custom `state_cls` on `LoginPage` subclass.  
- `aauthenticate_login_fields` for configurable login identifiers (`auth/login_fields.py`).

---

## Common mistakes

- Login succeeds but next event is anonymous — cookie sync / event bridge.  
- Page-level `@login_required` only without event protection.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Redirect loop | `LOGIN_URL` vs actual route |
| Reset email missing | `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL` |

---

## See also

- [Forms and validation](forms_and_validation.md)  
- [Best practices](best_practices.md)

---

**Navigation:** [← Forms and validation](forms_and_validation.md) | [Next: API integration →](api_integration.md)
