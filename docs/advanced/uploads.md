# Uploads and media

Reflex file uploads work with Django sessions. The bridge patches Reflex's `/_upload` handler so upload events carry cookies and routing metadata from the browser.

No extra wiring in `shop/shop.py`. Use Reflex upload components as documented in Reflex:

```python
rx.upload(id="file_upload", on_drop=MyState.handle_upload)
```

Handlers run with bridge context, so `self.request.user` and session data are available on `AppState`.

## Dev media files

Serve uploaded files in DEBUG:

```python
--8<-- "snippets/media_urls.py"
```

## Production

Do not serve `MEDIA_ROOT` through Django in production. Use object storage or nginx. Route `/_upload` and `/_event` to Reflex when using a split backend. See [Deploy](deployment.md).

**Next:** [CLI](cli.md)
