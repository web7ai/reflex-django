# Documentation style guide (maintainers)

Not published on the docs site.

## Voice

- Friendly instructor, second person ("you")
- Short paragraphs, one idea per section
- No em dashes. Use commas, periods, or parentheses
- At most one light joke per major page

## Page structure

1. What you will learn (one sentence)
2. When you need this (two bullets)
3. Body with !!! tip / !!! warning
4. Copy-paste code (--8<-- snippets when possible)
5. What just happened?
6. Next up (one link)

## Standard imports

- from reflex_django.states import AppState
- from reflex_django.pages.decorators import page
- from reflex_django.asgi_entry import application