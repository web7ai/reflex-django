---
level: intermediate
tags: [uploads, media]
---

# File uploads

**What you'll learn:** How Reflex `rx.upload` sends files through `/_upload`, how reflex-django attaches session cookies, and how to save bytes with Django storage.

**When you need this:**

- Users pick images or documents in the browser and you store them on the server.
- You need uploads to respect the same login session as your Reflex handlers.

Reflex uploads and Django media are two different paths. Upload receives bytes; media serves stored files after you save them.

---

## Two paths, two jobs

| Path | Purpose |
|:---|:---|
| `/_upload` | Reflex receives multipart upload bytes. |
| `/media/...` | Django (or your reverse proxy) serves files after your handler saves them. |

---

## How auth works

reflex-django patches the upload handler so cookies from the Starlette upload request flow into the [event bridge](../internals/event_pipeline.md). Users should be logged in before uploading. In dev, trust both `:3000` and `:8000` for CSRF and session cookies (see [Local development](../getting-started/local_development.md)).

!!! warning "Log in first"
    Anonymous uploads will not have `self.request.user` scoped the way you expect. Gate the upload button with auth checks in the handler.

---

## Basic pattern

```python
import reflex as rx
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from reflex_django.pages.decorators import page
from reflex_django.states import AppState


class UploadState(AppState):
    image_url: str = ""

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files or not self.request.user.is_authenticated:
            return
        upload = files[0]
        from shop.models import Profile

        profile, _ = await Profile.objects.aget_or_create(user=self.request.user)
        content = await upload.read()
        path = f"avatars/{self.request.user.id}_{upload.filename}"
        saved = default_storage.save(path, ContentFile(content))
        profile.avatar = saved
        await profile.asave()
        self.image_url = profile.avatar.url


@page(route="/upload-demo")
def upload_demo() -> rx.Component:
    return rx.vstack(
        rx.upload(rx.button("Select image"), id="avatar_upload", max_files=1),
        rx.button(
            "Upload",
            on_click=UploadState.handle_upload(rx.upload_files("avatar_upload")),
        ),
        rx.cond(UploadState.image_url != "", rx.image(src=UploadState.image_url)),
    )
```

Configure [media serving](media.md) so `profile.avatar.url` loads in the browser.

---

## Production limits

Set `client_max_body_size` on your reverse proxy. See [Deployment](../operations/deployment.md) for nginx and similar examples.

---

## What just happened?

You wired `rx.upload` to an `AppState` handler, saved bytes with Django storage, and exposed the public URL through your media config.

**Next up:** [Model serializers →](serializers.md)