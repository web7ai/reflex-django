import shop.views  # noqa: F401 - register @page decorators at import time

from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
# SPA catch-all: automatic when RX_AUTO_MOUNT=True (default)
