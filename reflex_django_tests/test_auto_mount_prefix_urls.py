"""URLconf with admin + api routes for django_prefix auto-detection tests."""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", admin.site.urls),
]
