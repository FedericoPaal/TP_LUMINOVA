from django.urls import path
from ..views import (
    produccion_lista_op_view,
    produccion_detalle_op_view,
    planificacion_produccion_view,
    solicitar_insumos_op_view,
    reportes_produccion_view,
    crear_reporte_produccion_view,
)

# Rutas de Ventas
urlpatterns = [
    path("produccion/", produccion_lista_op_view, name="produccion_principal"),
    # path('produccion/vista-general/', produccion_view, name='produccion_vista_general'), # Si necesitas una página "marco" separada
    path("produccion/lista-op/", produccion_lista_op_view, name="produccion_lista_op"),
    path(
        "produccion/orden/<int:op_id>/",
        produccion_detalle_op_view,
        name="produccion_detalle_op",
    ),
    path(
        "produccion/planificacion/",
        planificacion_produccion_view,
        name="planificacion_produccion",
    ),
    path(
        "produccion/orden/<int:op_id>/solicitar-insumos/",
        solicitar_insumos_op_view,
        name="produccion_solicitar_insumos_op",
    ),
    path("produccion/reportes/", reportes_produccion_view, name="reportes_produccion"),
    path(
        "produccion/orden/<int:op_id>/crear-reporte/",
        crear_reporte_produccion_view,
        name="crear_reporte_produccion",
    ),
    path(
        "produccion/reportes/resolver/<int:reporte_id>/",
        reportes_produccion_view,
        {"resolver": True},
        name="produccion_resolver_reporte",
    ),
]