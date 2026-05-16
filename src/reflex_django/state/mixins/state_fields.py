"""State field validation and data extraction."""

from __future__ import annotations

from typing import Any

from asgiref.sync import sync_to_async

from reflex_django.state.base import ActionContext, BaseModelState


class StateFieldsMixin(BaseModelState):
    """Read, validate, and normalize editable state vars."""

    def get_state_data(self) -> dict[str, Any]:
        opts = self.get_options()
        data: dict[str, Any] = {}
        for sf in opts.state_fields:
            raw = getattr(self, sf.name)
            data[sf.name] = sf.to_python(raw)
        return data

    def validate_required(self, data: dict[str, Any]) -> dict[str, str]:
        opts = self.get_options()
        errors: dict[str, str] = {}
        for sf in opts.state_fields:
            if sf.required or sf.name in opts.required_fields:
                val = data.get(sf.name)
                if val is None or (isinstance(val, str) and not val.strip()):
                    errors[sf.name] = self.get_error_message(sf.name, "required")
        return errors

    def validate_field(self, name: str, value: Any) -> dict[str, str]:
        errors: dict[str, str] = {}
        clean = getattr(self, f"clean_{name}", None)
        if clean is not None:
            try:
                cleaned = clean(value)
                if isinstance(cleaned, str) and cleaned:
                    errors[name] = cleaned
            except Exception as exc:
                errors[name] = str(exc)
        opts = self.get_options()
        for sf in opts.state_fields:
            if sf.name == name:
                err = sf.validate_value(value)
                if err:
                    errors[name] = err
        return errors

    def validate_state(self, ctx: ActionContext, data: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        errors.update(self.validate_required(data))
        for name, value in data.items():
            if name in errors:
                continue
            errors.update(self.validate_field(name, value))
        for validator in self.state_validators:
            result = validator(self, data)
            if isinstance(result, dict):
                errors.update(result)
        return errors

    def clean_state(self, data: dict[str, Any]) -> dict[str, Any]:
        return dict(data)

    async def run_model_validation(self, state_data: dict[str, Any]) -> dict[str, str]:
        opts = self.get_options()
        if not opts.run_model_validation:
            return {}

        def _validate() -> dict[str, str]:
            from django.core.exceptions import ValidationError

            instance = opts.model(**state_data)
            try:
                instance.full_clean()
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    return {k: "; ".join(v) for k, v in exc.message_dict.items()}
                return {"__all__": "; ".join(exc.messages)}
            return {}

        return await sync_to_async(_validate)()

    async def validate_and_clean(self, ctx: ActionContext) -> tuple[dict[str, Any] | None, dict[str, str]]:
        data = self.get_state_data()
        errors = self.validate_state(ctx, data)
        if errors:
            return None, errors
        data = self.clean_state(data)
        model_errors = await self.run_model_validation(data)
        if model_errors:
            return None, model_errors
        return data, {}

    def on_state_invalid(self, ctx: ActionContext, errors: dict[str, str]) -> None:
        opts = ctx.options
        if opts.structured_errors and opts.field_errors_var:
            setattr(self, opts.field_errors_var, errors)
        summary = "; ".join(f"{k}: {v}" for k, v in errors.items()) or "Validation failed."
        setattr(self, opts.error_var, summary)

    async def on_state_valid(self, ctx: ActionContext, state_data: dict[str, Any]) -> dict[str, Any]:
        return state_data

    def apply_form_data(self, form_data: dict[str, Any]) -> None:
        """Copy ``form_data`` (e.g. from ``rx.form``) into editable state vars."""
        opts = self.get_options()
        for sf in opts.state_fields:
            if sf.name not in form_data:
                continue
            raw = form_data[sf.name]
            if sf.var_type is bool:
                setattr(self, sf.name, bool(raw))
            elif sf.var_type is int:
                setattr(
                    self,
                    sf.name,
                    int(raw) if raw not in (None, "") else 0,
                )
            else:
                setattr(self, sf.name, str(raw) if raw is not None else "")

    def reset_state_fields(self) -> None:
        """Clear editable vars, exit edit mode, and bump the form remount key when configured."""
        opts = self.get_options()
        for sf in opts.state_fields:
            setattr(self, sf.name, sf.to_var(None))
        setattr(self, opts.editing_var, -1)
        setattr(self, opts.error_var, "")
        if opts.field_errors_var:
            setattr(self, opts.field_errors_var, {})
        if opts.form_reset_var:
            current = int(getattr(self, opts.form_reset_var, 0))
            setattr(self, opts.form_reset_var, current + 1)

    def _reset_state_fields(self) -> None:
        self.reset_state_fields()


__all__ = ["StateFieldsMixin"]
