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
| Flat fields | `rx.input(value=State.title, on_change=State.set_title)` |
| Form submit | `rx.form.root` + `form_data` via `Meta.use_form_submit` |

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

Enables `{list_var}_field_errors` (e.g. `notes_field_errors`) when `structured_errors` is true in resolved options.

Global message still uses `{list_var}_error`.

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

---

## Performance tips

- Validate only changed fields in `clean_*` when forms are large.

---

## See also

- [CRUD with mixins](crud_with_mixins_and_states.md)  
- [Authentication](authentication.md)

---

**Navigation:** [← CRUD with mixins](crud_with_mixins_and_states.md) | [Next: Authentication →](authentication.md)
