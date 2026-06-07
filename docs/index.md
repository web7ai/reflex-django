<style>
  .md-content .md-typeset > h1:first-of-type { display: none; }
</style>

<div class="rd-hero" markdown>
  <h1 class="rd-hero__brand">reflex-django</h1>
  <p class="rd-hero__tagline">Keep Django. Get a reactive UI in Python. One process, shared cookies, native Reflex dev.</p>
  <p class="rd-hero__badges">
    <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/v/reflex-django?color=%23e91e63&label=pypi" alt="PyPI"></a>
    <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/pyversions/reflex-django.svg?color=%23ad1457" alt="Python"></a>
    <a href="https://github.com/web7ai/reflex-django/blob/main/LICENSE"><img src="https://img.shields.io/github/license/web7ai/reflex-django.svg?color=%23ec407a" alt="License"></a>
  </p>
</div>

**What you'll learn:** How reflex-django lets you keep Django and add a reactive Reflex UI without a separate frontend repo.

**When you need this:**

- You love Django (ORM, admin, migrations) but want a modern SPA without writing React by hand.
- You want one origin in production, shared session cookies, and `request.user` inside button handlers.

---

## Welcome

You are probably here because Django already runs your backend, and you want a reactive UI in Python instead of spinning up Node, CORS, and a token bridge. reflex-django is the glue that makes that feel normal.

You keep writing Django. You write UI in [Reflex](https://reflex.dev). In production they run as **one program** on one port. In dev, `run_reflex` starts Vite on `:3000` and the backend on `:8000`, with `env.json` keeping admin, API, and `/_event` on the same cookies.

!!! tip "Start with the map"
    New here? Open the [Learning path](learning_path.md) for a guided tour with time estimates, or jump to [The three knobs](mental_model.md) if you like a diagram first.

---

## What you'll actually write

Three places shape almost every project. Settings hold Reflex config. `urls.py` imports your page modules. `views.py` holds your `@page` functions and state classes.

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

One command starts **two** dev servers: Vite on `:3000` for the SPA and hot reload, Django plus the Reflex backend on `:8000` for admin, API, and the `/_event` WebSocket. Prefer one URL in the address bar? Use `python manage.py run_reflex --env dev` and browse `:8000`. See [Local development](local_development.md).

In production there is no Vite. You export the SPA and serve everything from your ASGI server on a single port. See [Deployment](deployment.md).

---

## Pick a path

<div class="rd-path-grid" markdown="0">
<a href="learning_path/" class="rd-path-card rd-path-card--beginner">
<p class="rd-path-card__title">Guided learning path</p>
<p class="rd-path-card__meta">~45 minutes</p>
<p class="rd-path-card__desc">A checkbox tour from mental model to your first running app.</p>
</a>
<a href="quickstart/" class="rd-path-card rd-path-card--beginner">
<p class="rd-path-card__title">Just show me the code</p>
<p class="rd-path-card__meta">~15 minutes</p>
<p class="rd-path-card__desc">Build a small todo app. Pages, state, auth, and the database.</p>
</a>
<a href="existing_django_project/" class="rd-path-card rd-path-card--intermediate">
<p class="rd-path-card__title">I have Django already</p>
<p class="rd-path-card__meta">~20 minutes</p>
<p class="rd-path-card__desc">Add Reflex pages to a brownfield project. Keep models, admin, and API.</p>
</a>
<a href="existing_reflex_project/" class="rd-path-card rd-path-card--intermediate">
<p class="rd-path-card__title">I have Reflex already</p>
<p class="rd-path-card__meta">~20 minutes</p>
<p class="rd-path-card__desc">Wrap your Reflex app in Django for ORM, admin, and sessions.</p>
</a>
</div>

---

## Quick lookup

| I want to... | Read |
|:---|:---|
| Add Reflex to my Django project | [Existing Django project](existing_django_project.md) |
| Configure ports, app name, routing mode | [Configuration](configuration.md) |
| Read `request.user` in a button handler | [AppState bridge](state_management.md) |
| Deploy to one container | [Deployment](deployment.md) |
| Look up a `REFLEX_DJANGO_*` setting | [Settings reference](settings_reference.md) |

---

## What just happened?

You saw the three-file shape of a reflex-django project (settings, urls, views), how dev uses two ports by default, and where to go next depending on whether you want a tour or working code.

**Next up:** [Learning path (start here) →](learning_path.md)
