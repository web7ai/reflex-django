# shop/views.py — state and UI for app.add_page in shop/shop.py
import reflex as rx
from reflex_django.states import AppState


class HomeState(AppState):
    greeting: str = ""

    @rx.event
    async def on_load(self):
        user = self.request.user
        self.greeting = (
            f"Hi, {user.get_username()}!"
            if user.is_authenticated
            else "Hello, guest. Log in at /admin/."
        )


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("My Shop"),
        rx.text(HomeState.greeting),
    )
