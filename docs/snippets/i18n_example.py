# shop/views.py
import reflex as rx
from django.utils.translation import gettext as _
from reflex_django.states import AppState


class HomeState(AppState):
    greeting: str = ""
    welcome_label: str = ""

    @rx.event
    async def on_load(self):
        # translation.get_language() is active here (LocaleMiddleware + bridge)
        self.welcome_label = _("Welcome")
        user = self.request.user
        if user.is_authenticated:
            self.greeting = _("Hi, {name}!").format(name=user.get_username())
        else:
            self.greeting = _("Hello, guest.")


def language_switcher() -> rx.Component:
    """POST to Django set_language with CSRF from AppState."""
    return rx.form(
        rx.input(
            type_="hidden", name="csrfmiddlewaretoken", value=HomeState.csrf_token
        ),
        rx.input(type_="hidden", name="next", value="/"),
        rx.hstack(
            rx.button("English", type="submit", name="language", value="en"),
            rx.button("Deutsch", type="submit", name="language", value="de"),
            spacing="3",
        ),
        action="/i18n/setlang/",
        method="POST",
    )


def index() -> rx.Component:
    return rx.vstack(
        language_switcher(),
        rx.text(HomeState.welcome_label, font_weight="bold"),
        rx.text(HomeState.greeting),
        rx.cond(
            HomeState.language_bidi,
            rx.text("(RTL layout)"),
        ),
        rx.text("Locale: ", HomeState.language),
        spacing="3",
        padding="2em",
        direction=rx.cond(HomeState.language_bidi, "rtl", "ltr"),
    )
