# config/urls.py — language switcher endpoint
from django.contrib import admin
from django.urls import path
from django.views.i18n import set_language

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/setlang/", set_language, name="set_language"),
]
