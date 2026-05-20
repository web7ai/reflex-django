# Introduction

Modern web development often forces developers to make a tough choice. You either build a traditional server-rendered application (like Django templates) which is incredibly secure and robust but feels static, or you build a decoupled Single Page Application (SPA) using a frontend framework (like React or Vue) which is highly dynamic but requires you to manage separate servers, configure complex CORS policies, duplicate authentication logic, and maintain a full web API.

**reflex-django** is a first-class bridge designed to eliminate this compromise. It connects **Reflex** (a Python-first framework for building reactive user interfaces) with **Django** (the industry-standard batteries-included Python web framework) into a **single, unified ASGI process** that you manage using a single command line: `reflex run`.

---

## The Core Concept

Under the hood, `reflex-django` mounts the two frameworks side-by-side using an outermost ASGI path dispatcher. Django handles your database models (ORM), administrative dashboard, sessions, migrations, and static HTTP routes, while Reflex manages the dynamic user interface, WebSockets, and state-driven client events.

```text
               +-----------------------------------------+
               |          Single ASGI Process            |
               |                                         |
               |              ASGI Dispatcher            |
               |                     |                   |
        +------+------+       +------+------+            |
        |             |       |             |            |
  Django Routes  Static Assets|       WebSocket Events   |
  (e.g., /admin, /api)        |       (e.g., /_event)    |
        |                     |             |            |
        v                     v             v            |
  Django Core            Static Handler  Reflex Engine   |
  (ORM, Sessions)                             |          |
        |                                     |          |
        +---------> Event Bridge <------------+          |
               (Syncs request.user and session)          |
+--------------------------------------------------------+
```

---

## What reflex-django Is (and Is Not)

To write clean and performant applications, it is essential to understand the boundaries of the framework:

### What It Is:
1. **A Unified Bootstrapper**: When Reflex loads `rxconfig.py`, the plugin calls `configure_django()` immediately. This ensures that Django is fully initialized and its applications, settings, and models are completely loaded before your Reflex code attempts to import them.
2. **An HTTP Path-Prefix Dispatcher**: When web requests arrive at your ASGI server, `reflex-django` intercepts them. Selected paths (like `/admin`, `/api`, and `/static`) are seamlessly routed to Django's ASGI handler. All other requests are directed to the Reflex engine.
3. **A State and Event Bridge**: On every reactive event sent from the browser to Reflex over WebSockets, the **`DjangoEventBridge`** middleware builds a lightweight, synthetic `HttpRequest` representing the active socket session. This makes the Django user object (`request.user`), active session variables, and query parameters safely accessible from your `@rx.event` handlers.

### What It Is Not:
* **A Merged URL Router**: Reflex pages and `/_event/...` endpoints are **not** standard Django views. You cannot map a Reflex component directly inside a Django `urls.py` file, nor can you return a Reflex component from a traditional Django view callable.
* **A Full HTTP Middleware Runner for Socket.IO**: The Event Bridge does not run your entire Django `MIDDLEWARE` stack (such as CSRF protection or third-party security middleware) on every button click. It selectively loads session and authentication data to keep communication fast and lightweight.
* **A Replacement for Server-Side Templates**: If you have legacy Django views or HTML templates, Django will still serve them exactly as before under your configured path prefixes. Reflex serves the SPA (Single Page Application) frontend.

---

## Why Django Developers Choose This Stack

In a pure Reflex application, user interactions are sent to the server as asynchronous WebSocket events. Because these events occur outside Django's traditional HTTP request-response pipeline, standard patterns like accessing `request.user` or the Django session are unavailable. 

By installing **reflex-django**, you bridge this gap. You get the following major benefits:

* **Zero-CORS Development**: Because the frontend and backend share the same origin, you never have to deal with CORS errors, domain alignment, or token-refresh mechanisms during local development.
* **Unified Session State**: If a user logs in via a standard Django login form or the Django admin panel, the WebSocket bridge immediately identifies them. Your Reflex components can dynamically display user-specific data or enforce group-level permissions.
* **Production-Grade ORM**: You get access to the Django ORM, migration engine, and admin dashboard out of the box, with complete support for async operations (`acreate`, `adelete`, `asave`, etc.) directly inside your reactive state handlers.

---

## Architectural Comparison

| Feature | Django + React/Vue | Pure Django Templates | **reflex-django** |
|:---|:---|:---|:---|
| **Ecosystem Maturity** | Exceptionally high | High | **High** (Combines both) |
| **Development Servers** | Two servers (CORS configuration required) | One server | **One server** (Unified dev environment) |
| **Interactivity** | Extremely high | Medium (Requires Custom JS / HTMX) | **Extremely high** (State-driven reactive UI) |
| **Authentication Logic** | Duplicated on front and back | Single-source | **Single-source** (Shares Django session store) |
| **Language Requirements** | Python + JavaScript/TypeScript | Python + minimal JS | **100% Python** |

---

## When to Use reflex-django

> [!TIP]
> **This stack is perfect when:**
>
> * You love the simplicity and security of the Django ORM, migrations, and administrative panel, but want a highly interactive, modern, client-side reactive interface.
> * You want to build full-stack web apps in **pure Python** without learning or maintaining a modern JavaScript build toolchain.
> * You need a single-process deployment profile for local development, staging environments, or simple container deployments.

> [!WARNING]
> **You might want to skip it if:**
>
> * You are building a static web page that only requires traditional server-rendered templates.
> * Your architecture requires Reflex and Django to be hosted on entirely different cloud providers, communicating exclusively over standard token-based JSON APIs.

---

## Next Steps

Now that you understand the core philosophy, let's get you set up:

* For a new project from scratch: Explore the [Installation](installation.md) guide and the [Quickstart](quickstart.md) tutorial.
* For an existing project: Check out the [Existing Django Project](existing_django_project.md) integration guide.

---

**Navigation:** [← Docs Index](index.md) | [Next: Installation →](installation.md)
