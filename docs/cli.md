# CLI reference

`reflex-django` adds two Django management commands. Plus the rest of `manage.py` keeps working as you'd expect. This page is a tour of what each command does and the flags that matter.

---

## The two new commands

| Command | What it does |
|:---|:---|
| `python manage.py run_reflex` | Dev server: run Vite for hot-module reload + uvicorn, hot-reload the frontend on Reflex page edits. |
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

This is the one you'll run all day. By default it starts **two dev servers**:

1. **Compile** the Reflex SPA into `.web/`
2. **Start Vite** on port `3000` (frontend — **open this URL for the SPA**)
3. **Wait** until Vite is serving, then **start uvicorn** on port `8000` (backend — admin, API, `/_event`)
4. **Watch** `.py` files — page edits in `views.py` recompile and Vite hot-reloads; most other Python changes restart the backend (see [Reload precedence](#reload-precedence))

```bash
python manage.py run_reflex
```

Open **`http://localhost:3000/`** for UI work. In default **`django_outer`** mode, the SPA's `env.json` points admin, API, and `/_event` at **`http://localhost:8000`** — Vite does not proxy those paths. Use **`http://localhost:8000/admin/`** when you want the admin directly.

For **compile dev on one port** (no Vite), use **`--env dev`** and browse **`http://localhost:8000/`**. See [Local development](local_development.md).

In production there's no Vite — you serve the compiled SPA from your ASGI server on one port (see [Deployment](deployment.md)).

### Flags

| Flag | Effect |
|:---|:---|
| `--with-vite` / `--no-from-build` | The default. Run Vite for hot-module reload on `:3000`; backend on `:8000`. |
| `--from-build` / `--serve-build` | Skip Vite. Auto-export the SPA and serve the compiled bundle from disk; the watcher re-exports + restarts uvicorn on every `.py` change. Browse **`http://localhost:8000/`**. |
| `--env dev` | Compile dev on one port: recompile `.web/` on save and serve from Django on `:8000` (sets `REFLEX_DJANGO_COMPILE_DEV=1`). Pass `--with-vite` to add live HMR on `:3000` again. |
| `--env prod` | Set `REFLEX_ENV` to `prod` and serve the compiled bundle from disk (no Vite). If no bundle is found, it builds one once (skip with `--skip-rebuild`). Browse **`http://localhost:8000/`**. |
| `--skip-rebuild` | (with `--from-build` or `--env prod`) Skip the SPA build before starting. Good for "I only edited a Django model" iterations. |
| `--no-reload` | Don't watch for changes. The server runs once and exits when you Ctrl+C. |
| `--frontend-only` | Only run the Vite frontend (or, with `--from-build`, only build the bundle); don't start the server. |
| `--backend-only` | Only run uvicorn; don't start Vite or build the SPA. (Assumes the bundle is already on disk.) |
| `--frontend-port N` | Override the Vite port (default `3000`). |
| `--backend-port N` | Override the ASGI backend port (default `8000`). |
| `--backend-host HOST` | Backend bind host (default `0.0.0.0`). |
| `--loglevel LEVEL` | ASGI log level: `debug`, `info`, `warning`, `error`, `critical`. |
| `reflex_args` | Extra arguments forwarded to `reflex run` (prefix with `--`). |

Common combos:

```bash
# Default: Vite hot-module reload for Reflex page edits
python manage.py run_reflex

# Compile dev on one port (no Vite after first compile)
python manage.py run_reflex --env dev

# Serve a compiled bundle from disk (no Node, auto-rebuild on .py change)
python manage.py run_reflex --from-build

# Fast iteration on Django code only (from-build, skip SPA rebuilds)
python manage.py run_reflex --from-build --skip-rebuild

# Build only, don't serve (useful in CI to verify)
python manage.py run_reflex --from-build --frontend-only

# Custom backend port
python manage.py run_reflex --backend-port 9000
```

### What it boots, in order (default Vite mode)

```text
1. install_reflex_django_integration()
     - configures Django, patches reflex.config.get_config, builds in-memory rxconfig
     - patches reflex run so the backend serves reflex_django.asgi_entry:application
2. Sets two-port dev env (REFLEX_DJANGO_SEPARATE_DEV_PORTS=1, DEV_PROXY=0)
3. reflex run (native Reflex dev loop)
     - compiles .web, starts Vite on :3000 and the Django-outer ASGI backend on :8000
     - frontend page edits hot-reload via Vite; backend reload skips views.py (see dev_watch)
```

Browse **`http://localhost:3000/`** for the SPA. Admin, API, and `/_event` use **`http://localhost:8000/`** (env.json points the browser at the backend port).

With `--from-build` or `--env dev` instead:

```text
1. install_reflex_django_integration()
2. (unless --skip-rebuild)
     export_reflex --frontend-only --no-zip --stage-to-static-root
3. uvicorn subprocess on port 8000
4. parent process: watchfiles loop
     - on .py change: stop uvicorn, re-export, start fresh uvicorn
```

Open **`http://localhost:8000/`** for the SPA in those modes.

### Common warnings, easily fixed

**"DJANGO_SETTINGS_MODULE not set"**
Set it in your shell: `export DJANGO_SETTINGS_MODULE=config.settings`. The auto-discovery via `manage.py` usually catches this, but if it can't, set it explicitly.

**"Could not find compiled SPA" / "Reflex SPA bundle not found"**
You're probably not running `run_reflex` (e.g. `runserver` or bare `uvicorn`), or Vite didn't start. Use `python manage.py run_reflex` and open `http://localhost:3000/` (default two-port). If you use `--env dev` or `--from-build`, open `http://localhost:8000/`. If port `3000` is busy, free it first — see [Local development](local_development.md#troubleshooting).

**"Port 3000 is already in use"**
Stop the other dev server (`netstat` / Task Manager), then re-run `run_reflex`.

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
| `--no-ssr` | Disable Reflex server-side rendering / pre-rendered routes. |
| `--stage-to-static-root` | Copy the build into `STATIC_ROOT/_reflex/`, where `ReflexMountView` serves it from. |
| `--stage-target PATH` | Override the staging destination (implies `--stage-to-static-root`). Defaults to `STATIC_ROOT/_reflex`. |
| `--zip-dest-dir PATH` | If you do want a zip, where to put it (defaults to CWD). |

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

1. `watchfiles` notices the change.
2. If the path is **`views.py`** (or UI assets under `shell/`, `layout/`, `components/`), the runner recompiles the SPA and Vite hot-reloads the browser.
3. If the path is **other Python** (states, models, settings, services, …), uvicorn **restarts** the backend worker (see `dev_watch.py`).
4. Migrations, tests, and `.web/` are ignored.

With **`--from-build`** or **`--env dev`**, the watcher owns a full restart loop instead:

1. `watchfiles` notices the change.
2. If it's a `.py` file inside the project (not in `.web/`, `.venv/`, etc.), the watcher triggers a restart.
3. The watcher sends SIGTERM to uvicorn; uvicorn shuts down its workers.
4. The watcher re-runs the export (unless `--skip-rebuild`).
5. The watcher starts a fresh uvicorn subprocess.

---

## File watching

By default, `run_reflex` watches `BASE_DIR/**/*.py`. There are no `REFLEX_DJANGO_WATCH_PATHS` or `REFLEX_DJANGO_IGNORE_PATHS` settings — the watch root is always the project base directory, with built-in exclusions for `.web/`, `.venv/`, migrations, and tests.

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
| Port already in use | Old uvicorn from a previous run still listening | Stop the process or use `--backend-port N` |
| Hot-reload stops working | Watcher process died silently | Restart `run_reflex` |
| `AppRegistryNotReady` on start | Model import at module top level | Move the import inside event handlers |
| `ModuleNotFoundError: rxconfig` | Old stub file present | Delete `rxconfig.py`; `reflex_mount()` is the only config |
| Browser shows white page | SPA bundle missing | Run without `--skip-rebuild`, or run `export_reflex --frontend-only --stage-to-static-root` |
| `Vite manifest not found` (under `--with-vite`) | Vite didn't start | Check the parent process logs; try without `--with-vite` |

---

**Next:** [Testing →](testing.md)
