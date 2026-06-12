---
level: beginner
tags: [onboarding]
---

# Learning path

**What you'll learn:** A guided reading order from "what is this?" to a running app, with time estimates so you can plan a coffee break (or two).

**When you need this:**

- You are new to reflex-django and want a structured tour instead of jumping between reference pages.
- You are onboarding a teammate and need a checklist they can follow on day one.

---

Follow the cards in order. Check each box when you are done. Skip the Django or Reflex primer if that framework is already your day job.

<div class="rd-path-grid" markdown="0">
<a href="../mental_model/" class="rd-path-card rd-path-card--beginner">
<p class="rd-path-card__title">1. The three knobs</p>
<p class="rd-path-card__meta">~8 minutes</p>
<p class="rd-path-card__desc">Settings, page imports, and the automatic SPA catch-all. The map every other page links back to.</p>
</a>
<a href="../why_reflex_django/" class="rd-path-card rd-path-card--beginner">
<p class="rd-path-card__title">2. Why reflex-django exists</p>
<p class="rd-path-card__meta">~5 minutes</p>
<p class="rd-path-card__desc">The HTTP vs WebSocket gap and how reflex-django closes it. No code required.</p>
</a>
<a href="../how_django_works/" class="rd-path-card rd-path-card--beginner">
<p class="rd-path-card__title">3. How Django works (5 min)</p>
<p class="rd-path-card__meta">~5 minutes, optional</p>
<p class="rd-path-card__desc">URLs, middleware, views, ORM, sessions. Skip if Django is already home turf.</p>
</a>
<a href="../how_reflex_works/" class="rd-path-card rd-path-card--beginner">
<p class="rd-path-card__title">4. How Reflex works (5 min)</p>
<p class="rd-path-card__meta">~5 minutes, optional</p>
<p class="rd-path-card__desc">Components, state, events, and the compiled SPA. Skip if you have built Reflex before.</p>
</a>
<a href="../how_they_fit/" class="rd-path-card rd-path-card--intermediate">
<p class="rd-path-card__title">5. How they fit together</p>
<p class="rd-path-card__meta">~8 minutes</p>
<p class="rd-path-card__desc">Mount-only dev and production routing, AppState, and the event bridge in plain English.</p>
</a>
<a href="../installation/" class="rd-path-card rd-path-card--beginner">
<p class="rd-path-card__title">6. Install</p>
<p class="rd-path-card__meta">~5 minutes</p>
<p class="rd-path-card__desc">Add reflex-django to a project and register the app.</p>
</a>
<a href="../quickstart/" class="rd-path-card rd-path-card--beginner">
<p class="rd-path-card__title">7. Your first app</p>
<p class="rd-path-card__meta">~15 minutes</p>
<p class="rd-path-card__desc">A todo list that exercises pages, state, auth, and the database.</p>
</a>
<a href="../configuration/" class="rd-path-card rd-path-card--intermediate">
<p class="rd-path-card__title">8. Configuration</p>
<p class="rd-path-card__meta">~10 minutes</p>
<p class="rd-path-card__desc">Every knob in settings.py: routing mode, plugins, page packages, and overrides.</p>
</a>
</div>

---

## Checklist

- [ ] [The three knobs](mental_model.md): I know settings, page imports, and catch-all are separate jobs.
- [ ] [Why reflex-django exists](why_reflex_django.md): I understand the HTTP vs WebSocket gap.
- [ ] [How Django works](how_django_works.md): optional; skipped or done.
- [ ] [How Reflex works](how_reflex_works.md): optional; skipped or done.
- [ ] [How they fit together](how_they_fit.md): I can explain default dev (Vite + Reflex backend with Django mounted) and production routing.
- [ ] [Install](installation.md): reflex-django is in my project.
- [ ] [Your first app](quickstart.md): I ran `manage.py run_reflex` and saw a page update.
- [ ] [Configuration](configuration.md): I know where `REFLEX_DJANGO_*` settings live.

!!! tip "Brownfield projects"
    Already have Django or Reflex? After step 5, branch to [Existing Django project](existing_django_project.md) or [Existing Reflex project](existing_reflex_project.md) instead of the quickstart.

---

## After the path

Once the checklist is green, drop into build guides as you need them: [Pages in views.py](pages_in_views.md), [CRUD with ModelState](reactive_model_state.md), [Authentication](authentication.md), [Deployment](deployment.md).

Total time for the full path is about 45 minutes if you read everything, or about 25 if you skip the two primers. Either way, you will know more than the average developer who installs a framework and immediately opens twelve tabs.

---

## What just happened?

You picked a reading order with time boxes, optional primers, and a checklist that ends at a running app plus configuration literacy.

**Next up:** [The three knobs](mental_model.md)
