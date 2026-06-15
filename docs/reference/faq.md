# FAQ

## Can I add reflex-django to an existing Django project?

Yes. See [Add to an existing Django project](../getting-started/existing_django_project.md).

## Can I keep my Reflex project and add Django?

Yes. Add `ReflexDjangoPlugin` to `rxconfig.py`. See [Plugin path](../getting-started/existing_reflex_project_plugin.md).

## What dev command do I use?

`reflex run` for SPA development. Use `reflex django migrate` or `python manage.py` for Django tasks.

## How do ports work in dev?

Default: Vite on `:3000`, Reflex backend on `:8000`. Django admin/API are mounted in the Reflex backend. Vite proxies backend paths. See [Local development](../getting-started/local_development.md).

## Where is Reflex configured?

In `rxconfig.py` with `rx.Config` and `ReflexDjangoPlugin`. Django `settings.py` is for Django and optional `RX_*` tuning only.

## What is `app_name`?

The `app_name` field in `rx.Config`. It must match `{app_name}/{app_name}.py`.

## How do I deploy?

`reflex export` in CI, `collectstatic`, then serve with Django ASGI. See [Deployment](../operations/deployment.md).

## SPA bundle not found?

Run `reflex run` or `reflex export`. In two-port dev, browse `:3000`.

## Upgrading from v3?

See [v4: Plugin-only integration](migration/v4_plugin_only.md).
