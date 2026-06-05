# Branding auth without subclasses

Configure canned login, register, and password-reset pages from `REFLEX_DJANGO_AUTH` in `settings.py`.

## Text and logo only

```python
REFLEX_DJANGO_AUTH = {
    "BRAND_TEXT": "My App",
    "BRAND_ICON_SRC": "/static/logo.png",
    "MESSAGES": {
        "login_heading": "Sign in to My App",
    },
}
```

`BRAND_TEXT` or `BRAND_ICON_SRC` replaces the default icon above form headings on login and register pages.

## Custom layout (shell, card, gradients)

Subclass `LoginPage` / `RegisterPage` / etc. and point to them with `PAGE_CLASSES`:

```python
REFLEX_DJANGO_AUTH = {
    "PAGE_CLASSES": {
        "login": "myapp.auth.BrandedLoginPage",
        "register": "myapp.auth.BrandedRegisterPage",
        "password_reset": "myapp.auth.BrandedPasswordResetPage",
        "password_reset_confirm": "myapp.auth.BrandedPasswordResetConfirmPage",
    },
}
```

Override `shell()`, `card()`, and `heading()` on a shared mixin; keep form logic in reflex-django base classes.

## Auto-registration

When `ENABLED` is true (default), auth pages register during Reflex page preparation. No `add_auth_pages()` call in `views.py` is required.
