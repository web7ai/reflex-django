# Documentation style guide (maintainers)

Not published on the docs site.

## Voice

- Talk to the reader directly ("you") in a calm, confident tone.
- Short paragraphs (2-4 sentences). One idea per section.
- Active verbs: "Run", "Add", "Open".
- No em dashes. Use commas, periods, or parentheses.
- Sound like a helpful colleague, not a framework spec or changelog.
- No internal Python function or class names on Learn pages. Advanced pages may name APIs users import.

## Structure

Linear **Learn** path (do not duplicate across pages):

1. Integration
2. Embed
3. Mount
4. Proxy
5. Bridge

Optional **Tutorial** (quickstart). **Advanced** for pages, serializers, model state, database, auth, bridge utilities, i18n, uploads, CLI, deploy, troubleshooting, scaling, config reference.

No migration docs, legacy settings, internals pages, or v3/v4 references.

## Page length

- **README.md:** ~60 lines. Profile example, run steps, link to Learn path.
- **docs/index.md:** ~55 lines. Same profile example, learning path cards.
- **Learn pages:** ~40-70 lines each. End with **Next:** link.
- **Advanced pages:** task-focused, no boilerplate blocks.

## Page template

```markdown
# Page title

Opening paragraph: what this page helps you do.

## Section name
Body with code and occasional !!! tip / !!! warning (max 2 per page unless troubleshooting).

**Next:** [Next step](path.md)
```

Do not use "What you will learn", "What just happened?", or "Next up" blocks.

## Code

- Use `--8<-- "snippets/..."` when a snippet exists.
- Lead with `profile: "integrated"` in examples unless the page is about another profile.
- Standard imports: `AppState`, `ModelState`, `ReflexDjangoModelSerializer`, `app.add_page`, `@page` (optional), `add_auth_pages`, `ReflexDjangoPlugin`.

## Internal links

Use `.md` paths so MkDocs validates and rewrites them. Examples:

- From `docs/index.md`: `[Integration](learn/integration.md)`
- From nested pages: `[Embed](../learn/embed.md)`, `[Config](../advanced/config.md)`
- Section indexes: `[Advanced](advanced/index.md)` or `[Learn](../learn/index.md)` (not `advanced/` or `learn/`)
- Anchors: `[Option B](../advanced/pages-and-state.md#option-b-page-in-viewspy-optional)`

Published URLs still use directory paths (`/learn/integration/`) when `use_directory_urls` is on.

## Card grids

Use markdown links with `{ .rd-card }` inside a `markdown="1"` container so MkDocs rewrites hrefs. See `docs/index.md` for the home page pattern.

## Plugin-first configuration

Integration config lives in `ReflexDjangoPlugin` inside `rxconfig.py`. Django `settings.py` is for app setup (middleware, database, auth branding, cache, mirror toggles). Document tuning `RX_*` settings on [advanced/config.md](advanced/config.md) only. Do not document legacy flat mount keys that duplicate plugin pillars.

## Deduplication

- Each integration piece is explained once on its Learn page.
- Config key tables live only on [advanced/config.md](advanced/config.md).
- Split dev details live on [learn/proxy.md](learn/proxy.md).
