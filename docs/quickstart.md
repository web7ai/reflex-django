# Quickstart

This tutorial will guide you through building a brand-new Reflex + Django application from scratch in about 15 minutes. We will create a unified project where Django manages our database, authentication, and admin panel, while Reflex provides a gorgeous reactive frontend.

---

## Prerequisites
Before beginning, make sure you have:
* Python `>= 3.12` installed.
* **`uv`** installed (recommended for fast package installation and virtual environments).

---

## Step 1: Initialize the Project

Create a new directory for your project and initialize it with `uv`. This will set up a virtual environment and a standard python package structure.

<div class="termy">

```console
$ mkdir myapp
$ cd myapp
$ uv init
Initialized project `myapp` at /path/to/myapp

$ uv add reflex reflex-django
---> 100%
Successfully installed reflex and reflex-django
```

</div>

---

## Step 2: Scaffold the Reflex Frontend

Now, use the Reflex CLI tool to initialize the frontend structure. We will name the Reflex module `frontend`.

<div class="termy">

```console
$ uv run reflex init frontend
Scaffolding frontend project...
Reflex frontend initialized successfully.
```

</div>

Select the default blank template when prompted. This creates a `frontend` folder containing your UI pages and states, along with an `rxconfig.py` configuration file.

---

## Step 3: Scaffold the Django Backend

Next, create the Django backend project directly inside the root folder:

<div class="termy">

```console
$ uv run django-admin startproject backend .
```

</div>

This adds standard Django administration files: `manage.py` in the root, and a `backend/` folder containing `settings.py`, `urls.py`, and `wsgi.py`/`asgi.py`.

Your directory layout should now look like this:

```text
myapp/
├── manage.py
├── pyproject.toml
├── rxconfig.py
├── backend/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
└── frontend/
    ├── __init__.py
    └── frontend.py
```

---

## Step 4: Configure `rxconfig.py` and `settings.py`

Let's connect the frontend and backend. 

### 1. Update the Reflex Configuration
Open `rxconfig.py` and import the `ReflexDjangoPlugin`. We will configure the plugin to point to Django's settings module:

```python
# rxconfig.py
import reflex as rx
from reflex_django import ReflexDjangoPlugin

config = rx.Config(
    app_name="frontend",  # Must match your Reflex code directory
    plugins=[
        ReflexDjangoPlugin(
            settings_module="backend.settings",
            backend_prefix="/api",
            admin_prefix="/admin",
        ),
    ],
)
```

### 2. Update Django Settings
Open `backend/settings.py` and register the `"reflex_django"` application in `INSTALLED_APPS`:

```python
# backend/settings.py

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Add reflex-django helper here
    "reflex_django",
]
```

---

## Step 5: Database Migrations and First Start

Before starting the server, initialize Django's default sqlite database and run the migrations:

<div class="termy">

```console
$ uv run reflex django migrate
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying admin.0001_initial... OK
  Applying sessions.0001_initial... OK
```

</div>

Now, start your unified development server:

<div class="termy">

```console
$ uv run reflex run
Starting Reflex development server...
App running at: http://localhost:3000
```

</div>

Open [http://localhost:3000](http://localhost:3000) in your browser. You should see the standard Reflex welcome screen!

---

## Step 6: Create Your First Page

Let's write a simple page that displays the active user's details. We'll subclass the unified `AppState` class to easily inspect the Django request and its active authenticated user.

Replace the contents of `frontend/frontend.py` with this code:

```python
# frontend/frontend.py
import reflex as rx
from reflex_django.state import AppState

class IndexState(AppState):
    greeting: str = "Loading user information..."

    @rx.event
    async def on_load(self):
        # Access the bridged Django user object via the request context
        user = self.request.user
        
        if user.is_authenticated:
            self.greeting = f"Welcome back, {user.get_username()}! You are authenticated."
        else:
            self.greeting = "Hello, Guest! Please sign in to access more features."

def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Reflex + Django Integration", size="8"),
            rx.card(
                rx.text(IndexState.greeting, size="4", weight="medium"),
                padding="1.5em",
                border_radius="12px",
                box_shadow="lg",
            ),
            spacing="5",
            align="center",
        ),
        min_height="100vh",
        background="linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
    )

app = rx.App()
app.add_page(index, route="/", on_load=IndexState.on_load)
```

Save the file. The Reflex server will automatically reload. Since you are not logged in, you should see the guest greeting: **"Hello, Guest! Please sign in to access more features."**

---

## Step 7: Verify the Django Admin Integration

Let's verify that the backend's admin panel is working seamlessly. 

### 1. Create a Superuser
In a new terminal window, run the standard Django command to create a master user:

<div class="termy">

```console
$ uv run reflex django createsuperuser
Username: admin
Email address: admin@example.com
Password: 
Password (again): 
Superuser created successfully.
```

</div>

### 2. Access the Admin Panel
1. Visit [http://localhost:3000/admin](http://localhost:3000/admin).
2. The page will render the classic Django Admin login page. Log in with your new credentials.
3. Once logged in, navigate back to your main site home page at [http://localhost:3000](http://localhost:3000).
4. Refresh the page. Because your session cookie is active, the Event Bridge syncs the context, and your Reflex page will update to: **"Welcome back, admin! You are authenticated."**

---

## Troubleshooting & FAQ

### Stale User Data / Authentication Mismatch
* **Problem:** You logged into `/admin` but the homepage still says "Hello, Guest".
* **Solution:** Verify that your `ReflexDjangoPlugin` has `install_event_bridge=True` (which is the default). This is the bridge that reads active browser cookies and updates the state.

### Running standard commands
* **Rule:** Always use `uv run reflex django <command>` instead of standard `python manage.py <command>`. This ensures the exact settings and compiler environments match what Reflex uses during the compilation phase.

---

**Navigation:** [← Configuration](configuration.md) | [Next: Existing Django Project →](existing_django_project.md)
