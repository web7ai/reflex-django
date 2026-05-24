# Command Line Interface

Django-first projects use **`manage.py`** for Django commands and **`run_reflex`** for the unified dev server. The Reflex CLI remains available for optional workflows.

---

## Primary commands (Django-first)

```bash
# Unified Reflex + Django dev server (use this for full-stack dev)
python manage.py run_reflex

# Standard Django — unchanged
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser
python manage.py shell
python manage.py collectstatic
```

`run_reflex` calls the same stack as `reflex run`: one ASGI process, Django prefixes + Reflex SPA + WebSockets.

### `run_reflex` options

Forwarded to `reflex run`:

```bash
python manage.py run_reflex --frontend-port 3000 --backend-port 8000
python manage.py run_reflex --env prod
python manage.py run_reflex --backend-only
python manage.py run_reflex --frontend-only
```

Configure defaults in `reflex_mount(rx_config={...})` instead of duplicating ports in multiple files.

---

## Optional: Reflex CLI wrappers

When the Reflex CLI is installed, these also work:

```bash
uv run reflex django migrate
uv run reflex django createsuperuser
uv run reflex-django migrate          # standalone script alias
```

They load Django the same way: discover `manage.py`, run `configure_django()`, forward to Django’s management utility.

For day-to-day Django-first work, prefer **`python manage.py <command>`**.

---

## What `run_reflex` bootstraps

1. `install_reflex_django_integration()` — patches `get_config()` from `reflex_mount()` data
2. `ensure_reflex_cli_layout()` — in-memory `rxconfig`, `.web`, Reflex user dir (no template picker)
3. `ensure_django_led_app_ready()` — imports pages, builds `rx.App()`
4. Starts Reflex dev processes (frontend + backend)

---

## Database workflow

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py sqlmigrate myapp 0001
```

Use the same database settings as the rest of your Django project — `reflex_mount(rx_config={"db_url": ...})` only affects Reflex’s config object when you mirror DB settings there.

---

## Static files (production)

```bash
python manage.py collectstatic --noinput
```

Serve via your ASGI entry point with `django.contrib.staticfiles` in `INSTALLED_APPS`. See [Deployment](deployment.md).

---

## Do not use for full-stack dev

| Command | Issue |
|:---|:---|
| `python manage.py runserver` on backend port | WebSockets (`/_event`) won’t use the unified Reflex dispatcher |
| `reflex init` on brownfield projects | Scaffolds a separate Reflex app layout you don’t need |

Use **`run_reflex`** after `reflex_mount()` is configured.

---

**Navigation:** [← Best practices](best_practices.md) | [Testing →](testing.md)
