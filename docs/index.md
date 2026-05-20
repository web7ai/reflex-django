<style>
.md-content .md-typeset h1 { display: none; }
</style>

<p align="center">
  <a href="https://github.com/mohannadirshedat/reflex-django">
    <img src="assets/logo.png" alt="reflex-django logo" width="220" style="border-radius: 16px; margin-bottom: 8px;">
  </a>
</p>

<p align="center">
  <a href="https://github.com/mohannadirshedat/reflex-django">
    <h1 align="center" style="border-bottom: none; font-size: 3.2rem; font-weight: 850; margin-bottom: 0px; background: linear-gradient(135deg, #3f51b5, #00b0ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px; font-family: 'Outfit', sans-serif;">reflex-django</h1>
  </a>
</p>

<p align="center">
    <em>Unify the robust backend power of Django and the highly interactive, Python-first reactive UI of Reflex into a single process.</em>
</p>


<p align="center">
<a href="https://pypi.org/project/reflex-django">
    <img src="https://img.shields.io/pypi/v/reflex-django?color=%2334D058&label=pypi%20package" alt="PyPI package">
</a>
<a href="https://pypi.org/project/reflex-django">
    <img src="https://img.shields.io/pypi/pyversions/reflex-django.svg" alt="Supported Python Versions">
</a>
<a href="https://github.com/mohannadirshedat/reflex-django/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/mohannadirshedat/reflex-django.svg?color=blue" alt="License">
</a>
</p>

---

Welcome to the official documentation for **reflex-django**! 

This library acts as a bridge that brings **Django ASGI** and **Reflex** together in **one process** started by the single standard command: `reflex run`. 

By combining the strength of Django's robust ecosystem (its ORM, administrative panel, session store, migration framework, and URL routing) with Reflex's fast, modern, reactive user interfaces, you get a premium developer experience. You no longer need to run, configure, and maintain separate backend and frontend development servers.

Whether you are starting a new greenfield application or looking to mount a highly interactive modern web interface onto an existing enterprise Django codebase, **reflex-django** is built to scale with your architectural needs.

---

## Choose your path

<div class="path-grid">
  <a href="quickstart/" class="path-card">
    <h3>🚀 Starting from Scratch</h3>
    <p>Initialize a new full-stack project combining the power of Django ORM and Reflex reactivity in minutes.</p>
  </a>
  <a href="existing_django_project/" class="path-card">
    <h3>🔌 Existing Django Codebase</h3>
    <p>Seamlessly mount a modern Reflex frontend onto your existing Django enterprise application.</p>
  </a>
</div>

---

## Quick Installation

Get up and running immediately. You can install **reflex-django** directly from PyPI using your favorite package manager:

=== "Using uv (Recommended)"

    ```bash
    uv add reflex-django
    ```

=== "Using pip"

    ```bash
    pip install reflex-django
    ```

---

## Learning Path

We recommend exploring the documentation in this structured sequence to get a complete grasp of the integration:

1. **Foundations**
    * [Introduction](introduction.md) — Core concepts, philosophy, and comparison.
    * [Installation](installation.md) — Dependencies, Django setup, and basic plugin configuration.
    * [Configuration](configuration.md) — Deep dive into the `ReflexDjangoPlugin` arguments and `REFLEX_DJANGO_*` settings.
    * [Project Structure](project_structure.md) — Recommended folder layouts for monorepo development.

2. **Core Architecture**
    * [Architecture Overview](architecture.md) — Single-process dispatching, event bridges, and lifecycle hooks.
    * [Routing & URL Dispatching](routing.md) — Managing paths across Reflex pages and Django prefixes.
    * [API & HTTP Integration](api_integration.md) — Exposing Django REST Framework or standard Django views on `/api`.

3. **State, Context & Auth**
    * [State Management](state_management.md) — Synchronizing states between Python and the browser.
    * [Django Context in Reflex](django_context_to_reflex.md) — Running Django context processors per Socket.IO event.
    * [Django Middleware in Reflex](django_middleware_to_reflex.md) — How the Event Bridge brings `request.user` and session data to your event handlers.
    * [Session Authentication](authentication.md) — Full session authentication, permission decorators, and user sessions.

4. **Database & CRUD Development**
    * [Database Integration](database_integration.md) — Migrations, asynchronous ORM calls, and model structures.
    * [Model Serializers](serializers.md) — Serializing complex Django models into JSON-safe Reflex variables.
    * [CRUD Without Mixins](crud_without_mixins.md) — Step-by-step example of hand-rolled database actions.
    * [ModelState vs ModelCRUDView](model_state_and_crud_view.md) — Choosing between high-level CRUD tools.
    * [Reactive ModelState](reactive_model_state.md) — Using `ModelState` for automatic form generation and live grids.
    * [CRUD with Mixins & States](crud_with_mixins_and_states.md) — Customizing the `ModelCRUDView` workflow.
    * [reflex-django Mixins](reflex_django_mixins.md) — Standard mixin reference library.
    * [Forms & Validation](forms_and_validation.md) — Forms, error reporting, and UI resets.

5. **Ops & Development**
    * [Command Line Interface](cli.md) — Leveraging the `reflex django` wrapper.
    * [Testing Guide](testing.md) — Writing unit and integration tests.
    * [Deployment Guide](deployment.md) — Production configurations, static files, and environment requirements.
    * [Best Practices](best_practices.md) — Guidelines for writing clean, performant, and secure apps.
    * [FAQ](faq.md) — Answers to frequently asked questions.

---

## Core Task Guide

Need to solve a specific problem? Check out these direct guides:

| What do you want to do? | Recommended Guide |
|:---|:---|
| Configure Django settings and paths | [Configuration Guide](configuration.md) |
| Run Django database migrations | [CLI Reference](cli.md) |
| Access Django sessions and `request.user` in event handlers | [Session Authentication](authentication.md) |
| Read raw query parameters (`GET`/`POST`) or cookies in state | [Authentication — Accessing Request](authentication.md#accessing-the-django-request-on-appstate) |
| Create a list, create, edit, or delete UI for a database model | [Reactive ModelState](reactive_model_state.md) or [CRUD Without Mixins](crud_without_mixins.md) |
| Serialize database models into React-friendly dictionaries | [Serializers Reference](serializers.md) |
| Integrate DRF or standard Django HTTP views alongside the SPA | [API & HTTP Integration](api_integration.md) |
| Deploy your unified app to a production server | [Deployment Guide](deployment.md) |
| Debug anonymous user sessions or authentication problems | [FAQ](faq.md) |

---

## Maintainer Docs
To help maintain or contribute to the library:

* [CHANGELOG.md](../CHANGELOG.md) — Full release history.
* [RELEASING.md](../RELEASING.md) — Standard package publishing workflow.
* [README.md](../README.md) — General package overview.

---

**Navigation:** [Introduction →](introduction.md)
