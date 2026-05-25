"""``manage.py export_reflex`` — build the Reflex SPA bundle.

Running plain ``reflex export`` from a reflex-django project fails with
``rxconfig.py not found`` because Reflex's CLI is launched without our
:mod:`reflex_django.integration` hooks, which is what synthesizes
``rxconfig`` from your Django settings and bootstraps the Reflex app from
the Django ``INSTALLED_APPS`` registry.

This management command does the bootstrap first, then drives Reflex's
own export utilities directly. It produces the same artefacts as
``reflex export`` would in a vanilla Reflex project:

- ``.web/_static/`` — compiled SPA (``index.html`` + hashed JS/CSS) that
  :class:`reflex_django.views.mount.ReflexMountView` picks up automatically.
- ``frontend.zip`` and/or ``backend.zip`` in the current directory when
  ``--zip`` is passed (Reflex's default behaviour for ``reflex export``).

Common invocations:

.. code-block:: bash

    # Build the SPA bundle into .web/_static (no zip).
    python manage.py export_reflex --frontend-only --no-zip

    # Build and stage the bundle into STATIC_ROOT/_reflex so the prod
    # ``ReflexMountView`` finds it on its first lookup.
    python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root

    # Full build matching ``reflex export`` defaults (frontend + zips).
    python manage.py export_reflex
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


_DEFAULT_SPA_STATIC_ROOT_SUBDIR = "_reflex"


class Command(BaseCommand):
    """Compile the Reflex SPA bundle (the ``reflex export`` equivalent).

    Unlike ``reflex export`` directly, this command installs the
    reflex-django integration first so the synthetic ``rxconfig`` and
    Django-aware Reflex CLI patches are in place. Use this in your CI/CD
    pipeline before booting the prod ASGI server.
    """

    help = (
        "Compile the Reflex SPA bundle for production "
        "(the reflex-django equivalent of `reflex export`)."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--env",
            choices=["dev", "prod"],
            default="prod",
            help="Build environment (defaults to prod).",
        )
        parser.add_argument(
            "--frontend-only",
            action="store_true",
            help="Export only the frontend (the React/Vite bundle).",
        )
        parser.add_argument(
            "--backend-only",
            action="store_true",
            help="Export only the backend (Python source + requirements).",
        )
        parser.add_argument(
            "--no-zip",
            action="store_true",
            help="Skip creating frontend.zip/backend.zip artefacts.",
        )
        parser.add_argument(
            "--zip-dest-dir",
            dest="zip_dest_dir",
            default=str(Path.cwd()),
            help="Where to write the zipped artefacts (defaults to CWD).",
        )
        parser.add_argument(
            "--no-ssr",
            dest="ssr",
            action="store_false",
            help="Disable Reflex server-side rendering / pre-rendered routes.",
        )
        parser.add_argument(
            "--stage-to-static-root",
            dest="stage_to_static_root",
            action="store_true",
            help=(
                "After the build, copy .web/_static/* into "
                "STATIC_ROOT/_reflex/ so ReflexMountView discovers the SPA "
                "without an extra `collectstatic` step."
            ),
        )
        parser.add_argument(
            "--stage-target",
            dest="stage_target",
            default=None,
            help=(
                "Override the staging destination directory (implies "
                "--stage-to-static-root). Defaults to STATIC_ROOT/_reflex."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # Bootstrap the reflex-django integration BEFORE importing Reflex's
        # export utilities. Otherwise ``reflex.utils.prerequisites`` would
        # look for ``rxconfig.py`` on disk and raise the same error the
        # user hit running ``reflex export`` directly.
        from reflex_django.integration import (
            install_reflex_django_integration,
            refresh_get_config_bindings,
        )

        install_reflex_django_integration()
        refresh_get_config_bindings()

        env = options.get("env") or "prod"
        frontend_only = bool(options.get("frontend_only"))
        backend_only = bool(options.get("backend_only"))
        no_zip = bool(options.get("no_zip"))
        zip_dest_dir = options.get("zip_dest_dir") or str(Path.cwd())
        ssr = options.get("ssr", True)
        stage = bool(options.get("stage_to_static_root")) or bool(
            options.get("stage_target")
        )
        stage_target = options.get("stage_target")

        if frontend_only and backend_only:
            raise CommandError(
                "Pass only one of --frontend-only or --backend-only "
                "(or neither for both)."
            )

        try:
            from reflex.utils import export as export_utils
            from reflex.utils import prerequisites
            from reflex_base import constants
            from reflex_base.utils.console import _LOG_LEVEL  # noqa: PLC2701
        except ImportError as exc:
            raise CommandError(
                "Reflex is not installed in this environment. "
                "Install with `pip install reflex` (or your project pin)."
            ) from exc

        try:
            from reflex_base.config import get_config
        except ImportError:
            get_config = None  # type: ignore[assignment]

        running_mode = prerequisites.check_running_mode(frontend_only, backend_only)

        # ``assert_in_reflex_dir`` is patched by
        # :func:`install_reflex_django_integration` so it always passes in a
        # reflex-django project (the rxconfig is synthetic). Call it anyway
        # for parity with Reflex's CLI semantics.
        try:
            prerequisites.assert_in_reflex_dir()
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Reflex assert_in_reflex_dir failed: {exc!r}") from exc

        loglevel = _LOG_LEVEL
        if get_config is not None:
            try:
                loglevel = get_config().loglevel.subprocess_level()
            except Exception:  # noqa: BLE001
                pass

        self.stdout.write(
            self.style.NOTICE(
                f"reflex-django: exporting (env={env}, "
                f"frontend={running_mode.has_frontend()}, "
                f"backend={running_mode.has_backend()}, "
                f"zip={not no_zip}, ssr={ssr})"
            )
        )

        try:
            export_utils.export(
                zipping=not no_zip,
                frontend=running_mode.has_frontend(),
                backend=running_mode.has_backend(),
                zip_dest_dir=zip_dest_dir,
                env=constants.Env.DEV if env == "dev" else constants.Env.PROD,
                loglevel=loglevel,
                prerender_routes=ssr,
            )
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CommandError(
                f"reflex-django export failed: {exc!r}"
            ) from exc

        if running_mode.has_frontend() and stage:
            target = self._resolve_stage_target(stage_target)
            self._stage_to(target)
        elif running_mode.has_frontend():
            self._print_discovery_hint()

    # ------------------------------------------------------------------
    # Staging helpers
    # ------------------------------------------------------------------

    def _resolve_stage_target(self, override: str | None) -> Path:
        """Return the directory where the compiled SPA should be staged.

        Args:
            override: Explicit ``--stage-target`` argument; takes precedence
                over the default ``STATIC_ROOT/_reflex``.

        Returns:
            An absolute :class:`~pathlib.Path` (created if missing).
        """
        if override:
            return Path(override).resolve()
        try:
            from django.conf import settings

            static_root = getattr(settings, "STATIC_ROOT", None)
        except Exception:  # noqa: BLE001
            static_root = None
        if not static_root:
            raise CommandError(
                "--stage-to-static-root requires `settings.STATIC_ROOT` to be set. "
                "Either set STATIC_ROOT in your Django settings or pass "
                "--stage-target=<path> explicitly."
            )
        return Path(static_root).resolve() / _DEFAULT_SPA_STATIC_ROOT_SUBDIR

    def _stage_to(self, target: Path) -> None:
        """Copy the compiled SPA tree into *target* so ``ReflexMountView`` finds it.

        Source is whichever of ``.web/build/client`` (SSR), ``.web/_static``
        (no-SSR), or ``.web/build`` (legacy) contains an ``index.html``.
        Pre-rendered routes (``about.html``, ``items.html``,
        ``__spa-fallback.html``, …) and the ``assets/`` bundle directory are
        all copied verbatim — they coexist with ``index.html`` in the staged
        tree so the mount view can pick the right HTML per request path.
        """
        source = self._resolve_build_dir()
        if source is None:
            raise CommandError(
                "Could not locate the built SPA directory. Expected "
                "`.web/build/client`, `.web/_static`, or `.web/build` to "
                "contain an `index.html` after export."
            )
        target.mkdir(parents=True, exist_ok=True)
        # Wipe stale files in the target so old hashed bundles do not
        # accumulate across builds.
        for entry in target.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        # Copy contents (not the directory itself) into ``target``.
        for entry in source.iterdir():
            dest = target / entry.name
            if entry.is_dir():
                shutil.copytree(entry, dest)
            else:
                shutil.copy2(entry, dest)
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: staged SPA -> {target}"
            )
        )
        self.stdout.write(
            self.style.NOTICE(
                "    Run `python manage.py collectstatic --noinput` to merge "
                "Django admin/DRF assets alongside it."
            )
        )

    @staticmethod
    def _resolve_build_dir() -> Path | None:
        """Return the directory that contains the compiled SPA's ``index.html``.

        Reflex's output directory depends on whether SSR is enabled:

        - ``--no-ssr`` and pre-SSR Reflex versions: ``.web/_static/index.html``.
        - SSR enabled (the new default): Vite writes to ``.web/build/client/``
          with pre-rendered pages alongside (``about.html``, ``items.html``,
          ``__spa-fallback.html``, …); the SPA shell is ``client/index.html``.
        - Some older Reflex versions: ``.web/build/index.html`` (no ``client``
          subdir).

        We try each layout in order of "newest Reflex first" so SSR users land
        on the right place, then fall back to the legacy paths.
        """
        web = Path.cwd() / ".web"
        candidates = (
            web / "build" / "client",
            web / "_static",
            web / "build",
        )
        for candidate in candidates:
            if candidate.is_dir() and (candidate / "index.html").is_file():
                return candidate
        return None

    def _print_discovery_hint(self) -> None:
        """Tell the user where ``ReflexMountView`` will look for the bundle."""
        build = self._resolve_build_dir()
        if build is None:
            self.stdout.write(
                self.style.WARNING(
                    "reflex-django: export finished but no index.html was found "
                    "in .web/_static or .web/build. Check Reflex's output above."
                )
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: SPA built at {build}\n"
                "    `ReflexMountView` discovers it automatically. For prod "
                "deployments, pass --stage-to-static-root (or run "
                "`python manage.py collectstatic`) to package it with Django assets."
            )
        )


__all__ = ["Command"]


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    sys.exit(0)
