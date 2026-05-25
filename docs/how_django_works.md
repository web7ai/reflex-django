# How Django works in 5 minutes

If Django is your day job, skim this and move on. If you've mostly used FastAPI, Flask, Node, or Rails — this is the version of Django that fits on one page, written for folks who want enough mental model to read the rest of the docs comfortably.

---

## The big idea

Django turns an HTTP request into an HTTP response. That's it. Everything else — the ORM, the admin, migrations, sessions — is a helper that lives inside that one cycle.

```text
Browser  ───── HTTP request ─────►  Django  ─── middleware ───►  view  ───► response  ───►  Browser
```

Three pieces are doing the work: **URLs**, **middleware**, and **views**.

---

## URLs

Django reads a Python file called `urls.py` and matches the incoming URL against a list of patterns:

```python
# config/urls.py
from django.urls import path
from shop import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("products/", views.product_list),
    path("products/<int:pk>/", views.product_detail),
]
```

If the URL is `/products/42/`, Django calls `views.product_detail(request, pk=42)`. Nothing fancy.

---

## Views

A view is a Python function (or class). It receives an `HttpRequest` and returns an `HttpResponse`:

```python
# shop/views.py
from django.shortcuts import render
from shop.models import Product

def product_detail(request, pk: int):
    product = Product.objects.get(pk=pk)
    return render(request, "product.html", {"product": product})
```

The view can talk to the database, read cookies, write to the session, render a template, or return JSON. It's just a Python function.

---

## Middleware — the layered onion

Before your view runs, the request walks through a list of **middleware** classes. Each one can read or modify the request, short-circuit with a response, or do nothing.

```python
# settings.py
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",   # fills request.session
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",              # CSRF protection
    "django.contrib.auth.middleware.AuthenticationMiddleware", # fills request.user
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

Think of it as an onion. The request goes *in* through each layer, hits the view, then the response comes *out* through the same layers in reverse.

By the time the view runs, the request has been decorated with goodies:

```python
def some_view(request):
    request.user          # the logged-in Django user (or AnonymousUser)
    request.session       # a dict-like session store backed by the DB or cache
    request.COOKIES       # the raw cookies the browser sent
    request.LANGUAGE_CODE # the user's locale, set by LocaleMiddleware
    request._messages     # one-shot flash messages
```

Custom middleware works exactly the same way. If you write a `MultiTenantMiddleware` that puts `request.tenant` on every request, every view downstream sees it.

> **Remember this:** middleware only runs on **HTTP** requests. It does **not** run on Reflex WebSocket events by default. That gap is exactly what `reflex-django` closes.

---

## Models and the ORM

Django ships with a database ORM. You declare your tables in Python:

```python
# shop/models.py
from django.db import models

class Product(models.Model):
    name  = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

Run `python manage.py makemigrations` and `python manage.py migrate`, and the table exists. Query it like this:

```python
Product.objects.create(name="Coffee", price="3.50")
Product.objects.filter(price__lt=5).order_by("name")
```

There's also an **async** version of every method (`acreate`, `aget`, `asave`, `adelete`). That matters a lot in `reflex-django` because Reflex event handlers are async. You'll use these constantly:

```python
await Product.objects.acreate(name="Coffee", price="3.50")
async for p in Product.objects.filter(price__lt=5):
    ...
```

---

## The admin

Register a model in `admin.py` and Django builds a full CRUD UI for it:

```python
# shop/admin.py
from django.contrib import admin
from shop.models import Product

admin.site.register(Product)
```

Visit `/admin/`, log in, and you can list, create, edit, and delete `Product` rows. It's one of Django's superpowers and `reflex-django` lets you keep using it untouched.

---

## Sessions and auth

Django has a built-in user model and session system. The flow is:

1. User submits `/admin/login/` with a username and password.
2. Django validates them with `django.contrib.auth.authenticate()`.
3. If valid, Django creates a row in the `django_session` table and sends back a `sessionid` cookie.
4. On every subsequent request, `SessionMiddleware` reads the cookie and loads the session; `AuthenticationMiddleware` reads the session and fills `request.user`.

You don't write this code. It just works once you have those two middlewares enabled.

> **This is the magic `reflex-django` extends to WebSockets.** Same `sessionid` cookie, same session row, same user — just inside a `@rx.event` handler now.

---

## Settings

`settings.py` is one Python file that configures everything: `INSTALLED_APPS`, `MIDDLEWARE`, `DATABASES`, `SECRET_KEY`, `ALLOWED_HOSTS`, static files, templates. `reflex-django` adds a small number of `REFLEX_DJANGO_*` keys to this file — that's where you tune the integration.

---

## The shape of a Django project

```text
myproject/
├── manage.py                # run admin commands: migrate, runserver, shell
├── config/
│   ├── settings.py          # INSTALLED_APPS, MIDDLEWARE, DATABASES, ...
│   ├── urls.py              # top-level URL patterns
│   └── asgi.py              # ASGI entry point (modern deploys)
└── shop/                    # a Django "app" — a feature module
    ├── models.py
    ├── views.py             # your views go here (and in reflex-django, your Reflex pages too)
    ├── admin.py
    └── migrations/
```

A *project* contains many *apps*. An app is just a folder of related code (models, views, admin, templates). `INSTALLED_APPS` in `settings.py` lists them.

---

## You now know enough

That's it. That's Django for the purposes of these docs. If you can read the four bullets below without confusion, you're good:

- Django matches a URL to a view function and runs it.
- Before the view runs, `settings.MIDDLEWARE` decorates the request with `user`, `session`, and friends.
- The ORM lets you query the database with both sync and async APIs.
- Sessions are server-side rows looked up by a `sessionid` cookie.

The next page does the same thing for Reflex.

---

**Next:** [How Reflex works in 5 minutes →](how_reflex_works.md)
