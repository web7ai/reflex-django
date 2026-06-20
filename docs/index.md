<div class="rd-hero" markdown>
  <h1 class="rd-hero__brand">reflex-django</h1>
  <p class="rd-hero__tagline">You keep Django. You add a reactive UI in Python.</p>
  <p class="rd-hero__badges">
    <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/v/reflex-django?color=%232e7d32&label=pypi" alt="PyPI"></a>
    <a href="https://pypi.org/project/reflex-django"><img src="https://img.shields.io/pypi/pyversions/reflex-django.svg" alt="Python"></a>
    <a href="https://github.com/web7ai/reflex-django/blob/main/LICENSE"><img src="https://img.shields.io/github/license/web7ai/reflex-django.svg" alt="License"></a>
  </p>
</div>

## What is reflex-django?

**reflex-django** connects Django and [Reflex](https://reflex.dev) so you run one app, not two servers you glue together by hand. Django owns your database, admin, session auth, and REST or API routes. Reflex owns reactive pages you write in Python.

Install the plugin, set `profile: "integrated"` in `rxconfig.py`, and run `reflex run`. Django admin, your API, and Reflex pages share cookies and sessions. Handlers on Django-aware state (`AppState`, `ModelState`, or `DjangoUserState`) see `self.request.user` when bridge is enabled and the resolved event tier binds Django context.

## Install

```bash
uv add reflex-django
```

```bash
pip install reflex-django
```

For a new project, also add Django and Reflex (`uv add django reflex reflex-django` or `pip install django reflex reflex-django`). See [Integration](learn/integration.md) for the full layout.

## Configure and run

```python
--8<-- "snippets/profile_rxconfig.py"
```

1. Add `reflex_django` to `INSTALLED_APPS` and `AsyncStreamingMiddleware` last ([Integration](learn/integration.md))
2. Create `shop/shop.py` with `app = rx.App()` and `app.add_page(...)` ([Pages and state](advanced/pages-and-state.md))
3. `reflex django migrate` then `reflex run` → **http://localhost:3000/**

## Learn step by step

<div class="rd-card-grid" markdown="1">

[**1 · Integration**<br><span class="rd-card__desc">Install, wire settings, urls, and run your first app.</span>](learn/integration.md){ .rd-card }

[**2 · Embed**<br><span class="rd-card__desc">Django admin and API inside the Reflex backend.</span>](learn/embed.md){ .rd-card }

[**3 · Mount**<br><span class="rd-card__desc">URL prefixes and the SPA catch-all.</span>](learn/mount.md){ .rd-card }

[**4 · Proxy**<br><span class="rd-card__desc">Port 3000 dev wiring and split dev.</span>](learn/proxy.md){ .rd-card }

[**5 · Bridge**<br><span class="rd-card__desc">Request context and the logged-in user in handlers.</span>](learn/bridge.md){ .rd-card }

[**Tutorial**<br><span class="rd-card__desc">Build a todo app with auth and the async ORM.</span>](learn/quickstart.md){ .rd-card }

</div>

Need serializers, auth pages, deploy help, security guidance, or migration notes? See [Advanced](advanced/index.md).

For AI-assisted work, use the repository [`llm.txt`](https://github.com/web7ai/reflex-django/blob/main/llm.txt) guide as the compact source map.
