---
level: beginner
tags: [reflex, onboarding]
---

# How Reflex works in 5 minutes

**What you'll learn:** Reflex vocabulary (components, state, events, pages, compilation) so the rest of these docs make sense without opening reflex.dev for every term.

**When you need this:**

- You have only written Django (or other server-rendered stacks) and Reflex is new.
- You want a short primer before reading about AppState and the event bridge.

---

If you have built Reflex before, skim and move on. Everyone else: welcome to UI in Python.

---

## The big idea

Reflex lets you build a web UI in pure Python. You write functions that return components and classes that hold state. Reflex compiles that to a real React app.

When a user opens your site:

1. The browser loads a **compiled SPA** (HTML/JS that Reflex generated).
2. The SPA opens a **WebSocket** to your server. Clicks and form changes flow over that one connection.

```text
   First load           Every interaction after
   ──────────           ───────────────────────

   HTML/JS               WebSocket
   ─────────►            ◄─────────►
   from server           clicks go up, state diffs come down
```

A WebSocket is one persistent connection instead of a new HTTP request per click.

---

## Components

A Reflex component is a Python function returning `rx.Component`:

```python
import reflex as rx

def hello() -> rx.Component:
    return rx.vstack(
        rx.heading("Hello!"),
        rx.text("Welcome to my app."),
        rx.button("Click me"),
    )
```

`rx.vstack`, `rx.heading`, `rx.text`, `rx.button` are component builders. Compose them by nesting. Functions in, components out.

---

## State

**State** is like the JavaScript behind your HTML. A state class inherits from `rx.State`:

```python
class CounterState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1
```

1. `count: int = 0` is a **reactive variable**. Change it on the server, the UI updates.
2. `increment` is an **event handler** the client can call.

Wire it to a component:

```python
def counter_ui() -> rx.Component:
    return rx.vstack(
        rx.text(f"Count: {CounterState.count}"),
        rx.button("Add one", on_click=CounterState.increment),
    )
```

Click the button, the browser sends an event, `increment` runs, `count` changes, the text updates. No hand-written JavaScript.

---

## Pages

A page is a component with a route. In reflex-django, use `@page`:

```python
from reflex_django.pages.decorators import page

@page(route="/counter", title="Counter")
def counter_page() -> rx.Component:
    return counter_ui()
```

Put page functions in your Django app's `views.py`:

```python
--8<-- "snippets/minimal_views.py"
```

Same idea as `@rx.page`, with Django-friendly extras from reflex-django.

---

## The event loop

```text
1. Browser:   user clicks "Add one"
2. Browser:   send event { handler: "CounterState.increment", args: [] } over WebSocket
3. Server:    Reflex finds the CounterState instance for this tab
4. Server:    runs CounterState.increment() (self.count += 1)
5. Server:    sends { CounterState.count: 1 } back
6. Browser:   React re-renders; "Count: 0" becomes "Count: 1"
```

You only wrote step 4. Reflex handles the rest.

---

## Async handlers

Event handlers can be `async def`. Use async when you talk to Django's async ORM:

```python
class TaskState(rx.State):
    tasks: list[dict] = []

    @rx.event
    async def load(self):
        self.tasks = [
            {"title": t.title}
            async for t in Task.objects.all()
        ]
```

In reflex-django, subclass `AppState` instead of `rx.State` when you need `self.request.user`.

---

## The compiled SPA

Reflex does not run your Python in the browser. It **compiles** Python into a React app on disk (`.web/` and `STATIC_ROOT/_reflex/`).

- `python manage.py run_reflex` rebuilds and serves through Django.
- In production, `python manage.py export_reflex` in CI, then Django serves static files.

Something is always compiled. When you change Python, the compile step runs again.

---

## Where Reflex stops

Plain Reflex events do not automatically include:

- A real `HttpRequest`
- `settings.MIDDLEWARE`
- `request.user`, `csrf_token`, `messages`, `request.session`

The data is often in the cookies. Nothing inside Reflex unpacks it for you.

**reflex-django closes that gap.** It rebuilds an `HttpRequest` per event, runs middleware, and hands you `AppState` with `self.request`, `self.user`, and `self.session`.

---

## You now know enough

If these four bullets feel obvious, you are ready for the bridge page:

- A Reflex app is a compiled SPA talking over a WebSocket.
- Components are Python functions returning `rx.Component`.
- State holds reactive fields and `@rx.event` methods.
- Pages are components with a route (`@page` in reflex-django).

Official Reflex docs: [reflex.dev](https://reflex.dev).

---

## What just happened?

You learned how Reflex compiles Python to a SPA, how state and events update the UI, and where plain Reflex stops (no Django context).

**Next up:** [How the two fit together →](../overview/concepts.md)
