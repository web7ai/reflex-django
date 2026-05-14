"""JSON-safe context for Reflex, driven by Django settings.

Reflex serializes state to the browser, so values must be JSON-serializable.

Processor paths come from either:

- ``settings.REFLEX_DJANGO_CONTEXT_PROCESSORS`` when non-empty (sync or async
  callables; you are responsible for JSON safety), or
- ``TEMPLATES[*].OPTIONS["context_processors"]`` when
  ``REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS`` is ``True`` and the reflex
  list is empty — the same dotted paths as normal Django templates, with
  built-in stripping/adaptation for keys Django commonly adds (``user`` becomes
  a snapshot; ``request``, ``perms``, ``messages`` are omitted; other values
  must pass ``json.dumps`` or they are skipped with a warning).
"""

from __future__ import annotations

import inspect
import json
from importlib import import_module
from typing import Any

import reflex as rx
from reflex_django.auth_state import user_snapshot
from reflex_django.conf import configure_django
from reflex_django.context import current_request, current_user


def builtin_user_context(request: Any) -> dict[str, Any]:
    """Expose a template-shaped ``user`` key as a JSON snapshot.

    Args:
        request: The active Django :class:`~django.http.HttpRequest` (unused;
            the bridge already bound :func:`~reflex_django.current_user`).

    Returns:
        ``{"user": {<user_snapshot fields>}}``.
    """
    del request
    return {"user": user_snapshot(current_user())}


def builtin_i18n_context(request: Any) -> dict[str, Any]:
    """Expose ``LANGUAGE_CODE``, ``LANGUAGE_BIDI``, and ``LANGUAGES`` for Reflex.

    Intended for ``REFLEX_DJANGO_CONTEXT_PROCESSORS`` or for
    ``TEMPLATES`` ``context_processors`` when using template passthrough.
    Values are JSON-serializable.

    Args:
        request: Active Django request; ``LANGUAGE_CODE`` is read when set by
            the locale middleware or the Reflex event bridge.

    Returns:
        Keys ``LANGUAGE_CODE`` (str), ``LANGUAGE_BIDI`` (bool), and
        ``LANGUAGES`` (list of ``[code, label]`` pairs, all strings).
    """
    from django.conf import settings
    from django.utils import translation

    code = getattr(request, "LANGUAGE_CODE", None) or translation.get_language()
    if not code:
        code = str(getattr(settings, "LANGUAGE_CODE", "en") or "en")
    raw = getattr(settings, "LANGUAGES", ()) or ()
    langs = [
        [str(entry[0]), str(entry[1])]
        for entry in raw
        if isinstance(entry, tuple | list) and len(entry) >= 2
    ]
    return {
        "LANGUAGE_CODE": str(code),
        "LANGUAGE_BIDI": bool(translation.get_language_bidi()),
        "LANGUAGES": langs,
    }


def _import_processor(dotted_path: str):
    """Load a callable from a dotted path.

    Args:
        dotted_path: ``'some.module.function_name'``.

    Returns:
        The imported attribute.

    Raises:
        ValueError: If the path is malformed.
        ImportError: If the module or attribute cannot be loaded.
    """
    if "." not in dotted_path:
        msg = f"Invalid processor path {dotted_path!r}"
        raise ValueError(msg)
    module_path, _, attr = dotted_path.rpartition(".")
    module = import_module(module_path)
    return getattr(module, attr)


def template_context_processor_paths() -> tuple[str, ...]:
    """Collect ``context_processors`` from Django template engine configs.

    Only ``django.template.backends.django.DjangoTemplates`` entries are
    considered. Order is preserved; duplicate dotted paths are skipped after
    the first occurrence.

    Returns:
        Tuple of dotted paths suitable for :func:`_import_processor`.
    """
    from django.conf import settings

    paths: list[str] = []
    seen: set[str] = set()
    for cfg in getattr(settings, "TEMPLATES", ()) or ():
        if cfg.get("BACKEND") != "django.template.backends.django.DjangoTemplates":
            continue
        opts = cfg.get("OPTIONS") or {}
        for raw in opts.get("context_processors") or ():
            dotted = str(raw)
            if dotted not in seen:
                seen.add(dotted)
                paths.append(dotted)
    return tuple(paths)


