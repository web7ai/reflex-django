"""Scaffold a new Reflex + Django project using ``uv`` and ``reflex-django``."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

_DJANGO_SETTINGS = '''"""Django settings for reflex-django (local / production).

Set ``DJANGO_SECRET_KEY`` in the environment for any non-local deployment.
This module intentionally does **not** set ``REFLEX_DJANGO_AUTO_SETTINGS``, so
Reflex will not warn about bundled defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-for-production",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") not in {"0", "false", "False"}

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

USE_I18N = True
LANGUAGE_CODE = "en-us"

REFLEX_DJANGO_ADMIN_PREFIX = "/admin"
REFLEX_DJANGO_CONTEXT_PROCESSORS: tuple[str, ...] = ()
REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS = False
REFLEX_DJANGO_LOGIN_URL = "/login"
REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS = False
REFLEX_DJANGO_I18N_EVENT_BRIDGE = True

REFLEX_DJANGO_AUTH = {
    "ENABLED": True,
    "SIGNUP_ENABLED": True,
    "PASSWORD_RESET_ENABLED": True,
    "LOGIN_URL": "/login",
    "SIGNUP_URL": "/register",
    "PASSWORD_RESET_URL": "/password-reset",
    "PASSWORD_RESET_CONFIRM_URL": "/password-reset/confirm/[uid]/[key]",
    "LOGIN_REDIRECT_URL": "/",
    "LOGOUT_REDIRECT_URL": "/login",
    "SIGNUP_REDIRECT_URL": "/login",
    "REDIRECT_AUTHENTICATED_USER": "/",
    "LOGIN_FIELDS": ["username"],
    "EMAIL_REQUIRED": False,
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@localhost"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
    "reflex_django",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "reflex_django.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = str(BASE_DIR / ".reflex-django" / "staticfiles")
'''

_RXCONFIG = '''import reflex as rx
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="{app_name}",
    plugins=[
        ReflexDjangoPlugin(
            settings_module="django_settings",
            install_event_bridge=True,
        ),
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
'''

_README = '''# {title}

Starter [Reflex](https://reflex.dev) app with [reflex-django](https://pypi.org/project/reflex-django/) — Django ORM, sessions, and **Django admin** on the **same ASGI process** as your Reflex UI.

## What you get

- `rxconfig.py` — `ReflexDjangoPlugin(settings_module="django_settings")` plus Sitemap and Tailwind v4 plugins
- `django_settings.py` — production-style Django settings (no bundled auto-settings warning)
- `{app_name}/{app_name}.py` — home page, canned auth pages (`/login`, `/register`, password reset), and a link to `/admin`
- `.env.example` — copy to `.env` and adjust for deployment

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## First run

```bash
uv sync
uv run reflex-django createsuperuser
uv run reflex run
```

Then open the URL printed for Reflex. Use **`/login`** or **`/register`** for session auth (same users as `/admin`), or visit **`/admin`** on the same host (create a superuser first).

## Django commands

```bash
uv run reflex-django migrate
uv run reflex-django makemigrations
uv run reflex-django shell
```

Or, with reflex-django’s Reflex CLI hook installed: `reflex django migrate`, etc.

## Production

- Set `DJANGO_SECRET_KEY` (see `.env.example`) and `DJANGO_DEBUG=0`
- Tighten `DJANGO_ALLOWED_HOSTS`
- Run `uv run reflex-django collectstatic` when serving with `DEBUG=False`

## Docs

See the [reflex-django README](https://github.com/reflex-dev/reflex/tree/main/packages/reflex-django) for routing, auth bridge, and more.
'''

_ENV_EXAMPLE = '''# Copy to ".env" and load with your process manager or direnv.
# reflex-django reads these via Django settings (see django_settings.py).

# Required in production — use a long random string.
# DJANGO_SECRET_KEY=

# 1 for local dev, 0 in production.
# DJANGO_DEBUG=1

# Comma-separated hostnames when DEBUG=0.
# DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
'''

_APP_PY = '''"""Starter Reflex UI for {app_name} (reflex-django)."""

from __future__ import annotations

import reflex as rx

from reflex_django.auth import add_auth_pages, routes
from reflex_django.auth.state import DjangoAuthState


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Welcome to reflex-django", size="9"),
            rx.cond(
                DjangoAuthState.is_authenticated,
                rx.vstack(
                    rx.hstack(
                        rx.text("Signed in as"),
                        rx.text(DjangoAuthState.username, weight="bold"),
                        rx.text("."),
                        spacing="1",
                        align="center",
                    ),
                    rx.button("Log out", on_click=DjangoAuthState.logout, variant="soft"),
                    spacing="2",
                    align="center",
                ),
                rx.vstack(
                    rx.text("You are not signed in."),
                    rx.link("Sign in →", href=routes.LOGIN_ROUTE),
                    rx.link("Create account →", href=routes.SIGNUP_ROUTE),
                    spacing="1",
                    align="center",
                ),
            ),
            rx.text(
                "Django admin, ORM, and sessions run alongside this Reflex app "
                "in one ASGI process.",
            ),
            rx.link("Open Django admin →", href="/admin", is_external=True),
            rx.text(
                "First time: run ",
                rx.code("uv run reflex-django createsuperuser"),
                " then sign in at ",
                rx.code("/login"),
                " or ",
                rx.code("/admin"),
                ".",
            ),
            rx.text(
                "Edit this page in ",
                rx.code("{app_name}/{app_name}.py"),
                " and your Django settings in ",
                rx.code("django_settings.py"),
                ".",
            ),
            spacing="4",
            align="center",
            max_width="42rem",
        ),
        padding="2rem",
        min_height="100vh",
    )


app = rx.App()
add_auth_pages(app)
app.add_page(index, on_load=DjangoAuthState.sync_from_django)
'''

_GITIGNORE_EXTRA = """
# Django / reflex-django
db.sqlite3
.reflex-django/

# Env
.env
.env.*.local

# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Reflex / uv
.web/
.states/
.venv/
"""


def _dist_name_from_app(app_name: str) -> str:
    """Turn ``my_app`` into a hyphenated distribution name ``my-app``."""
    return app_name.replace("_", "-")


def _pyproject_toml(*, dist_name: str, editable_relative: str | None) -> str:
    lines = [
        "[project]",
        f'name = "{dist_name}"',
        'version = "0.1.0"',
        'description = "Reflex + Django app (reflex-django starter)."',
        'readme = "README.md"',
        "requires-python = \">=3.12\"",
        "dependencies = [",
        '    "reflex>=0.9.2,<1.0",',
        '    "reflex-django",',
        "]",
        "",
    ]
    if editable_relative is not None:
        lines.extend(
            [
                "[tool.uv.sources]",
                f'reflex-django = {{ path = "{editable_relative}", editable = true }}',
                "",
            ]
        )
    return "\n".join(lines)


def _uv_exe() -> str:
    exe = shutil.which("uv")
    if not exe:
        raise click.ClickException(
            "The `uv` executable was not found on PATH. Install uv from "
            "https://docs.astral.sh/uv/ — it is required to scaffold a project."
        )
    return exe


def _run_uv(root: Path, *args: str) -> None:
    try:
        subprocess.run(
            [_uv_exe(), *args],
            cwd=root,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise click.ClickException(
            f"Command failed ({e.returncode}): {' '.join([_uv_exe(), *args])!r}"
        ) from e


def _validate_app_name(project_name: str) -> str:
    from reflex.utils import prerequisites

    try:
        return prerequisites.validate_app_name(project_name)
    except Exception as e:
        raise click.ClickException(str(e)) from e


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _append_gitignore(root: Path) -> None:
    gi = root / ".gitignore"
    extra = _GITIGNORE_EXTRA.strip("\n") + "\n"
    if gi.is_file():
        existing = gi.read_text(encoding="utf-8")
        if "db.sqlite3" not in existing:
            gi.write_text(existing.rstrip() + "\n" + extra, encoding="utf-8", newline="\n")
    else:
        _write_text(gi, extra)


def _remove_main_py_if_present(root: Path) -> None:
    """Drop uv's default ``main.py`` so the Reflex app entry is unambiguous."""
    main_py = root / "main.py"
    if main_py.is_file():
        main_py.unlink()


def _write_starter_files(
    root: Path,
    app_name: str,
    *,
    editable_resolved: Path | None,
) -> None:
    dist_name = _dist_name_from_app(app_name)
    title = dist_name.replace("-", " ").title()

    editable_rel: str | None = None
    if editable_resolved is not None:
        editable_rel = Path(
            os.path.relpath(editable_resolved, root.resolve()),
        ).as_posix()

    _write_text(root / "django_settings.py", _DJANGO_SETTINGS)
    _write_text(root / "rxconfig.py", _RXCONFIG.format(app_name=app_name))
    _write_text(
        root / "pyproject.toml",
        _pyproject_toml(dist_name=dist_name, editable_relative=editable_rel),
    )
    _write_text(
        root / "README.md",
        _README.format(title=title, app_name=app_name),
    )
    _write_text(root / ".env.example", _ENV_EXAMPLE)

    app_dir = root / app_name
    app_py = app_dir / f"{app_name}.py"
    if app_py.is_file():
        _write_text(app_py, _APP_PY.format(app_name=app_name))
    else:
        app_dir.mkdir(parents=True, exist_ok=True)
        _write_text(app_py, _APP_PY.format(app_name=app_name))

    # Reflex imports ``<app>.<app>``; ``<app>`` must be a proper package.
    init_py = app_dir / "__init__.py"
    if not init_py.is_file():
        _write_text(
            init_py,
            f'"""Reflex application package for `{app_name}`."""\n',
        )

    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    gitkeep = assets / ".gitkeep"
    if not gitkeep.is_file():
        _write_text(gitkeep, "")


def run_reflex_django_init(
    project_name: str,
    *,
    editable_reflex_django: Path | None = None,
) -> Path:
    """Create ``./project_name`` with uv, Reflex, reflex-django, and a full starter tree.

    Args:
        project_name: Reflex / Python app name (validated like ``reflex init``).
        editable_reflex_django: If set, ``uv add --editable <path>`` is used
            instead of installing ``reflex-django`` from PyPI. The same path is
            written into ``pyproject.toml`` under ``[tool.uv.sources]``.

    Returns:
        Path to the new project root.
    """
    app_name = _validate_app_name(project_name)
    root = Path.cwd() / app_name
    if root.exists():
        raise click.ClickException(f"Refusing to init: directory already exists: {root}")

    root.mkdir(parents=False)

    editable_resolved: Path | None = None
    if editable_reflex_django is not None:
        editable_resolved = editable_reflex_django.resolve()
        if not editable_resolved.is_dir():
            raise click.ClickException(
                f"--editable-reflex-django is not a directory: {editable_resolved}"
            )

    _run_uv(root, "init", "--name", app_name.replace("-", "_"))
    _run_uv(root, "add", "reflex>=0.9.2,<1.0")
    if editable_resolved is not None:
        _run_uv(root, "add", "--editable", str(editable_resolved))
    else:
        _run_uv(root, "add", "reflex-django")
    _run_uv(
        root,
        "run",
        "reflex",
        "init",
        "--template",
        "blank",
        "--name",
        app_name,
    )

    _remove_main_py_if_present(root)
    _write_starter_files(root, app_name, editable_resolved=editable_resolved)
    _append_gitignore(root)

    _run_uv(root, "lock")
    _run_uv(root, "run", "reflex-django", "migrate", "--noinput")
    return root


def main_argv_init(argv: list[str]) -> None:
    """Handle ``reflex-django init ...`` from :func:`reflex_django.cli.main`."""
    if not argv:
        raise click.ClickException(
            "Missing project name: reflex-django init <project_name> "
            "[--editable-reflex-django PATH]"
        )

    name = argv[0]
    editable: Path | None = None
    i = 1
    while i < len(argv):
        if argv[i] == "--editable-reflex-django" and i + 1 < len(argv):
            editable = Path(argv[i + 1])
            i += 2
            continue
        raise click.ClickException(f"Unknown argument: {argv[i]!r}")

    root = run_reflex_django_init(name, editable_reflex_django=editable)
    click.echo(f"Created starter Reflex + Django project at {root}")
    click.echo("")
    click.echo(f"  cd {root.name}")
    click.echo("  uv sync")
    click.echo("  uv run reflex-django createsuperuser")
    click.echo("  uv run reflex run")
    click.echo("")
    click.echo("Then open the app URL: use /login for Reflex session auth or /admin (same origin).")


def reflex_django_init_entry() -> None:
    """``python -m reflex_django.init_project`` (optional debugging entry)."""
    try:
        main_argv_init(sys.argv[1:])
    except click.ClickException as e:
        click.echo(f"Error: {e!s}", err=True)
        raise SystemExit(2) from e


if __name__ == "__main__":
    reflex_django_init_entry()
