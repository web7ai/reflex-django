# Split dev: point Reflex at a separate Django server (prefer plugin config over settings).
#
# rxconfig.py:
# ReflexDjangoPlugin(config={
#     "settings_module": "config.settings",
#     "profile": "split_dev",
#     "proxy": {"server": "http://127.0.0.1:8000"},
# })
