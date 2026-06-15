> **Historical - pre-v4 only.** Current integration uses ReflexDjangoPlugin in xconfig.py. See [v4 migration](v4_plugin_only.md).

# RX settings rename

**Breaking change:** all `REFLEX_DJANGO_*` Django settings and environment variables are now `RX_*`. There are no deprecated aliases.

## Rule

For most settings, replace the prefix:

```text
REFLEX_DJANGO_<NAME>  ->  RX_<NAME>
```

Special cases:

| Old | New |
|:---|:---|
| `REFLEX_DJANGO_RX_CONFIG` | `RX_CONFIG` |
| `REFLEX_DJANGO_DJANGO_PREFIX` | `RX_DJANGO_PREFIX` |
| `RXDJANGO_PROXY_SERVER` | `RX_PROXY_SERVER` |
| `_reflex_django_bridge` on State classes | `_rx_bridge` |

Removed: `REFLEX_DJANGO_HTTP_UPSTREAM` (use `RX_PROXY_SERVER`).

Default event cache key prefix is now `rx:event:` (was `rxdj:event:`).

## Example

Before:

```python
REFLEX_DJANGO_RX_CONFIG = {
    "app_name": "shop",
    "backend_port": 8000,
}
REFLEX_DJANGO_AUTH = {"ENABLED": True}
RXDJANGO_PROXY_SERVER = "http://127.0.0.1:8000"
```

After:

```python
RX_CONFIG = {
    "app_name": "shop",
    "backend_port": 8000,
}
RX_AUTH = {"ENABLED": True}
RX_PROXY_SERVER = "http://127.0.0.1:8000"
```

## Environment variables

Update CI, Docker, and shell exports the same way:

```bash
export RX_CONFIG_APP_NAME=shop   # prefer settings.py for RX_CONFIG dict
export RX_DJANGO_PREFIX="/admin,/api"
export RX_DEBUG=0
export RX_PROXY_SERVER=http://127.0.0.1:8000
```

Runtime env vars set by `run_reflex` also use the `RX_*` prefix (`RX_FRONTEND_PORT`, `RX_BACKEND_PORT`, `RX_DEV_PROXY`, and so on). See [Settings reference](../settings.md).

## Per-State bridge override

```python
class FilterState(rx.State):
    _rx_bridge = "none"
```

## Canonical names in code

Library code reads setting names from `reflex_django.core.settings_names` (`SETTING_*` constants) and env names from `reflex_django.core.constants` (`ENV_*` constants).
