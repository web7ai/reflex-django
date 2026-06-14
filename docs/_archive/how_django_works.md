---
level: beginner
tags: [django, onboarding]
---

# How Django works in 5 minutes

**What you'll learn:** Enough Django vocabulary (URLs, middleware, views, ORM, sessions) to read the rest of these docs comfortably.

**When you need this:**

- You mostly use FastAPI, Flask, Node, or Rails and Django is new to you.
- You want a one-page refresher before reading about AppState and the event bridge.

---

If Django is your day job, skim this and move on. Everyone else: this is Django compressed to one page.

---

## The big idea

Django turns an HTTP request into an HTTP response. Everything else (the ORM, the admin, migrations, sessions) is a helper inside that cycle.

```text
Browser  ───── HTTP request ─────►  Django  ─── middleware ───►  view  ───► response  ───►  Browser
```

Three pieces do the work: **URLs**, **middleware**, and **views**.

---

## URLs

Django reads `urls.py` and matches the incoming URL against a list of patterns:

```python
--8<-- "snippets/minimal_urls.py"
```

Add more `path()` entries above the catch-all for your own views. If the URL is `/admin/`, Django calls the admin site. Nothing fancy.

---

## Views

A view is a Python function (or class). It receives an `HttpRequest` and returns an `HttpResponse`:

```python
# shop/views.py (classic Django view, not a Reflex page)
from django.shortcuts import render
from shop.models import Product

def product_detail(request, pk: int):
    product = Product.objects.get(pk=pk)
    return render(request, "product.html", {"product": product})
```

In reflex-django, the same `views.py` file also holds your Reflex `@page` functions. Same Django app, two kinds of view.

---

## Middleware

Before your view runs, the request walks through **middleware**. Each layer can read or modify the request, short-circuit with a response, or pass through.

```python
# settings.py (excerpt)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",   # fills request.session
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",              # CSRF protection
    "django.contrib.auth.middleware.AuthenticationMiddleware", # fills request.user
    "django.contrib.messages.middleware.MessageMiddleware",
]
```

Think of it as an onion. The request goes *in* through each layer, hits the view, then the response comes *out* in reverse.

By the time the view runs:

```python
def some_view(request):
    request.user          # logged-in user (or AnonymousUser)
    request.session       # dict-like session store
    request.COOKIES       # raw cookies from the browser
    request.LANGUAGE_CODE # locale from LocaleMiddleware
```

!!! tip "Remember this"
    Middleware only runs on **HTTP** requests by default. It does **not** run on Reflex WebSocket events. That gap is what reflex-django closes.

Custom middleware works the same way. A `MultiTenantMiddleware` that sets `request.tenant` is visible to every view downstream.

---

## Models and the ORM

You declare tables in Python:

```python
# shop/models.py
from django.db import models

class Product(models.Model):
    name  = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

Run `python manage.py makemigrations` and `migrate`, and the table exists:

```python
Product.objects.create(name="Coffee", price="3.50")
Product.objects.filter(price__lt=5).order_by("name")
```

There is also an **async** API (`acreate`, `aget`, `asave`, `adelete`). Use it in Reflex event handlers:

```python
await Product.objects.acreate(name="Coffee", price="3.50")
async for p in Product.objects.filter(price__lt=5):
    ...
```

---

## The admin

Register a model and Django builds a CRUD UI:

```python
# shop/admin.py
from django.contrib import admin
from shop.models import Product

admin.site.register(Product)
```

Visit `/admin/`, log in, manage rows. reflex-django leaves this untouched.

---

## Sessions and auth

1. User submits `/admin/login/` with username and password.
2. Django validates with `authenticate()`.
3. On success, Django creates a `django_session` row and sends a `sessionid` cookie.
4. On every request, `SessionMiddleware` loads the session; `AuthenticationMiddleware` fills `request.user`.

You do not write this plumbing. It works once those middlewares are enabled.

!!! tip "The magic reflex-django extends"
    Same `sessionid` cookie, same session row, same user. Now inside a `@rx.event` handler via `AppState`.

---

## Settings and project shape

`settings.py` configures everything: `INSTALLED_APPS`, `MIDDLEWARE`, `DATABASES`, `SECRET_KEY`, and the `REFLEX_DJANGO_*` keys reflex-django adds.

```text
myproject/
├── manage.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py              # get_asgi_application() (production)
└── shop/
    ├── models.py
    ├── views.py             # Django views and Reflex pages
    ├── admin.py
    └── migrations/
```

A *project* contains many *apps*. An app is a folder of related code listed in `INSTALLED_APPS`.

---

## You now know enough

If these four bullets feel clear, you are ready for the Reflex primer:

- Django matches a URL to a view and runs it.
- `settings.MIDDLEWARE` decorates the request with `user`, `session`, and friends.
- The ORM has sync and async APIs.
- Sessions are server-side rows looked up by a `sessionid` cookie.

---

## What just happened?

You got a compressed Django tour: request flow, middleware goodies, ORM basics, and why sessions matter for reflex-django.

**Next up:** [How Reflex works in 5 minutes →](../overview/concepts.md)
