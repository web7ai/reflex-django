# CLI reference

**What you will learn:** What `run_reflex` and `export_reflex` do, which flags matter, and how reload works in default dev.

**When you need this:**

- You are choosing a dev mode (Vite HMR, compile dev, or from-build).
- You are wiring CI or production builds with `export_reflex`.

`reflex-django` adds two Django management commands. Everything else in `manage.py` works as before.

---

## The two commands

| Command | What it does |
|:---|:---|
| `python manage.py run_reflex` | Dev server: Vite on `:3000` (default) plus ASGI backend on `:8000`. |
| `python manage.py export_reflex` | Build the SPA bundle for CI and production. |

Standard Django commands are unchanged:

```bash
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser
python manage.py shell
python manage.py collectstatic
```

---

## `manage.py run_reflex`

This is the command you run while building UI.

By default it:

1. Compiles the Reflex SPA into `.web/`.
2. Starts Vite on port `3000` (open this URL for the SPA).
3. Waits for Vite, then starts uvicorn on port `8000` (admin, API, `/_event`).
4. Watches `.py` files (see [Reload precedence](#reload-precedence)).

--8<-- "snippets/run_reflex_command.md"

Open **`http://localhost:3000/`** for UI work. In default **`django_outer`** mode, the SPA's `env.json` points admin, API, and `/_event` at **`http://localhost:8000`**. Use **`http://localhost:8000/admin/`** when you want admin directly.

For compile dev on one port (no Vite), use **`--env dev`** and browse **`http://localhost:8000/`**. See [Local development](local_development.md).

!!! tip "Production has no Vite"
    In production you serve the compiled SPA from your ASGI server on one port. See [Deployment](deployment.md).

### Flags

| Flag | Effect |
|:---|:---|
| `--with-vite` / `--no-from-build` | Default. Vite HMR on `:3000`; backend on `:8000`. |
| `--from-build` / `--serve-build` | Skip Vite. Auto-export and serve from disk; watcher re-exports on `.py` change. Browse `:8000`. |
| `--env dev` | Compile dev on one port (`REFLEX_DJANGO_COMPILE_DEV=1`). Pass `--with-vite` to add HMR on `:3000` again. |
| `--env prod` | Set `REFLEX_ENV=prod` and serve compiled bundle from disk. Builds once if missing (skip with `--skip-rebuild`). |
| `--skip-rebuild` | With `--from-build` or `--env prod`, skip SPA build before start. |
| `--no-reload` | Disable file watching. |
| `--frontend-only` | Only Vite (or only build with `--from-build`); no backend. |
| `--backend-only` | Only uvicorn; assumes bundle already on disk. |
| `--frontend-port N` | Vite port (default `3000`). |
| `--backend-port N` | ASGI port (default `8000`). |
| `--backend-host HOST` | Backend bind host (default `0.0.0.0`). |
| `--loglevel LEVEL` | ASGI log level: `debug`, `info`, `warning`, `error`, `critical`. |
| `reflex_args` | Extra args forwarded to `reflex run` (prefix with `--`). |

Common combos:

```bash
# Default: Vite HMR
python manage.py run_reflex

# Compile dev on one port
python manage.py run_reflex --env dev

# Serve compiled bundle from disk
python manage.py run_reflex --from-build

# Fast Django-only iteration (skip SPA rebuilds)
python manage.py run_reflex --from-build --skip-rebuild

# Build only (CI smoke test)
python manage.py run_reflex --from-build --frontend-only

# Custom backend port
python manage.py run_reflex --backend-port 9000
```

### Boot order (default Vite mode)

```text
1. install_reflex_django_integration()
2. Sets two-port dev (REFLEX_DJANGO_SEPARATE_DEV_PORTS=1, REFLEX_DJANGO_DEV_PROXY=0)
3. reflex run: compiles .web, starts Vite :3000 and backend :8000
4. Page edits hot-reload via Vite; backend reload skips views.py (see dev_watch)
```

With `--from-build` or `--env dev`:

```text
1. install_reflex_django_integration()
2. export_reflex --frontend-only --no-zip --stage-to-static-root (unless --skip-rebuild)
3. uvicorn on :8000
4. watchfiles: on .py change, stop uvicorn, re-export, restart
```

### Common warnings

**"DJANGO_SETTINGS_MODULE not set"**

Set `export DJANGO_SETTINGS_MODULE=config.settings`. Auto-discovery via `manage.py` usually handles this.

**"Could not find compiled SPA"**

You may be using `runserver` instead of `run_reflex`, or Vite did not start. Use `python manage.py run_reflex` and open `:3000` (or `:8000` with `--env dev`). See [Troubleshooting](troubleshooting.md).

**"Port 3000 is already in use"**

Stop the other process, then re-run `run_reflex`.

---

## `manage.py export_reflex`

For CI and production. Builds the SPA and stages it where the runtime expects it.

```bash
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
```

### Flags

| Flag | Effect |
|:---|:---|
| `--frontend-only` | Build React/Vite frontend only. |
| `--backend-only` | Build backend bundle only (rare). |
| `--no-zip` | Do not zip output. |
| `--no-ssr` | Disable SSR / pre-rendered routes. |
| `--stage-to-static-root` | Copy build into `STATIC_ROOT/_reflex/`. |
| `--stage-target PATH` | Override staging path (implies `--stage-to-static-root`). |
| `--zip-dest-dir PATH` | Zip destination if you use zipping. |

### Typical CI sequence

```bash
uv sync --frozen
python manage.py migrate --noinput
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
python manage.py collectstatic --noinput
# start ASGI: reflex_django.asgi_entry:application
```

---

## Reload precedence

**Default Vite mode** when you save a `.py` file:

1. `watchfiles` notices the change.
2. **`views.py`** (or UI under `shell/`, `layout/`, `components/`): recompile SPA, Vite hot-reloads.
3. **Other Python** (states, models, settings): uvicorn restarts the backend.
4. Migrations, tests, and `.web/` are ignored.

**`--from-build` or `--env dev`:** full restart loop (stop uvicorn, re-export unless `--skip-rebuild`, start fresh uvicorn).

---

## File watching

By default, `run_reflex` watches `BASE_DIR/**/*.py`. Built-in exclusions: `.web/`, `.venv/`, migrations, tests. There are no `REFLEX_DJANGO_WATCH_PATHS` settings.

---

## `reflex django ...` entry point

Mirrors `manage.py`:

```bash
uv run reflex django migrate
uv run reflex django run_reflex
uv run reflex django collectstatic --noinput
```

Thin proxy with auto `DJANGO_SETTINGS_MODULE` discovery. Use whichever style your team prefers.

---

## Symptom quick links

| Symptom | Where to look |
|:---|:---|
| Port in use, white page, reload loops | [Troubleshooting](troubleshooting.md) |
| `AppRegistryNotReady`, missing bundle | [Troubleshooting](troubleshooting.md) |
| CSRF on admin in dev | [Local development](local_development.md) |

---

## What just happened?

You mapped the two reflex-django commands, the flags that change dev ports and rebuild behavior, and where to go when something breaks.

## Next up

[Testing →](testing.md)