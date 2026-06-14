# Documentation style guide (maintainers)

Not published on the docs site.

## Voice

- Talk to the reader directly ("you") in a calm, confident tone.
- Short paragraphs (2-4 sentences). One idea per section.
- Active verbs: "Run", "Add", "Open".
- No em dashes. Use commas, periods, or parentheses.
- Sound like a helpful colleague, not a framework spec or changelog.

## Page template

```markdown
# Page title

Opening paragraph: what this page helps you do, and when to open it.

## Section name (task-based heading)
Body with code and occasional !!! tip / !!! warning (max 2 per page unless troubleshooting).

## See also
- [Related page](path.md)
```

Do not require "What you will learn", "When you need this", "What just happened?", or "Next up" blocks.

## Code

- Use `--8<-- "snippets/..."` when a snippet exists.
- Standard imports in examples:
  - `from reflex_django.states import AppState`
  - `from reflex_django.pages.decorators import page`
  - `from django.core.asgi import get_asgi_application`

## Section indexes

Use `rd-card-grid` / `rd-card` on section hub pages only, not on every guide.
