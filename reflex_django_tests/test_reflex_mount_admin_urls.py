"""URLconf for admin + reflex_mount slash handling tests."""

from reflex_django.django.urls import admin_urlpatterns, reflex_mount

urlpatterns = [
    *admin_urlpatterns("/admin"),
]
urlpatterns += [
    reflex_mount(django_prefix=("/admin",)),
]
