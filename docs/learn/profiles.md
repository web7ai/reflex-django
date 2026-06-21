# Profiles

<p class="rd-page-lead" markdown="1">
Profiles are presets for the four integration pillars in <code>ReflexDjangoPlugin</code>. Pick a profile in <code>rxconfig.py</code> instead of tuning embed, mount, proxy, and bridge by hand. Explicit pillar blocks always override profile defaults.
</p>

Pillar details: [Embed](embed.md) · [Mount](mount.md) · [Proxy](proxy.md) · [Bridge](bridge.md)

## Comparison

<div class="rd-table-wrap" markdown="1">

| Profile | embed | mount | proxy | bridge | Dev commands | Use when |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `integrated` (default) | on | on | on | on | `reflex run` | Most projects. One command, Django admin/API in the Reflex backend. |
| `split_dev` | off | on | on | on | `runserver` + `reflex run` | Debug Django with normal `runserver`, or Django already runs elsewhere. |
| `reflex_only` | off | off | on | off | `reflex run` | Reflex UI only. No Django HTTP embedding, mount, or event bridge. |

{: .rd-pillar-table }

</div>

Browse **http://localhost:3000/** in all profiles when proxy is on. Default ports: Vite `3000`, Reflex backend `8000`.

## Profile presets

<div class="rd-profile-grid" markdown="1">

<div class="rd-profile-card rd-profile-card--integrated" markdown="1">

<span class="rd-level rd-level--0">Default</span>

### `integrated`

Default for new projects. Embed runs Django HTTP inside the Reflex backend. Mount adds the SPA catch-all. Proxy wires Vite to the backend. Bridge binds Django request context to Reflex events.

<div class="rd-profile-meta" markdown="1">
<span class="rd-profile-chip rd-profile-chip--on"><span class="rd-profile-chip__key">embed</span> on</span>
<span class="rd-profile-chip rd-profile-chip--on"><span class="rd-profile-chip__key">mount</span> on</span>
<span class="rd-profile-chip rd-profile-chip--on"><span class="rd-profile-chip__key">proxy</span> on</span>
<span class="rd-profile-chip rd-profile-chip--on"><span class="rd-profile-chip__key">bridge</span> on</span>
</div>

```python
--8<-- "snippets/profile_rxconfig.py"
```

```bash
reflex run
```

Use integrated when you want the simplest local workflow and a single integrated production stack (`reflex run --env prod` or Reflex deploy). See [Deploy](../advanced/deployment.md).

</div>

<div class="rd-profile-card rd-profile-card--split-dev" markdown="1">

<span class="rd-level rd-level--2">Split dev</span>

### `split_dev`

Django runs in a separate HTTP process. Vite still serves the Reflex UI on port 3000. Admin and API traffic go to your Django server through `proxy.server`.

<div class="rd-profile-meta" markdown="1">
<span class="rd-profile-chip rd-profile-chip--off"><span class="rd-profile-chip__key">embed</span> off</span>
<span class="rd-profile-chip rd-profile-chip--on"><span class="rd-profile-chip__key">mount</span> on</span>
<span class="rd-profile-chip rd-profile-chip--on"><span class="rd-profile-chip__key">proxy</span> on</span>
<span class="rd-profile-chip rd-profile-chip--on"><span class="rd-profile-chip__key">bridge</span> on</span>
</div>

```python
--8<-- "snippets/profile_split_dev_rxconfig.py"
```

```bash
python manage.py runserver
reflex run
```

`proxy.server` is required at runtime when embed is off. You can also set `RX_PROXY_SERVER` in Django settings or the environment, but explicit `profile: "split_dev"` plus `proxy.server` is clearer for new projects.

Use split dev when you want independent Django and Reflex reload cycles, or when another service already owns Django HTTP.

</div>

<div class="rd-profile-card rd-profile-card--reflex-only" markdown="1">

<span class="rd-level rd-level--3">UI only</span>

### `reflex_only`

Reflex UI development without Django HTTP embedding, automatic mount, or the event bridge. Proxy stays on for normal Vite dev wiring.

<div class="rd-profile-meta" markdown="1">
<span class="rd-profile-chip rd-profile-chip--off"><span class="rd-profile-chip__key">embed</span> off</span>
<span class="rd-profile-chip rd-profile-chip--off"><span class="rd-profile-chip__key">mount</span> off</span>
<span class="rd-profile-chip rd-profile-chip--on"><span class="rd-profile-chip__key">proxy</span> on</span>
<span class="rd-profile-chip rd-profile-chip--off"><span class="rd-profile-chip__key">bridge</span> off</span>
</div>

```python
--8<-- "snippets/profile_reflex_only_rxconfig.py"
```

Use reflex_only when you are prototyping Reflex UI only, or when Django integration is wired manually outside the default pillars.

Handlers will not receive `self.request` or `current_request()` because bridge is off. Re-enable bridge or switch profiles when you need Django auth in events.

</div>

</div>

## Override patterns

Keep a profile and override individual pillars:

```python
ReflexDjangoPlugin(config={
    "settings_module": "config.settings",
    "profile": "integrated",
    "bridge": {"mode": "smart"},
    "mount": {
        "django_prefix": ("/admin", "/api", "/billing"),
    },
})
```

<div class="rd-table-wrap" markdown="1">

| Goal | Override |
| :--- | :--- |
| Faster events on UI-only state | `"bridge": {"mode": "smart"}` |
| External Django in integrated profile | `"embed": {"enabled": False}`, `"proxy": {"server": "http://127.0.0.1:8000"}` |
| Explicit API/admin prefixes | `"mount": {"django_prefix": ("/admin", "/api")}` |
| Native Reflex two-port dev | `"proxy": {"separate_dev_ports": True}` |

{: .rd-pillar-table }

</div>

## Legacy flat keys

These top-level plugin keys still work for upgrades:

<div class="rd-table-wrap" markdown="1">

| Legacy key | Maps to |
| :--- | :--- |
| `auto_mount` | `mount.enabled` |
| `mount_prefix` | `mount.mount_prefix` |
| `django_prefix` | `mount.django_prefix` |

{: .rd-pillar-table }

</div>

Prefer nested `mount` blocks in new projects.

## Validation and warnings

<div class="rd-instructor" markdown="1">

<strong>Startup checks:</strong>

- <strong><code>split_dev</code> without <code>proxy.server</code>:</strong> raises a configuration error. Set <code>proxy.server</code> or <code>RX_PROXY_SERVER</code>.
- <strong><code>embed.enabled=True</code> with <code>proxy.server</code> set:</strong> logs a warning. In-process Django HTTP takes precedence; <code>proxy.server</code> applies only when embed is off.
- <strong><code>bridge.enabled=False</code>:</strong> logs a warning. Reflex events will not bind Django request context.
- <strong>Invalid <code>bridge.mode</code>:</strong> raises a configuration error. Allowed values: <code>full</code>, <code>smart</code>, <code>none</code>.

</div>

Full plugin and Django settings reference: [Config reference](../advanced/config.md).

**Next:** [Embed](embed.md)
