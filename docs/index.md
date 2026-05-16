# reflex-django documentation

**reflex-django** is a [Reflex](https://reflex.dev) plugin that runs a **Django ASGI** application and your **Reflex** app in **one process** under `reflex run`. Django handles ORM, admin, sessions, and HTTP routes on configured path prefixes; Reflex handles the reactive UI and Socket.IO events.

This documentation is written for **Python and Django developers** who want full-stack applications without maintaining separate dev servers for every local workflow.

**Author:** Mohannad Irshedat  
**Versions:** Python 3.12+, Django 6.0.x, Reflex 0.9.2+ (see `pyproject.toml` in the package).

---

## Choose your path

| You are… | Start here |
|----------|------------|
| Starting a new project from scratch | [Quickstart](quickstart.md) |
| Adding Reflex to an existing Django codebase | [Existing Django project](existing_django_project.md) |

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
15. [Reactive ModelState](reactive_model_state.md) — `ModelState[M]` + canonical ORM API  
16. [CRUD with mixins and states](crud_with_mixins_and_states.md) — `ModelCRUDView` / BlogPost  
17. [Forms and validation](forms_and_validation.md)  
18. [Authentication](authentication.md)  
19. [API integration](api_integration.md) — Django HTTP under `backend_prefix`  
20. [CLI](cli.md) — `reflex django` and `reflex-django`  
21. [Deployment](deployment.md)  
22. [Testing](testing.md)  
23. [Best practices](best_practices.md)  
24. [FAQ](faq.md)

---

## I want to…

| Goal | Page |
|------|------|
| Wire Django settings and prefixes | [Configuration](configuration.md) |
| Run migrations | [CLI](cli.md) |
| Use Django session auth in Reflex events (`AppState`, `login`, `has_perm`) | [Authentication](authentication.md) |
| Understand state: plain Reflex vs helpers | [State management](state_management.md) |
| Build a list/create/edit UI for a model | [Reactive ModelState](reactive_model_state.md), [CRUD with mixins](crud_with_mixins_and_states.md), or [CRUD without mixins](crud_without_mixins.md) |
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
