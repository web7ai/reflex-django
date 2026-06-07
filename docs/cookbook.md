---
level: intermediate
tags: [recipes, patterns]
---

# Cookbook

**What you will learn:** Copy-paste recipes for common reflex-django tasks: login gates, uploads, DRF beside the SPA, and branded auth pages.

**When you need this:**

- You know the feature you want and prefer a short recipe over a full guide.
- You are wiring auth, media, or REST alongside Reflex pages.

Each card links to the long-form doc when you need more context.

---

## Login gate (page and handler)

**Goal:** Only signed-in users see a page or run a handler. Same session as Django admin.

**Ingredients:**

- `AppState` subclass
- `@page(..., login_required=True)` or `@login_required` on handlers
- `SessionMiddleware` and `AuthenticationMiddleware` in `MIDDLEWARE`

**Steps:**

1. Subclass `AppState` in your app's `views.py`.
2. Gate the whole page with `@page`:

```python
from reflex_django.pages.decorators import page
from reflex_django.states import AppState
import reflex as rx


class AccountState(AppState):
    pass


@page(route="/account", title="Account", login_required=True)
def account() -> rx.Component:
    return rx.vstack(
        rx.heading("Your account"),
        rx.text(AccountState.username),
    )
```

3. For sensitive handlers, add `@login_required` even when the page is public:

```python
from reflex_django.auth import login_required


class CartState(AppState):
    @rx.event
    @login_required
    async def checkout(self):
        ...
```

**Check:** Log in at `/login` or `/admin/`, then open the page from `:3000` in default dev. Handlers must use `self.request.user` for authorization, not snapshot vars alone.

**Deep dive:** [Login and sessions](authentication.md)

---

## File upload with Django storage

**Goal:** User picks a file in the browser, you save it with `default_storage`, and serve it from `/media/`.

**Ingredients:**

- `rx.upload` and `rx.upload_files`
- Handler on `AppState` with `@login_required` (recommended)
- `MEDIA_URL` / `MEDIA_ROOT` configured

**Steps:**

1. Build the upload UI:

```python
@page(route="/upload")
def upload_page() -> rx.Component:
    return rx.vstack(
        rx.upload(rx.button("Choose file"), id="doc_upload", max_files=1),
        rx.button(
            "Upload",
            on_click=UploadState.handle_upload(rx.upload_files("doc_upload")),
        ),
        rx.cond(UploadState.file_url != "", rx.link("Open file", href=UploadState.file_url)),
    )
```

2. Save in the handler:

```python
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class UploadState(AppState):
    file_url: str = ""

    @rx.event
    @login_required
    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        upload = files[0]
        content = await upload.read()
        path = default_storage.save(
            f"uploads/{self.request.user.id}_{upload.filename}",
            ContentFile(content),
        )
        self.file_url = default_storage.url(path)
```

3. Configure [media serving](media_files.md) so `file_url` loads in the browser.

**Check:** Upload while logged in. Anonymous uploads will not see the expected `self.request.user`.

**Deep dive:** [File uploads](file_uploads.md)

---

## DRF alongside the SPA

**Goal:** Mobile clients or scripts call REST on `/api/`, while the Reflex SPA uses `@rx.event` on the same origin and session.

**Ingredients:**

- Normal Django `urlpatterns` with `path("api/", ...)`
- DRF viewsets or API views (optional package)
- `REFLEX_DJANGO_AUTO_MOUNT=True` so the SPA catch-all stays last

**Steps:**

1. Register API routes **before** the auto-mounted catch-all:

```python
# config/urls.py
from django.contrib import admin
from django.urls import include, path

import shop.views  # loads @page modules

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("shop.api_urls")),
]
# SPA catch-all: automatic when REFLEX_DJANGO_AUTO_MOUNT=True
```

2. Add a DRF viewset with session auth:

```python
# shop/api.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)
```

3. From a Reflex page, call the API with the browser session:

```python
@rx.event
async def load_orders(self):
    resp = await self.request.aGET("/api/orders/")
    ...
```

**Check:** `GET /api/orders/` works on `:8000` when logged in. Same cookie works from the SPA on `:3000` because Vite proxies `/api` to the backend.

**Deep dive:** [HTTP APIs alongside Reflex](api_integration.md)

---

## Branded auth pages

**Goal:** Login, register, and password reset match your product name, logo, and colors without rewriting auth views.

**Ingredients:**

- `REFLEX_DJANGO_AUTH` in `settings.py`
- Optional `PAGE_CLASSES` overrides for layout

**Steps:**

1. Enable and brand auth in settings:

```python
REFLEX_DJANGO_AUTH = {
    "ENABLED": True,
    "SITE_NAME": "Acme Shop",
    "LOGIN_URL": "/login",
    "LOGO_URL": "/static/brand/logo.svg",
    "MESSAGES": {
        "login_heading": "Sign in to Acme Shop",
        "register_heading": "Create your account",
    },
}
```

2. Customize layout classes when you need tighter control:

```python
REFLEX_DJANGO_AUTH = {
    "ENABLED": True,
    "PAGE_CLASSES": {
        "login": "auth-page auth-page--login",
        "register": "auth-page auth-page--register",
    },
}
```

3. Ship matching CSS in your static files or Reflex theme plugin.

**Check:** Open `/login` from `:3000`. After login, Reflex events should see the same user as `/admin/`.

**Deep dive:** [Login and sessions (make it yours)](authentication.md#make-it-yours)

---

## What just happened?

You saw four focused recipes: gating with Django sessions, saving uploads, colocating DRF with the SPA, and branding built-in auth.

**Next up:** [Troubleshooting](troubleshooting.md) when something breaks in dev.
