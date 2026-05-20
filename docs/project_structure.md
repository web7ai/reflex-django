# Project Structure

When combining **Reflex** and **Django** into a single monorepo repository, keeping your code organized is essential to prevent dependency cycles and compilation errors. This guide details the recommended structural organization for full-stack apps.

---

## The Monorepo Layout

Below is the standard, production-ready directory tree for a unified `reflex-django` application.

```text
myproject/                         # Git repository root
├── manage.py                      # Django command line management utility
├── rxconfig.py                    # Reflex configuration & Django plugin bootstrapper
├── pyproject.toml                 # Package dependencies (uv or poetry)
│
├── config/                        # Main Django configuration package
│   ├── __init__.py
│   ├── settings.py                # Database, auth, and REFLEX_DJANGO_* settings
│   └── urls.py                    # Root URL pattern dispatcher (/admin, /api)
│
├── shop/                          # A standard Django application app
│   ├── migrations/
│   ├── __init__.py
│   ├── models.py                  # Database models (domain-specific data)
│   ├── views.py                   # Traditional HTTP API views
│   └── serializers.py             # Reflex-safe model serializers
│
└── frontend/                      # Reflex app package (matches rxconfig app_name)
    ├── __init__.py
    ├── frontend.py                # Main router (adds pages and wraps auth)
    ├── layout/                    # Layout templates (navbar, sidebars, headers)
    ├── components/                # Reusable presentation widgets
    └── states/                    # Reactive states (subclassing AppState/ModelState)
```

---

## Key Directory Roles

By dividing the frontend UI code and the backend database code into separate packages, you establish a clean separation of concerns:

| Layer | Directory | Responsibility |
|:---|:---|:---|
| **Django Core** | `config/` | Contains the global settings, database backends, URL patterns, and configurations. |
| **Django Domain** | `shop/` | Contains models, migrations, standard views, test suites, and backend utility methods. |
| **Reflex Entry** | `frontend/frontend.py` | Configures the main `rx.App` instance, defines page routes, and wires global page-load event hooks. |
| **Reflex Layout** | `frontend/layout/` | Contains headers, navbars, responsive shells, and menus shared across different pages. |
| **Reflex Presentation** | `frontend/components/` | Custom UI elements (e.g., product cards, confirmation modals, error alerts) that don't maintain global state. |
| **Reflex Logic** | `frontend/states/` | Houses event handlers, state variables, permissions check routines, and ORM access methods. |

---

## File Responsibilities in a Unified Process

To keep your code clean, stick to these core file responsibilities:

```text
+-------------------+      Starts      +------------------------+
|    rxconfig.py    | -------------->  | configure_django()     |
| (Reflex Config)   |                  | (Initializes Backend)  |
+-------------------+                  +------------------------+
         |                                          |
         v                                          v
+-------------------+                  +------------------------+
| frontend/         |                  | shop/models.py         |
| (Pages & States)  | <=============== | (Database ORM Models)  |
+-------------------+     Queries      +------------------------+
```

* **`rxconfig.py`**: Initializes the `ReflexDjangoPlugin`. It acts as the gateway that boots Django before the first line of Reflex frontend code is evaluated.
* **`frontend/frontend.py`**: Imports individual page modules and registers them using `app.add_page(index)`.
* **`shop/models.py`**: Defines your database schemas. These should remain completely standard Django models, keeping your domain logic separate from Reflex UI logic.
* **`frontend/states/*.py`**: Implements reactive states. You should import Django models inside state files, query them asynchronously, and map results to JSON-safe dictionaries using custom serializers.

---

## Where to Place Serializers

Model serialization bridges the gap between database models and reactive states. 

We recommend placing your **`ReflexDjangoModelSerializer`** classes in a dedicated `serializers.py` file inside each Django application folder (e.g., `shop/serializers.py`). 

This keeps serialization rules close to the database schema, while your frontend states in `frontend/states/` can easily import them.

---

## Static Files Flow

Handling static assets (images, stylesheets, user uploads) is managed dynamically depending on your active runtime environment:

| Mode | Static Engine | Path |
|:---|:---|:---|
| **Development** | Vite Development Proxy + `ASGIStaticFilesHandler` | Served dynamically on the same origin. No build compilation required. |
| **Production** | Shared Outermost ASGI Path Dispatcher | Compiled via `reflex django collectstatic` into `STATIC_ROOT` and served directly from the dispatcher path. |

---

## Next Steps

Now that you are familiar with the recommended Monorepo directory structure:

* Understand how the dispatcher intercepts incoming traffic: Read the [Architecture Overview](architecture.md).
* Configure your project settings: Review the [Configuration Reference](configuration.md).

---

**Navigation:** [← Existing Django Project](existing_django_project.md) | [Next: Architecture →](architecture.md)
