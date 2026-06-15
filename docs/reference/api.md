# Public API

## Package imports

```python
from reflex_django import configure_django, create_app, django_cli, build_django_asgi
from reflex_django.plugins import ReflexDjangoPlugin
from reflex_django.pages.decorators import page
from reflex_django.states import AppState
```

Your Reflex `app` lives in `{app_name}/{app_name}.py` (`app = rx.App()`), not on the package root.

## CLI

| Command | Purpose |
|:---|:---|
| `reflex run` | Dev server |
| `reflex export` | Production build |
| `reflex django <args>` | Django management commands |

See [CLI reference](../operations/cli.md).

## Plugin

`ReflexDjangoPlugin(config={...})` with keys: `settings_module`, `django_prefix`, `mount_prefix`, `auto_mount`.
