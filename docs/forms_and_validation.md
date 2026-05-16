# Forms and validation

Reflex forms, **state-field validation** on `ModelCRUDView`, and auth form rules.

---

## Prerequisites

- [CRUD with mixins](crud_with_mixins_and_states.md)  
- [Authentication](authentication.md)

---

## Two input styles

| Style | Pattern |
|-------|---------|
| Flat fields | `rx.input(value=State.title, on_change=State.set_title)` inside `rx.form(key=State.form_reset_key)` |
| Form submit | `rx.form` + `form_data` via `Meta.use_form_submit` (also use `key=State.form_reset_key`) |

---

## Clearing forms after save and edit

`ModelState` / `ModelCRUDView` clear editable state vars after a successful save when `Meta.reset_after_save` is `True` (default). The browser may still show old text until the form remounts.

| Handler | Clears vars | Bumps `form_reset_key` |
|---------|-------------|------------------------|
| `reset_state_fields()` | Yes | Yes |
| `cancel_edit` | Yes (via reset) | Yes |
| Successful `save` / `save_*` | Yes (when `reset_after_save`) | Yes |
| `start_edit` / `load(pk)` | Replaces with row data | Yes (`populate_edit_state`) |
| `bump_form_reset_key()` | No | Yes only |

**UI (recommended for create and update forms):**

```python
rx.form(
    rx.vstack(
        rx.input(value=NotesState.title, on_change=NotesState.set_title),
        rx.text_area(value=NotesState.content, on_change=NotesState.set_content),
        spacing="3",
        width="100%",
    ),
    key=NotesState.form_reset_key,
    width="100%",
)
rx.button("Save changes", on_click=NotesState.save)  # outside form when using on_click
```

- Set `Meta.reset_after_save = False` to keep values after save; call `reset_state_fields()` manually when needed.
- Set `Meta.form_reset_var = None` to disable automatic key bumps.
- Override `on_save_success(ctx, instance)` for custom logic before reset.

Full details: [Reactive ModelState — Clearing forms](reactive_model_state.md#clearing-forms-save-edit-cancel).

---

## `use_form_submit`

```python
class NotesState(AppState, ModelCRUDView):
    class Meta:
        use_form_submit = True
        save_event = "save_note"
```

Generates `save_note_form` that reads `form_data` then `dispatch("save")`—helps avoid stale bound fields on fast submit (see tests: `_FormSubmitState`).

```python
rx.form(
    rx.form.field(rx.input(name="title")),
    rx.button("Save", type="submit"),
    on_submit=NotesState.save_note_form,
    reset_on_submit=False,
    key=NotesState.form_reset_key,
)
```

Form `name=` keys must match serializer writable fields.

---

## State-centric validation (`StateFieldsMixin`)

| Hook | Role |
|------|------|
| `validate_state(ctx)` | Async; return error dict |
| `clean_{field}(value)` | Per-field |
| `state_validators` | Tuple of callables |
| `validate_and_clean` | Called from `dispatch("save")` |
| `on_state_invalid(ctx, errors)` | UX feedback |

```python
def clean_title(self, value: str) -> str | None:
    if len(value.strip()) < 3:
        return "At least 3 characters."
    return None
```

---

## Model `full_clean()`

```python
class Meta:
    run_model_validation = True
```

Runs Django model validation during save pipeline.

---

## Structured field errors

```python
class Meta:
    structured_errors = True
```

Enables per-field errors: `field_errors` on **`ModelState`**, or `{list_var}_field_errors` on **`ModelCRUDView`** (e.g. `notes_field_errors`).

Global message uses `error` (`ModelState`) or `{list_var}_error` (`ModelCRUDView`).

---

## Auth form validation

Registration mixin uses `validate_password`, `PASSWORD_MIN_LENGTH`, `EMAIL_REQUIRED` from `REFLEX_DJANGO_AUTH`.

Login uses `aauthenticate_login_fields` with configurable `LOGIN_FIELDS`.

---

## Manual CRUD validation

See [CRUD without mixins](crud_without_mixins.md) `_validate()` pattern.

---

## Advanced usage

- Combine client-side `required` on inputs with server `validate_state` always.  
- Custom `on_save_success` to clear only specific fields.

---

## Common mistakes

- Trusting client validation only.  
- Mismatched `name=` in `rx.form` vs serializer fields when using `use_form_submit`.
- Forgetting `key=State.form_reset_key` — form stays filled after update/save even when state vars are cleared.

---

## Performance tips

- Validate only changed fields in `clean_*` when forms are large.

---

## See also

- [CRUD with mixins](crud_with_mixins_and_states.md)  
- [Authentication](authentication.md)

---

**Navigation:** [← CRUD with mixins](crud_with_mixins_and_states.md) | [Next: Authentication →](authentication.md)
