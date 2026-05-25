# Command Line Interface

`reflex-django` is operated through Django's `manage.py`. Two custom commands cover the entire build + serve lifecycle:

- **`run_reflex`** — the dev loop (auto-export + serve + watch on port `8000`).
- **`export_reflex`** — build the SPA bundle for CI / deployment.

Every other Django command (`migrate`, `makemigrations`, `createsuperuser`, `shell`, `collectstatic`, …) works exactly as it does on any Django project.

---

## `manage.py run_reflex`

```bash
python manage.py run_reflex
```

What it does, in order:

1. Bootstraps the reflex-django integration in the current Python process (patches `reflex.config.get_config`, runs `configure_django()`, imports `{app}/views.py`).
2. Auto-exports the Reflex SPA bundle:
   `manage.py export_reflex --frontend-only --no-zip --stage-to-static-root`.
3. Spawns `uvicorn` as a subprocess pointed at `reflex_django.asgi_entry:application` on `0.0.0.0:8000`.
4. Watches the project root for `.py` changes via `watchfiles`. Every change cleanly stops the uvicorn subprocess, re-exports the SPA, and respawns uvicorn.

Excluded from the watcher: `.web/`, `node_modules/`, `staticfiles/`, `static_collected/`, `.reflex/`, `dist/`, `build/`, and your `STATIC_ROOT`. The export itself can never re-trigger the loop.

### Flags

| Flag | Effect |
|:---|:---|
| *(none)* | Auto-export + serve + watch. The canonical dev loop. |
| `--skip-rebuild` | Keep the watcher but skip the per-restart re-export. Fast path for Python-only edits that don't touch Reflex pages. |
| `--no-reload` | One-shot: rebuild + serve, no watcher, no auto-restart. |
| `--env prod` | Production semantics: no auto-export at boot, `DEBUG` off, dev proxy off, no watcher. |
| `--frontend-only` | Just rebuild the bundle and exit. Useful in CI / pre-deploy. |
| `--backend-only` | Skip the watcher and serve whatever's on disk. |
| `--with-vite` | Opt out of from-build and run the legacy Vite-HMR dev loop. |
| `--backend-host`, `--backend-port` | ASGI bind host / port (defaults `0.0.0.0:8000`). |
| `--frontend-port` | Vite port when `--with-vite` is active (default `3000`). |
| `--loglevel` | Uvicorn log level (`debug`, `info`, `warning`, `error`). |

### Examples

```bash
# Default dev loop: auto-export + watch + restart on every .py change
python manage.py run_reflex

# Fast iteration: skip the re-export on each restart
python manage.py run_reflex --skip-rebuild

# Production smoke test: build once and serve on a custom port
python manage.py run_reflex --env prod --backend-port 9000

# Build the SPA and exit (useful in CI / pre-deploy)
python manage.py run_reflex --frontend-only

# Legacy Vite HMR (no auto-export, Vite reverse-proxied through Django)
python manage.py run_reflex --with-vite
```

### Reload precedence (highest wins)

1. `--env prod` → no reload, no auto-export.
2. `--no-reload` → no reload, but auto-export still runs once at boot.
3. `--with-vite` → in-process uvicorn reload + Vite HMR (legacy loop).
4. Default → parent-side watch loop drives clean re-export + uvicorn restart.

---

## `manage.py export_reflex`

```bash
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
```

Builds the Reflex SPA bundle using Reflex's `export` utilities while keeping the reflex-django integration installed (so `rxconfig.py` is synthesised in memory and your `urls.py` provides the runtime config). The compiled output lands in `.web/build/client/` (SSR layout) or `.web/_static/` (legacy layout).

### Flags

| Flag | Effect |
|:---|:---|
| `--frontend-only` | Build only the frontend assets. Skip the backend export. |
| `--backend-only` | Build only the backend artifacts. Skip the frontend bundle. |
| `--no-zip` | Don't zip the output. Useful when you're staging files directly. |
| `--zip-dest-dir <path>` | Custom destination for the zipped output. |
| `--no-ssr` | Disable Reflex's SSR pre-rendering. |
| `--stage-to-static-root` | Copy the compiled SPA into `STATIC_ROOT/_reflex/` (or `--stage-target`). |
| `--stage-target <path>` | Override the staging path (default `STATIC_ROOT/_reflex`). |
| `--env <name>` | Reflex environment label passed through to the exporter. |

### Typical CI sequence

```bash
python manage.py migrate
python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root
python manage.py collectstatic --noinput
# Boot the ASGI server pointed at reflex_django.asgi_entry:application
```

---

## Standard Django commands

All work unchanged:

```bash
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser
python manage.py shell
python manage.py collectstatic --noinput
python manage.py test
```

`run_reflex` is the only command that owns the ASGI server lifecycle. `runserver` is **not** the right choice for full-stack development — it lacks the outer dispatcher, so Reflex WebSockets and the SPA catch-all would bypass the reflex-django integration.

---

## What `run_reflex` boots, end to end

1. `install_reflex_django_integration()` — patches `reflex.config.get_config` to read from `reflex_mount()`.
2. `configure_django()` — `django.setup()` so apps, models, and middleware are ready.
3. `refresh_get_config_bindings()` — re-resolves any cached config references.
4. Imports `ROOT_URLCONF`; `reflex_mount()` registers the in-memory `rx.Config`.
5. `reflex_django.django_led_app` imports `{app}/views.py` for each `INSTALLED_APPS` entry.
6. `rx.App()` is instantiated; `@template` / `@page` decorators register routes.
7. `manage.py export_reflex --frontend-only --no-zip --stage-to-static-root` runs in-process.
8. `uvicorn` subprocess starts at `reflex_django.asgi_entry:application`.
9. `watchfiles` watches `BASE_DIR` for `.py` changes and drives the rebuild + restart loop.

---

## When to use the Reflex CLI directly

`reflex-django` wraps Reflex's own CLI for everything end-users need (`run`, `export`). You should not need `reflex run`, `reflex export`, or `reflex init` directly — those commands look for `rxconfig.py` on disk, which `reflex-django` deliberately does not require.

If you really want to use the Reflex CLI, set `REFLEX_DJANGO_URL_ROUTING=reflex_led` to fall back to the legacy two-port layout where Reflex runs the show and Django is a sub-application. That mode is supported for backwards compatibility but not the default.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|:---|:---|:---|
| `WatchFiles detected changes ... Reloading...` hangs | You're running with `--with-vite` and uvicorn's in-process reloader hit a re-import deadlock. | Drop `--with-vite` and use the default from-build watch loop. |
| `manage.py run_reflex` exits immediately with "Could not locate the built SPA directory" | Reflex's exporter produced an unexpected layout, or `--frontend-only` was disabled by environment overrides. | Run `python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root` manually and check the output paths. |
| `rxconfig.py not found` from a Reflex CLI subcommand | You're calling `reflex run` / `reflex export` directly. | Use `manage.py run_reflex` / `manage.py export_reflex` — they synthesise the config in memory. |
| `SynchronousOnlyOperation` on `request.user` | Your code reads `request.user` from an async context without the bridge. | Use `self.user` (the bridge already eager-resolves it via `aget_user`). |
| Uvicorn boots but `/` returns 404 | SPA bundle wasn't built / wasn't staged. | `python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root` then re-run. |

---

**Navigation:** [← Best practices](best_practices.md) | [Testing →](testing.md)
