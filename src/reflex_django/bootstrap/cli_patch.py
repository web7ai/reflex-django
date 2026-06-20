"""Early ``get_config`` patch when the Reflex CLI starts (``.pth`` hook)."""

try:
    from reflex_django.runtime.get_config_patch import install_plugin_get_config_patch

    install_plugin_get_config_patch()
except Exception:
    pass
