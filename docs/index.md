<div class="rd-hero" markdown>
  <h1 class="rd-hero__brand">reflex-django</h1>
  <p class="rd-hero__tagline">You keep Django. You add a reactive UI in Python.</p>
  <p class="rd-hero__badges">
    <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/v/reflex-django?color=%232e7d32&label=pypi" alt="PyPI"></a>
    <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/pyversions/reflex-django.svg" alt="Python"></a>
    <a href="https://github.com/web7ai/reflex-django/blob/main/LICENSE"><img src="https://img.shields.io/github/license/web7ai/reflex-django.svg" alt="License"></a>
  </p>
</div>

You already run Django. reflex-django lets you build the UI in [Reflex](https://reflex.dev) without a separate frontend repo. One process in production, shared session cookies, and `request.user` inside button handlers.

- **Same origin** - admin, API, and SPA on one host in production
- **Django-first** - settings, ORM, auth, and middleware stay familiar
- **One dev command** - `python manage.py run_reflex` starts Vite and the backend

## Start here

<div class="rd-card-grid" markdown="0">
<a href="getting-started/" class="rd-card">
<p class="rd-card__title">Getting started</p>
<p class="rd-card__desc">Install, run the quickstart, and learn the project layout.</p>
</a>
<a href="guides/" class="rd-card">
<p class="rd-card__title">Guides</p>
<p class="rd-card__desc">Pages, state, auth, CRUD, uploads, and more.</p>
</a>
</div>

## The three files you touch most

```python
--8<-- "snippets/minimal_settings.py"
```

```python
--8<-- "snippets/minimal_urls.py"
```

```python
--8<-- "snippets/minimal_views.py"
```

Then run:

--8<-- "snippets/run_reflex_command.md"

In dev, Vite listens on `:3000` and proxies to the backend on `:8000`. See [Local development](getting-started/local_development.md).

## Quick lookup

| I want to... | Read |
|:---|:---|
| See how Django and Reflex fit | [How it fits](overview/concepts.md) |
| Add Reflex to my Django project | [Existing Django project](getting-started/existing_django_project.md) |
| Read `request.user` in a handler | [State](guides/state.md) |
| Deploy to one container | [Deployment](operations/deployment.md) |
| Look up a setting | [Settings reference](reference/settings.md) |