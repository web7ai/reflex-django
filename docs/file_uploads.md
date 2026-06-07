# File uploads (`rx.upload`)

Reflex file uploads use **`/_upload`** — separate from Django **`/media/`** (served files after you save them). reflex-django wires session cookies into upload handler events.

---

## Two paths, two jobs

| Path | Purpose |
|:---|:---|
| **`/_upload`** | Reflex receives raw upload bytes (multipart POST). |
| **`/media/...`** | Django or nginx serves stored files after your handler saves them. |

---

## How auth works

reflex-django's `upload_patch.py` merges cookies from the Starlette upload request into handler events so [DjangoEventBridge](websocket_event_pipeline.md) can run session and auth middleware. Log in first; dev must trust both `:3000` and `:8000` for CSRF/session.

---

## Basic pattern

```python
import reflex as rx
from reflex_django.pages.decorators import page
from reflex_django.states import AppState
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class UploadState(AppState):
    image_url: str = ""

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
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
        rx.button("Upload", on_click=UploadState.handle_upload(rx.upload_files("avatar_upload"))),
        rx.cond(UploadState.image_url != "", rx.image(src=UploadState.image_url)),
    )
```

Configure [media serving](media_files.md) so `profile.avatar.url` loads in the browser.

---

## Production limits

Set `client_max_body_size` on your reverse proxy (see [Deployment](deployment.md)).

---

## Related

- [Media files](media_files.md)
- [Forms & validation](forms_and_validation.md)
- [WebSocket event pipeline](websocket_event_pipeline.md)