from django.urls import path
from ..views import (
    ventas_lista_ov_view,
    ventas_crear_ov_view,
    lista_clientes_view,
    crear_cliente_view,
    editar_cliente_view,
    eliminar_cliente_view,
    ventas_detalle_ov_view,
    ventas_generar_factura_view,
    ventas_editar_ov_view,
    ventas_cancelar_ov_view,
    ventas_ver_factura_pdf_view,
)

# Rutas de Ventas
urlpatterns = [
    path("ventas/", ventas_lista_ov_view, name="ventas_lista_ov"),
    path("ventas/orden/crear/", ventas_crear_ov_view, name="ventas_crear_ov"),
    path("ventas/clientes/", lista_clientes_view, name="lista_clientes"),
    path("ventas/clientes/crear/", crear_cliente_view, name="crear_cliente"),
    path(
        "ventas/clientes/editar/<int:cliente_id>/",
        editar_cliente_view,
        name="editar_cliente",
    ),
    path(
        "ventas/clientes/eliminar/<int:cliente_id>/",
        eliminar_cliente_view,
        name="eliminar_cliente",
    ),
    path("ventas/orden/<int:ov_id>/", ventas_detalle_ov_view, name="ventas_detalle_ov"),
    path(
        "ventas/orden/<int:ov_id>/generar-factura/",
        ventas_generar_factura_view,
        name="ventas_generar_factura",
    ),
    path(
        "ventas/orden/<int:ov_id>/editar/",
        ventas_editar_ov_view,
        name="ventas_editar_ov",
    ),  # NUEVA
    path(
        "ventas/orden/<int:ov_id>/cancelar/",
        ventas_cancelar_ov_view,
        name="ventas_cancelar_ov",
    ),  # NUEVA
    path(
        "ventas/factura/<int:factura_id>/pdf/",
        ventas_ver_factura_pdf_view,
        name="ventas_ver_factura_pdf",
    ),
    path(
        "ventas/orden/<int:ov_id>/editar/",
        ventas_editar_ov_view,
        name="ventas_editar_ov",
    ),
]

