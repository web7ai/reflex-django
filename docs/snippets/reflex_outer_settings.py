# reflex_outer only: Django admin/API run in a separate HTTP worker.
REFLEX_DJANGO_URL_ROUTING = "reflex_outer"
REFLEX_DJANGO_HTTP_PORT = 8001
REFLEX_DJANGO_DJANGO_PREFIX = (
    "/admin",
    "/api",
    "/static",
)
