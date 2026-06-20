# Embed

Embed runs Django HTTP inside the Reflex backend during dev. Admin at `/admin/` and your API work without a separate `runserver`.

## Default

With `profile: "integrated"`, embed is on. One terminal, one `reflex run`.

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
})
```

## Turn embed off

Use this when you want Django on `runserver` in a second terminal. Set `profile: "split_dev"` or:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "embed": {"enabled": False},
    "proxy": {"server": "http://127.0.0.1:8000"},
})
```

Then run `python manage.py runserver` and `reflex run` together. See [Proxy](proxy.md).

Embed is a dev convenience. Production uses your own reverse proxy, not this flag.

**Next:** [Mount](mount.md)
