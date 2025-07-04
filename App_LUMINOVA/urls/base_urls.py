from django.urls import path
from ..views import (
    inicio,
    login_view,
    change_password_view,
    custom_logout_view,
    dashboard_view,
)

# Rutas base
urlpatterns = [
    path("", inicio, name="inicio"),
    path("login/", login_view, name="login"),
    path("change-password/", change_password_view, name="change_password"),
    path("logout/", custom_logout_view, name="logout"),
    path("dashboard/", dashboard_view, name="dashboard"),
]