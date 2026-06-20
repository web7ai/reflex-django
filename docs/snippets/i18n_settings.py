# settings.py — i18n (add to your existing settings)
USE_I18N = True
USE_L10N = True

LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("de", "Deutsch"),
    ("ar", "Arabic"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

# LocaleMiddleware after SessionMiddleware, before CommonMiddleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    # ... auth, messages, clickjacking ...
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
]
