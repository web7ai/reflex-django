# Learn reflex-django

Follow these steps in order. Each page covers one integration piece. The default `integrated` profile turns all of them on.

## Checklist

1. [Integration](integration.md) - install, wire Django, run `reflex run`
2. [Embed](embed.md) - Django admin and API inside the Reflex backend
3. [Mount](mount.md) - URL prefixes and the SPA catch-all
4. [Proxy](proxy.md) - port 3000 dev wiring
5. [Bridge](bridge.md) - `request.user` in your handlers

Optional: [Tutorial](quickstart.md) - build a todo app with auth and the ORM.

## Profiles

Pick a preset in `rxconfig.py` instead of tuning each piece by hand.

| Profile | embed | mount | proxy | bridge | Good for |
|:---|:---|:---|:---|:---|:---|
| `integrated` | on | on | on | on | Most projects. Just `reflex run`. |
| `split_dev` | off | on | on | on | Django on `runserver`, Reflex separate |
| `reflex_only` | off | off | on | off | Reflex UI only, no Django HTTP |

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
})
```

You can override any piece after choosing a profile. See [Config reference](../advanced/config.md).

**Next:** [Integration](integration.md)
