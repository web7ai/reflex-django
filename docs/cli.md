# CLI reference

`reflex-django` adds two Django management commands. Plus the rest of `manage.py` keeps working as you'd expect. This page is a tour of what each command does and the flags that matter.

---

## The two new commands

| Command | What it does |
|:---|:---|
| `python manage.py run_reflex` | Dev server: build the SPA, run uvicorn, watch for changes, restart on edit. |
| `python manage.py export_reflex` | Build the SPA bundle for production (CI). |

Plus everything you already use:

```bash
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser
python manage.py shell
python manage.py collectstatic
```

Nothing changes about those.

---

## `manage.py run_reflex` — the dev server

This is the one you'll run all day. It does three things:

1. **Build the SPA.** Auto-runs `export_reflex` (frontend-only, no zip, staged to `STATIC_ROOT/_reflex/`) before starting.
2. **Start uvicorn** as a subprocess on port 8000 (or wherever you set `backend_port`), pointed at `reflex_django.asgi_entry:application`.
3. **Watch** the project for `.py` changes. Each change cleanly stops uvicorn, re-runs the build, and starts a fresh uvicorn.

```bash
python manage.py run_reflex
```

That's the default. Open `http://localhost:8000/` and you have your admin at `/admin/`, the SPA at `/`, and the Reflex WebSocket on `/_event`.

### Flags

| Flag | Effect |
|:---|:---|
| `--skip-rebuild` | Skip the SPA build before starting. Good for "I only edited a Django model" iterations. |
| `--no-reload` | Don't watch for changes. The server runs once and exits when you Ctrl+C. |
| `--env prod` | Set `REFLEX_ENV` to `prod` (changes a few default toggles — see Reflex's docs). |
| `--frontend-only` | Only build the SPA frontend; don't start the server. |
| `--backend-only` | Only run uvicorn; don't build the SPA. (Assumes the bundle is already on disk.) |
| `--with-vite` | Use the Vite hot-reload dev server proxied through Django. Hot-module reload on Reflex page edits. |
| `--port N` | Override the backend port. |

Common combos:

```bash
# Fast iteration on Django code only (skip SPA rebuilds)
python manage.py run_reflex --skip-rebuild

# Hot-module reload for Reflex page edits
python manage.py run_reflex --with-vite

# Build only, don't serve (useful in CI to verify)
python manage.py run_reflex --frontend-only
```

### What it boots, in order

```text
1. install_reflex_django_integration()
     - configures Django, patches reflex.config.get_config, builds in-memory rxconfig
2. (unless --skip-rebuild)
     export_reflex --frontend-only --no-zip --stage-to-static-root
3. uvicorn subprocess
     reflex_django.asgi_entry:application on port 8000
4. parent process: watchfiles loop
     - on .py change: stop uvicorn, re-export, start fresh uvicorn
```

Open the browser, the page loads, the WebSocket connects, you're in.

### Common warnings, easily fixed

**"DJANGO_SETTINGS_MODULE not set"**
Set it in your shell: `export DJANGO_SETTINGS_MODULE=config.settings`. The auto-discovery via `manage.py` usually catches this, but if it can't, set it explicitly.

**"Could not find compiled SPA"**
The build hasn't run yet, or `STATIC_ROOT` isn't writable. Run `python manage.py run_reflex` once without `--skip-rebuild`.

**Restart loop on every file**
You're probably saving files in a watched directory that gets modified by the rebuild itself (`.web/`). Make sure your editor's "save" doesn't also touch generated files.

---

## `manage.py export_reflex` — build the SPA bundle

For CI and production. Builds the compiled SPA and stages it where the runtime needs it.

```bash
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
```

That's the canonical invocation for a one-process production deploy.

### Flags

| Flag | Effect |
|:---|:---|
| `--frontend-only` | Only build the React/Vite frontend. Skip the backend bundle. |
| `--backend-only` | The opposite. Rare. |
| `--no-zip` | Don't zip the output. (Zipping is the old Reflex deploy format; you don't want it here.) |
| `--stage-to-static-root` | Copy the build into `STATIC_ROOT/_reflex/`, where `ReflexMountView` serves it from. |
| `--zip-dest PATH` | If you do want a zip, where to put it. |

### Typical CI sequence

```bash
uv sync --frozen
python manage.py migrate --noinput
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
python manage.py collectstatic --noinput
# now start the ASGI server pointed at reflex_django.asgi_entry:application
```

The first two are standard Django. The third builds the SPA. The fourth picks up the SPA assets (plus your admin static files) into `STATIC_ROOT`. Your reverse proxy then serves `/static/` directly from disk.

---

## Reload precedence

When you save a file in dev:

1. `watchfiles` notices the change.
2. If it's a `.py` file inside the project (not in `.web/`, `.venv/`, etc.), the watcher triggers a restart.
3. The watcher sends SIGTERM to uvicorn; uvicorn shuts down its workers.
4. The watcher re-runs the export (unless `--skip-rebuild`).
5. The watcher starts a fresh uvicorn subprocess.

If you used `--with-vite`, edits to Reflex components hot-reload through Vite without restarting the Python process. Edits to states or non-page code still trigger a restart.

---

## Customizing what's watched

By default, `run_reflex` watches `BASE_DIR/**/*.py`. To restrict or extend:

```python
# settings.py
REFLEX_DJANGO_WATCH_PATHS = [
    BASE_DIR / "config",
    BASE_DIR / "shop",
    BASE_DIR / "blog",
]
```

Or to ignore specific directories:

```python
REFLEX_DJANGO_IGNORE_PATHS = [
    BASE_DIR / "data",
    BASE_DIR / "uploads",
]
```

(These setting names are illustrative — check your installed version. The defaults usually work.)

---

## The `reflex django ...` CLI entry point

There's also a `reflex django` command-line entry point that mirrors `manage.py`:

```bash
uv run reflex django migrate
uv run reflex django run_reflex
uv run reflex django collectstatic --noinput
```

It's a thin proxy that auto-discovers `DJANGO_SETTINGS_MODULE` from `manage.py`. Use whichever feels natural. For Django-first projects, `python manage.py ...` reads more naturally to most teams.

---

## Troubleshooting matrix

| Symptom | Likely cause | Fix |
|:---|:---|:---|
| Port already in use | Old uvicorn from a previous run still listening | `pkill -f uvicorn` or use `--port N` |
| Hot-reload stops working | Watcher process died silently | Restart `run_reflex` |
| `AppRegistryNotReady` on start | Model import at module top level | Move the import inside event handlers |
| `ModuleNotFoundError: rxconfig` | Old stub file present | Delete `rxconfig.py`; `reflex_mount()` is the only config |
| Browser shows white page | SPA bundle missing | Run without `--skip-rebuild`, or run `export_reflex --frontend-only --stage-to-static-root` |
| `Vite manifest not found` (under `--with-vite`) | Vite didn't start | Check the parent process logs; try without `--with-vite` |

---

**Next:** [Testing →](testing.md)