def _json_serializable(value: Any) -> bool:
    """Return True if ``value`` is safe for ``json.dumps`` (no ``default=``).

    Args:
        value: Candidate context value.

    Returns:
        Whether ``json.dumps(value)`` succeeds without a custom encoder.
    """
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


def _sanitize_template_context_chunk(
    chunk: dict[str, Any],
    *,
    request: Any,
) -> dict[str, Any]:
    """Make one template context-processor dict safe for Reflex JSON state.

    Args:
        chunk: Raw mapping from a Django template context processor.
        request: The active request (unused; reserved for future use).

    Returns:
        A shallow mapping with non-serializable template keys removed or
        adapted.
    """
    del request
    from django.http import HttpRequest
    from reflex_base.utils import console

    out: dict[str, Any] = {}
    for key, val in chunk.items():
        if key == "user":
            out[key] = user_snapshot(val)
            continue
        if key == "request" and isinstance(val, HttpRequest):
            continue
        if key in {"perms", "messages"}:
            continue
        if _json_serializable(val):
            out[key] = val
            continue
        console.warn(
            f"reflex-django skipped non-JSON template context key {key!r} "
            f"({type(val).__name__}); use a Reflex-specific processor or "
            "return JSON-safe values."
        )
    return out


def reflex_context_processor_paths() -> tuple[str, ...]:
    """Resolve which dotted paths :func:`collect_reflex_context` should run.

    If ``REFLEX_DJANGO_CONTEXT_PROCESSORS`` is non-empty, those paths win
    (async processors allowed; JSON safety is the caller's responsibility).

    Otherwise, if ``REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS`` is
    ``True``, paths are taken from :func:`template_context_processor_paths`.

    Returns:
        Ordered dotted paths, possibly empty.
    """
    from django.conf import settings

    explicit = getattr(settings, "REFLEX_DJANGO_CONTEXT_PROCESSORS", None) or ()
    if explicit:
        return tuple(str(p) for p in explicit)
    if getattr(settings, "REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS", False):
        return template_context_processor_paths()
    return ()


def reflex_context_processors_use_template_sanitization() -> bool:
    """Return True when running template ``context_processors`` (not explicit).

    Returns:
        ``True`` iff paths come from ``TEMPLATES`` (sanitization is applied).
    """
    from django.conf import settings

    explicit = getattr(settings, "REFLEX_DJANGO_CONTEXT_PROCESSORS", None) or ()
    if explicit:
        return False
    return bool(
        getattr(settings, "REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS", False)
    )


async def collect_reflex_context(request: Any | None) -> dict[str, Any]:
    """Run configured context processors and shallow-merge dicts.

    Args:
        request: Bound Django request, or ``None`` to get an empty context.

    Returns:
        Merged mapping from all processors (later keys override earlier ones).
        Processors that raise are skipped after logging a warning.
    """
    from reflex_base.utils import console

    configure_django()
    if request is None:
        return {}

    paths = reflex_context_processor_paths()
    sanitize = reflex_context_processors_use_template_sanitization()
    setting_label = (
        "TEMPLATES context_processors"
        if sanitize
        else "REFLEX_DJANGO_CONTEXT_PROCESSORS"
    )

    merged: dict[str, Any] = {}
    for dotted in paths:
        try:
            proc = _import_processor(str(dotted))
            if not callable(proc):
                console.warn(f"{setting_label} entry {dotted!r} is not callable.")
                continue
            result = proc(request)
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, dict):
                console.warn(f"{setting_label} entry {dotted!r} did not return a dict.")
                continue
            if sanitize:
                result = _sanitize_template_context_chunk(result, request=request)
            merged.update(result)
        except Exception as ex:
            console.warn(
                f"reflex-django context processor {dotted!r} failed: {ex!r}",
            )
    return merged


class DjangoContextState(rx.State):
    """State holding merged :func:`collect_reflex_context` output."""

    django_context: dict[str, Any] = {}
    django_context_json: str = ""

    @rx.event
    async def load_django_context(self) -> None:
        """Populate :attr:`django_context` from configured processors."""
        import json

        merged = await collect_reflex_context(current_request())
        self.django_context = merged
        self.django_context_json = json.dumps(merged, indent=2, sort_keys=True)


__all__ = [
    "DjangoContextState",
    "builtin_i18n_context",
    "builtin_user_context",
    "collect_reflex_context",
    "reflex_context_processor_paths",
    "reflex_context_processors_use_template_sanitization",
    "template_context_processor_paths",
]
