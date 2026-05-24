"""Stub ``rxconfig`` for reflex-django Django-first mode.

Reflex reads this file for project layout checks. Live settings come from Django
(``reflex_mount(app_name=..., rx_config=...)``) and are merged at
runtime by reflex-django. You may edit or delete this file if you maintain your
own ``rxconfig.py`` instead.
"""
import reflex as rx

config = rx.Config(
    app_name='reflex_django',
    app_module_import='reflex_django.django_led_app',
)
