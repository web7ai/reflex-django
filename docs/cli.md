# CLI reference

`reflex-django` adds two Django management commands. Plus the rest of `manage.py` keeps working as you'd expect. This page is a tour of what each command does and the flags that matter.

---

## The two new commands

| Command | What it does |
|:---|:---|
| `python manage.py run_reflex` | Dev server: run Vite for hot-module reload + uvicorn, hot-reload the frontend on Reflex edits. |
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

This is the one you'll run all day. By default it does three things:

1. **Start Vite** for hot-module reload, reverse-proxied by Django (invisible to you on the single port).
2. **Start uvicorn** as a subprocess on port 8000 (or wherever you set `backend_port`), pointed at `reflex_django.asgi_entry:application`. It boots **once** and stays up.
3. **Watch** the Reflex source for `.py` changes. Each change recompiles the SPA into `.web` and Vite **hot-reloads only the frontend** — the backend is not restarted.

```bash
python manage.py run_reflex
```

That's the default. Open `http://localhost:8000/` and you have your admin at `/admin/`, the SPA at `/`, and the Reflex WebSocket on `/_event`.

Because the backend stays up, edits to **states, event handlers, or other server-side Python** won't take effect until you restart the command (Ctrl+C and re-run, or save again after restarting). Pure UI/page edits hot-reload instantly. If you'd rather have the backend auto-rebuild and serve a compiled bundle from disk (no Node, no HMR), use `--from-build`.

### Flags

| Flag | Effect |
|:---|:---|
| `--with-vite` | The default. Run Vite for hot-module reload, proxied through Django. Frontend edits hot-reload; the backend stays up. |
| `--from-build` | Opt out of Vite. Auto-export the SPA and serve the compiled bundle from disk; the watcher re-exports + restarts uvicorn on every `.py` change. |
| `--skip-rebuild` | (with `--from-build`) Skip the SPA build before starting. Good for "I only edited a Django model" iterations. |
| `--no-reload` | Don't watch for changes. The server runs once and exits when you Ctrl+C. (In the default Vite mode this disables the frontend recompile loop too.) |
| `--env prod` | Set `REFLEX_ENV` to `prod` and serve the compiled bundle from disk (no Vite). If no bundle is found, it builds one once (skip with `--skip-rebuild`); a pre-built bundle is served as-is. |
| `--frontend-only` | Only run the Vite frontend (or, with `--from-build`, only build the bundle); don't start the server. |
| `--backend-only` | Only run uvicorn; don't start Vite or build the SPA. (Assumes the bundle is already on disk.) |
| `--port N` | Override the backend port. |

Common combos:

```bash
# Default: Vite hot-module reload for Reflex page edits
python manage.py run_reflex

# Serve a compiled bundle from disk (no Node, auto-rebuild on .py change)
python manage.py run_reflex --from-build

# Fast iteration on Django code only (from-build, skip SPA rebuilds)
python manage.py run_reflex --from-build --skip-rebuild

# Build only, don't serve (useful in CI to verify)
python manage.py run_reflex --from-build --frontend-only
```

### What it boots, in order (default Vite mode)

```text
1. install_reflex_django_integration()
     - configures Django, patches reflex.config.get_config, builds in-memory rxconfig
2. Vite dev server (frontend runner subprocess)
     - compiles .web once, runs `vite dev` on the frontend port
     - watches the Reflex source: on .py change, recompiles .web in a fresh
       interpreter so Vite hot-reloads the frontend
3. uvicorn subprocess
     reflex_django.asgi_entry:application on port 8000 — boots once, stays up
```

With `--from-build` instead:

```text
1. install_reflex_django_integration()
2. (unless --skip-rebuild)
     export_reflex --frontend-only --no-zip --stage-to-static-root
3. uvicorn subprocess on port 8000
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

In the **default Vite mode**, when you save a `.py` file:

1. `watchfiles` (in the frontend runner) notices the change.
2. The runner recompiles the SPA into `.web` in a fresh interpreter.
3. Vite hot-reloads the changed frontend modules in the browser.
4. The uvicorn backend is **not** touched — it keeps running.

Because the backend is never re-imported, edits to **states, event handlers, or other server-side Python** only reach the running backend after you restart `run_reflex`. Pure UI/page edits hot-reload instantly.

With **`--from-build`**, the watcher owns a full restart loop instead:

1. `watchfiles` notices the change.
2. If it's a `.py` file inside the project (not in `.web/`, `.venv/`, etc.), the watcher triggers a restart.
3. The watcher sends SIGTERM to uvicorn; uvicorn shuts down its workers.
4. The watcher re-runs the export (unless `--skip-rebuild`).
5. The watcher starts a fresh uvicorn subprocess.

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
