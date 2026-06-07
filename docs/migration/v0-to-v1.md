# Migrating from reflex-django 0.x to 1.0

## Routing modes

Only two modes are supported:

| Mode | Setting |
|------|---------|
| django_outer (default) | REFLEX_DJANGO_URL_ROUTING = django_outer |
| reflex_outer | REFLEX_DJANGO_URL_ROUTING = reflex_outer |

Removed: reflex_led, django_led, and aliases reflex, djangoled.

## ReflexDjangoPlugin / rxconfig.py

Removed: ReflexDjangoPlugin and rxconfig-first setup.

Use Django-first configuration:

1. Add REFLEX_DJANGO_RX_CONFIG to settings.py
2. Import views.py in urls.py for @page registration
3. Set config/asgi.py to from reflex_django.asgi_entry import application
4. Run python manage.py run_reflex

## App module path

reflex_django.django_led_app is deprecated. Use reflex_django.reflex_app.

## make_dispatcher

Removed: reflex_django.asgi.make_dispatcher.

Use reflex_django.asgi_entry.build_django_outer_application for production ASGI.