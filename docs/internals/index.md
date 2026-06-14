# Internals

Optional reading for debugging, performance tuning, and contributors. You do not need these pages to ship your first app.

| Page | Contents |
|:---|:---|
| [Architecture](architecture.md) | Dev vs prod routing, ASGI layout, event bridge overview |
| [Routing](routing.md) | How HTTP paths split between Django and Reflex |
| [Event pipeline](event_pipeline.md) | WebSocket events, middleware tiers, cache |
| [Streaming middleware](streaming_middleware.md) | `AsyncStreamingMiddleware` and async ORM |

**Start simpler:** [How it fits](../overview/concepts.md) | **Tune performance:** [Scaling](../operations/scaling.md)