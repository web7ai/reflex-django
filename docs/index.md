<style>
.md-content .md-typeset h1 { display: none; }
</style>

<p align="center">
  <a href="https://github.com/mohannadirshedat/reflex-django">
    <h1 align="center" style="border-bottom: none; font-size: 3.2rem; font-weight: 850; margin-bottom: 0px; background: linear-gradient(135deg, #3f51b5, #00b0ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px; font-family: 'Outfit', sans-serif;">reflex-django</h1>
  </a>
</p>
<p align="center">
    <em>Run a Django ASGI backend and Reflex app in one unified process. Easy to build, highly interactive.</em>
</p>
<p align="center">
<a href="https://github.com/mohannadirshedat/reflex-django/actions">
    <img src="https://github.com/mohannadirshedat/reflex-django/workflows/pytest/badge.svg" alt="Test Status">
</a>
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

**Documentation**: [https://github.com/mohannadirshedat/reflex-django](https://github.com/mohannadirshedat/reflex-django)

**Source Code**: [https://github.com/mohannadirshedat/reflex-django](https://github.com/mohannadirshedat/reflex-django)

---

**reflex-django** is a [Reflex](https://reflex.dev) plugin that runs a **Django ASGI** application and your **Reflex** app in **one process** under `reflex run`. Django handles the ORM, admin, sessions, and HTTP routes on configured path prefixes; Reflex handles the reactive UI and Socket.IO events.

This documentation is written for **Python and Django developers** who want full-stack applications without maintaining separate dev servers for every local workflow.

**Author:** Mohannad Irshedat  
**Versions:** Python 3.12+, Django 6.0.x, Reflex 0.9.2+ (see `pyproject.toml` in the package).

---

## Choose your path

<div class="path-grid">
  <a href="quickstart.md" class="path-card">
    <h3>🚀 Starting from Scratch</h3>
    <p>Initialize a new full-stack project combining the power of Django ORM and Reflex reactivity in minutes.</p>
  </a>
  <a href="existing_django_project.md" class="path-card">
    <h3>🔌 Existing Django Codebase</h3>
    <p>Seamlessly mount a modern Reflex frontend onto your existing Django enterprise application.</p>
  </a>
</div>

---

## Installation

Install **reflex-django** via pip:

<div class="termy">

```console
$ pip install reflex-django
---> 100%
Successfully installed reflex-django asgiref django reflex
```

</div>

---

## Learning path

1. [Introduction](introduction.md) — what reflex-django is and is not  
2. [Installation](installation.md) — dependencies and plugin wiring  
3. [Configuration](configuration.md) — `ReflexDjangoPlugin` and `REFLEX_DJANGO_*` settings  
4. [Quickstart](quickstart.md) *or* [Existing Django project](existing_django_project.md)  
5. [Project structure](project_structure.md) — recommended layout  
6. [Architecture](architecture.md) — HTTP dispatcher, event bridge, lifecycles  
7. [Routing](routing.md) — Reflex pages and Django URL prefixes  
8. [Django middleware to Reflex](django_middleware_to_reflex.md) — `DjangoEventBridge`  
9. [Django context to Reflex](django_context_to_reflex.md) — processors and `DjangoContextState`  
10. [State management](state_management.md) — `AppState`, `DjangoUserState`, wire format  
    - [Authentication](authentication.md) — `self.user` / `self.session`, login, permissions, decorators  
11. [Serializers](serializers.md) — `ReflexDjangoModelSerializer`  
12. [Database integration](database_integration.md) — migrations, `Model`, ORM backend  
13. [CRUD without mixins](crud_without_mixins.md) — manual Product example  
14. [reflex-django mixins](reflex_django_mixins.md) — mixin catalog and `session_auth_mixin`  
15. [ModelState and ModelCRUDView](model_state_and_crud_view.md) — comparison, examples, when to use each  
16. [Reactive ModelState](reactive_model_state.md) — `ModelState[M]` + canonical ORM API  
17. [CRUD with mixins and states](crud_with_mixins_and_states.md) — `ModelCRUDView` / BlogPost  
18. [Forms and validation](forms_and_validation.md)  
19. [Authentication](authentication.md)  
20. [API integration](api_integration.md) — Django HTTP under `backend_prefix`  
21. [CLI](cli.md) — `reflex django` and `reflex-django`  
22. [Deployment](deployment.md)  
23. [Testing](testing.md)  
24. [Best practices](best_practices.md)  
25. [FAQ](faq.md)

---

## I want to…

| Goal | Page |
|------|------|
| Wire Django settings and prefixes | [Configuration](configuration.md) |
| Run migrations | [CLI](cli.md) |
| Use Django session auth in Reflex events (`AppState`, `login`, `has_perm`) | [Authentication](authentication.md) |
| Use `self.request.user`, `self.request.GET`, Django request in handlers | [Authentication — `self.request`](authentication.md#accessing-the-django-request-on-appstate) |
| Understand state: plain Reflex vs helpers | [State management](state_management.md) |
| Build a list/create/edit UI for a model | [ModelState and ModelCRUDView](model_state_and_crud_view.md), [Reactive ModelState](reactive_model_state.md), [CRUD with mixins](crud_with_mixins_and_states.md), or [CRUD without mixins](crud_without_mixins.md) |
| Understand `ModelState` vs `ModelCRUDView` | [ModelState and ModelCRUDView](model_state_and_crud_view.md) |
| Serialize models for Reflex state | [Serializers](serializers.md) |
| Expose DRF or Django views on `/api` | [API integration](api_integration.md) |
| Deploy to production | [Deployment](deployment.md) |
| Debug `current_user()` or session issues | [FAQ](faq.md), [Django middleware to Reflex](django_middleware_to_reflex.md) |

---

## Maintainer docs

- [CHANGELOG.md](../CHANGELOG.md) — release history  
- [RELEASING.md](../RELEASING.md) — publish workflow  
- [README.md](../README.md) — package overview (links here for depth)

---

**Navigation:** [Introduction →](introduction.md)
