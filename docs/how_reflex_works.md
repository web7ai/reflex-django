# How Reflex works in 5 minutes

If you've used Reflex before, skim this and move on. If you've only ever written Django (or your usual stack is FastAPI / Flask / something server-rendered), this page is for you. By the end you'll know enough Reflex vocabulary to read the rest of these docs without looking things up.

---

## The big idea

Reflex lets you build a web UI in pure Python. You don't write React, you don't write JSX, you don't write CSS in a separate folder. You write Python functions that *return components*, and Python classes that hold *state*. Reflex compiles all of that to a real React app.

So when a user opens your site, two things are happening:

1. The browser loads a **compiled SPA** (single-page app — a folder of HTML/JS that Reflex generated from your code).
2. The SPA opens a **WebSocket** to your server. From then on, every click, every form change, every navigation flows over that one connection.

```text
   First load           Every interaction after
   ──────────           ───────────────────────

   HTML/JS               WebSocket
   ─────────►            ◄─────────►
   from server           clicks go up, state diffs come down
```

A WebSocket is just one persistent connection. Instead of making a new HTTP request for every action, the browser and server keep talking on the same line.

---

## Components — functions that return UI

A Reflex component is a Python function that returns an `rx.Component`:

```python
import reflex as rx

def hello() -> rx.Component:
    return rx.vstack(
        rx.heading("Hello!"),
        rx.text("Welcome to my app."),
        rx.button("Click me"),
    )
```

`rx.vstack`, `rx.heading`, `rx.text`, `rx.button` are component builders. They look like HTML elements but they're plain Python. You compose them by passing them as arguments.

That's the whole component layer. Functions in, components out.

---

## State — Python classes that hold your app's data

If components are like HTML, **state** is like the JavaScript that backs them. A state is a Python class that inherits from `rx.State`:

```python
class CounterState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1
```

Two things to notice:

1. `count: int = 0` is a **reactive variable**. When you change it on the server, the UI updates automatically.
2. `increment` is decorated with `@rx.event`. That means it's an **event handler** — a method the client can call.

Wire it to a component:

```python
def counter_ui() -> rx.Component:
    return rx.vstack(
        rx.text(f"Count: {CounterState.count}"),
        rx.button("Add one", on_click=CounterState.increment),
    )
```

Click the button → the browser sends an event over the WebSocket → `increment` runs on the server → `self.count` changes → Reflex sends the new value back → the text updates. You wrote no JavaScript.

---

## Pages — components that get a URL

A page is just a component decorated with `@rx.page` (or, in `reflex-django`, `@page`):

```python
@rx.page(route="/counter", title="Counter")
def counter_page() -> rx.Component:
    return counter_ui()
```

Visit `/counter` and you see the page. The client-side router handles navigation between pages without a full reload.

In `reflex-django`, you put these page functions directly inside your Django app's `views.py`:

```python
# shop/views.py
from reflex_django.pages.decorators import page

@page(route="/", title="Home")
def home() -> rx.Component:
    return rx.heading("Hello")
```

That's the same idea as `@rx.page`, just with a small default layout wrapper around your content.

---

## The event loop, end to end

Here's what actually happens when a user clicks a button:

```text
1. Browser:   user clicks "Add one"
2. Browser:   send event { handler: "CounterState.increment", args: [] } over WebSocket
3. Server:    Reflex finds the CounterState instance for this user/tab
4. Server:    runs CounterState.increment() (self.count += 1)
5. Server:    notices count changed, sends { CounterState.count: 1 } back
6. Browser:   React re-renders; "Count: 0" becomes "Count: 1"
```

You only wrote step 4. Reflex handled the rest.

---

## Async event handlers

Event handlers can be `async def`. This matters a lot for `reflex-django` because Django's async ORM methods need an async context:

```python
class TaskState(rx.State):
    tasks: list[dict] = []

    @rx.event
    async def load(self):
        # async iteration over the database
        self.tasks = [
            {"title": t.title}
            async for t in Task.objects.all()
        ]
```

Use `async def` whenever you talk to the database.

---

## The compiled SPA — built once, served from disk

Reflex doesn't run your Python in the browser. Before your app can serve users, Reflex **compiles** your Python into a real React app and writes it to disk. There's an `.web/` folder where the source lives and a built bundle that gets shipped.

In `reflex-django`:

- `python manage.py run_reflex` rebuilds the bundle and serves it through Django.
- In production, you run `python manage.py export_reflex` in CI and Django serves the static files from `STATIC_ROOT/_reflex/`.

You don't have to think about this most of the time. Just know that *something is compiled*, so when you change a Python file, that compile step runs again.

---

## Where Reflex stops, and where the gap lives

Notice what's *not* in this story:

- No `HttpRequest`. The WebSocket payload has the path, query string, and a few headers — but no real Django request object.
- No middleware. Reflex doesn't know what `settings.MIDDLEWARE` is.
- No `request.user`. Reflex has its own state, but it doesn't know about Django auth.
- No `csrf_token`, no `messages`, no `request.session`.

That's why every `@rx.event` handler in plain Reflex is "blind" to your Django world. The data is right there in the cookies — but nothing inside Reflex unpacks it.

**This is the gap `reflex-django` closes.** It rebuilds a real `HttpRequest` for each event, runs your full middleware chain, and hands the result to your handler as `self.request`, `self.user`, `self.session`, and friends.

---

## You now know enough Reflex

If the four bullets below feel obvious, you're ready for the rest of these docs:

- A Reflex app is a compiled SPA that talks to the server over a WebSocket.
- Components are Python functions returning `rx.Component`.
- State is a Python class with reactive fields and `@rx.event` methods.
- Pages are components with a `@rx.page` (or `@page`) decorator and a `route`.

The full official Reflex docs live at [reflex.dev](https://reflex.dev). For our purposes, the page above is plenty.

---

**Next:** [How the two fit together →](how_they_fit.md)
