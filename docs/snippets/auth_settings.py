REFLEX_DJANGO_AUTH = {
    "LOGIN_URL": "/sign-in",
    "SIGNUP_URL": "/sign-up",
    "LOGIN_REDIRECT_URL": "/dashboard",
    "LOGOUT_REDIRECT_URL": "/",
    "LOGIN_FIELDS": ["email"],
    "PASSWORD_MIN_LENGTH": 10,
    "SIGNUP_ENABLED": True,
    "PASSWORD_RESET_ENABLED": True,
}
