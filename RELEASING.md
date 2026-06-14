# Releasing `reflex-django` to PyPI

This package is built with [Hatchling](https://hatch.pypa.io/) and published on
PyPI as [**reflex-django**](https://pypi.org/project/reflex-django/).

**Repository layout.** You may be in either place:

- **Standalone checkout** — this directory is the project root (contains
  `pyproject.toml`, `src/reflex_django/`, `reflex_django_tests/`). Use paths
  below with `dist/` next to `pyproject.toml`.
- **Reflex monorepo** — the same package lives under
  `packages/reflex-django/`; adjust `cd` and `pytest` paths accordingly and
  point `uv build --out-dir` at a shared `dist/` if your team uses one.

## Prerequisites

- A [PyPI](https://pypi.org/) account with permission to upload **reflex-django**
  (the first successful upload creates the project).
- A [PyPI API token](https://pypi.org/help/#apitoken). **Username/password uploads
  are no longer supported**; you must use a token (or [trusted
  publishing](https://docs.pypi.org/trusted-publishers/) from CI).

## PyPI authentication

### `uv publish` (recommended)

Set the token in the environment (do not commit it), then publish built files:

```bash
# POSIX
export UV_PUBLISH_TOKEN="pypi-..."   # paste token from PyPI
uv publish dist/reflex_django-x.y.z*
```

```powershell
# Windows PowerShell
$env:UV_PUBLISH_TOKEN = "pypi-..."
uv publish .\dist\reflex_django-x.y.z*
```

Or pass the token once:

```bash
uv publish -t "pypi-..." dist/reflex_django-x.y.z*
```

Publish **both** the wheel and the sdist (`reflex_django-x.y.z*`) so installers
can prefer the wheel.

### `twine upload`

Create a token scoped to this project (or the whole account for the first
release). When `twine` prompts for credentials:

- **Username:** `__token__` (literally, seven characters with two underscores).
- **Password:** the token value (starts with `pypi-`).

For non-interactive use, prefer environment variables supported by your Twine
version, or stick to `uv publish` with `UV_PUBLISH_TOKEN`.

### Trusted publishing (GitHub Actions)

If you [registered a trusted publisher](https://docs.pypi.org/trusted-publishers/)
on PyPI (e.g. repository `yourname/reflex-django`, workflow `release.yml`), uploads
**only work when that workflow runs on GitHub**. Running `uv publish` on your
laptop does **not** receive an OIDC token, so PyPI will not accept “trusted”
uploads from your machine.

In CI, use `uv publish --trusted-publishing always` (see
`.github/workflows/release.yml` in this repo). Trigger by pushing a version tag
such as `v0.1.0` (after `version` in `pyproject.toml` matches), or run the
workflow manually from the Actions tab (`workflow_dispatch`).

**If you publish locally instead**, do not type your PyPI username at the prompt.
Use `UV_PUBLISH_TOKEN` / `uv publish -t`, or interactive username `__token__`
with your **API token** as the password.

## Release checklist

1. **Changelog** — Update `CHANGELOG.md` with the new version and date.
2. **Version** — Set `version = "x.y.z"` in `pyproject.toml` (PEP 440; semantic
   versioning).
3. **Tests** — From the package directory (standalone: `reflex-django/`):

   ```bash
   cd reflex-django   # or: cd packages/reflex-django
   uv run pytest reflex_django_tests -q
   ```

   CI runs the same suite via `.github/workflows/test.yml`.

4. **Build** — From the same directory:

   ```bash
   uv build --out-dir dist
   ```

   Expect `dist/reflex_django-x.y.z.tar.gz` and
   `dist/reflex_django-x.y.z-py3-none-any.whl`.

5. **Check metadata**

   ```bash
   uv tool run twine check dist/reflex_django-x.y.z*
   ```

6. **Upload** — Optional dry run: `uv publish --dry-run dist/reflex_django-x.y.z*`.

   [TestPyPI](https://test.pypi.org/) first if you like (configure a TestPyPI
   token and `--publish-url` / index options per [uv publish
   docs](https://docs.astral.sh/uv/guides/publish/)).

   Production:

   ```bash
   uv publish dist/reflex_django-x.y.z*
   ```

7. **Tag** (optional) — e.g. `git tag reflex-django-x.y.z && git push origin reflex-django-x.y.z`.

## Notes

- **README images on PyPI** — The project description does not resolve
  relative paths like `![](img.png)`. Host the asset in your repo (or
  elsewhere) and use an **absolute** `https://` URL, for example
  `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/img.png`.
- **`dist/`** — Add or keep `dist/` in `.gitignore`; do not commit built
  artifacts.
- **URLs** — In `pyproject.toml`, `project.urls` should match the canonical
  repository and documentation; adjust before publishing a fork under the same
  or a different distribution name.
