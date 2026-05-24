# Architecture

To successfully build and debug high-performance full-stack applications with **reflex-django**, it is helpful to understand the underlying mechanics of how Reflex and Django run in harmony within a single operating system process.

This document details the single-process ASGI dispatch model, the event bridge pipeline, and the runtime request lifecycles.

---

## The Three Architecture Pillars

```mermaid
flowchart LR
    subgraph pillar1["Pillar 1: Bootstrapping"]
        A["urls.py imports reflex_mount"] --> B["register_mount_rx_config"]
        B --> C["configure_django + patch get_config"]
        C --> D["django_led_app loads pages"]
    end
    
    subgraph pillar2["Pillar 2: HTTP Dispatcher"]
        E["ASGI Server"] --> F["make_dispatcher"]
        F --> G["django_prefix → Django; else → Reflex"]
    end
    
    subgraph pillar3["Pillar 3: Event Bridge"]
        H["WebSocket /_event"] --> I["DjangoEventBridge"]
        I --> J["self.request.user in State"]
    end
```

1. **Bootstrap**: Importing `ROOT_URLCONF` runs `reflex_mount()`, which registers Reflex `rx.Config`. `install_reflex_django_integration()` patches `get_config()`, calls `configure_django()`, imports `{app}.views`, and builds `rx.App` via `reflex_django.django_led_app`.
2. **HTTP dispatcher**: `make_dispatcher()` routes paths in `django_prefix` to Django ASGI; everything else (except Reflex reserved paths) goes to the Reflex SPA.
3. **Event bridge**: `DjangoEventBridge` builds a synthetic `HttpRequest` per WebSocket event so session and `request.user` match Django.

---

## Unified Process System Topology

Below is the runtime topology of the unified ASGI process during a standard local run or production container deployment:

```mermaid
flowchart TB
  subgraph Client["Client (Browser Context)"]
    BrowserHTTP["Standard HTTP Requests\n(e.g., /admin, /api/products)"]
    BrowserWS["Persistent WebSockets\n(Socket.IO - e.g., /_event)"]
  end

  subgraph Process["Single ASGI Process (reflex run)"]
    Dispatcher["ASGI Path Dispatcher\n(make_dispatcher)"]
    
    subgraph DjangoApp["Django App Context"]
      DjangoASGI["Django ASGI Handler\n(build_django_asgi)"]
      DjangoORM[("Django ORM\n(Database Connection)")]
    end
    
    subgraph ReflexApp["Reflex App Context"]
      ReflexASGI["Reflex ASGI Handler\n(Starlette / Socket.IO)"]
      EventBridge["DjangoEventBridge\n(Middleware Interceptor)"]
      EventHandlers["Reactive Event Handlers\n(@rx.event States)"]
    end
  end

  BrowserHTTP --> Dispatcher
  Dispatcher -->|"/admin, /api, /static"| DjangoASGI
  Dispatcher -->|Default / Fallback| ReflexASGI
  
  BrowserWS --> ReflexASGI
  ReflexASGI --> EventBridge
  EventBridge -->|Binds Session & User| EventHandlers
  EventHandlers -->|Queries database| DjangoORM
  DjangoASGI -->|Queries database| DjangoORM
```

---

## Detailed HTTP Request Lifecycle

When a client hits an HTTP path served by your server, the outermost ASGI router evaluates the incoming Starlette/ASGI connection scope:

```text
Incoming HTTP Connection
   │
   ▼
Check Connection Scope (scope["type"])
   │
   ├─► "lifespan" ────► Handled exclusively by Reflex (Django is bypassed)
   │
   └─► "http" / "websocket"
         │
         ▼
       Check scope["path"] prefix
         │
         ├──► Matches admin_prefix (e.g., /admin)  ─────────┐
         ├──► Matches backend_prefix (e.g., /api)  ─────────┼─► Routed to Django ASGI
         ├──► Matches STATIC_URL (e.g., /static)   ─────────┤   (Full Django Middleware runs)
         ├──► Matches custom django_prefix         ─────────┘
         │
         └──► Default (No Prefix Matches)  ─────────────────► Routed to Reflex ASGI
                                                              (SPA page, dynamic views)
```

### Reserved Paths
To ensure your frontend client can always communicate with the Reflex compiler, certain paths are reserved and will **never** be captured by Django prefixes, regardless of catch-all wildcards:
* `/_event` (WebSocket communication)
* `/_upload` (File upload handlers)
* `/_health` & `/ping` (Process health checks)
* `/auth-codespace` (Authentication tools)

---

## Detailed WebSocket Event Lifecycle

Reflex components trigger interactions using WebSocket event packets. The `DjangoEventBridge` acts as an event pre-processor to link these packets to Django's active session store:

```mermaid
sequenceDiagram
    autonumber
    participant Browser as Client Browser
    participant Reflex as Reflex Engine
    participant Bridge as DjangoEventBridge
    participant Django as Django Session & Auth
    participant State as State Event Handler

    Browser->>Reflex: Clicks button (Triggers socket event)
    activate Reflex
    Reflex->>Bridge: preprocess(event)
    activate Bridge
    Bridge->>Bridge: Clean old thread-local contexts
    Bridge->>Bridge: Rebuild synthetic HttpRequest from event cookies & headers
    Bridge->>Django: Load session (via SESSION_ENGINE)
    Django-->>Bridge: Session variables retrieved
    Bridge->>Django: Resolve user (via aget_user)
    Django-->>Bridge: Authenticated User instance
    Bridge->>Bridge: Bind request, user, and language to current contextvars
    deactivate Bridge
    Reflex->>State: Invoke developer state handler (e.g., on_click)
    activate State
    State->>State: Access current_user() / require_login_user()
    State-->>Reflex: Return state mutations
    deactivate State
    Reflex-->>Browser: Push reactive UI changes to frontend
    deactivate Reflex
```

---

## Environment Configuration Alignment

Incoming connections are handled differently depending on the active environment profile:

| Feature / Scope | Development Mode | Production Mode |
|:---|:---|:---|
| **Process Count** | Two sub-processes (Vite + Reflex Server) | **Single Process** |
| **Frontend Assets** | Served dynamically via Vite development server | Served directly by Starlette or an external CDN |
| **API Path Routing** | Vite forwards prefix paths (`/admin`, `/api`) directly to the backend port | Same-origin dispatcher forwards matching paths directly to Django |
| **Static files** | Served dynamically by Django `ASGIStaticFilesHandler` | Served from `STATIC_ROOT` via the ASGI dispatcher |

---

**Navigation:** [← Project Structure](project_structure.md) | [Next: Routing →](routing.md)
