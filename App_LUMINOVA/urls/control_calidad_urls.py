from django.urls import path
from ..views import (
    control_calidad_view
)
# Rutas de Control de Calidad
urlpatterns = [
    path("control_calidad/", control_calidad_view, name="control_calidad_view"),
]