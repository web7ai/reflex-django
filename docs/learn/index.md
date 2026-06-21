# Learn reflex-django

Follow these steps in order. Each page covers one integration piece. The default `integrated` profile turns all of them on.

## Checklist

1. [Integration](integration.md) - install, wire Django, run `reflex run`
2. [Profiles](profiles.md) - choose `integrated`, `split_dev`, or `reflex_only`
3. [Embed](embed.md) - Django admin and API inside the Reflex backend
4. [Mount](mount.md) - URL prefixes and the SPA catch-all
5. [Proxy](proxy.md) - port 3000 dev wiring
6. [Bridge](bridge.md) - `request.user` in your handlers

Optional: [Tutorial](quickstart.md) - build a todo app with auth and the ORM.

## Profiles

Pick a preset in `rxconfig.py` instead of tuning each pillar by hand. See [Profiles](profiles.md) for the comparison table, examples, override patterns, and validation rules.

**Next:** [Integration](integration.md)
