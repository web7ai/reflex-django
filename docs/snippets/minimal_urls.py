from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
# SPA catch-all: automatic when mount.enabled is True (default in plugin)
