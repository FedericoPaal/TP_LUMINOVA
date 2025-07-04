from django.urls import path
from ..views import (
    compras_lista_oc_view,
    compras_crear_oc_view,
    compras_seleccionar_proveedor_para_insumo_view,
    compras_detalle_oc_view,
    compras_editar_oc_view,
    compras_aprobar_oc_directamente_view,
    compras_desglose_view,
    compras_seguimiento_view,
    compras_tracking_pedido_view,
    compras_desglose_detalle_oc_view,
    get_oferta_proveedor_ajax,
    ajax_get_proveedores_for_insumo,
)

# Rutas de Ventas
urlpatterns = [
    path(
        "compras/", compras_lista_oc_view, name="compras_lista_oc"
    ),  # Vista principal de compras
    path("compras/desglose/", compras_desglose_view, name="compras_desglose"),
    path("compras/seguimiento/", compras_seguimiento_view, name="compras_seguimiento"),
    path(
        "compras/tracking/<int:oc_id>/",
        compras_tracking_pedido_view,
        name="compras_tracking_pedido",
    ),
    path(
        "compras/desglose-oc/<str:numero_orden_desglose>/",
        compras_desglose_detalle_oc_view,
        name="compras_desglose_detalle_oc",
    ),
    path(
        "compras/orden/crear/", compras_crear_oc_view, name="compras_crear_oc"
    ),  # Vista para crear una nueva OC
    path(
        "compras/orden/crear/desde-insumo/<int:insumo_id>/proveedor/<int:proveedor_id>/",
        compras_crear_oc_view,
        name="compras_crear_oc_desde_insumo_y_proveedor",
    ),
    path(
        "compras/orden/seleccionar-proveedor/insumo/<int:insumo_id>/",
        compras_seleccionar_proveedor_para_insumo_view,
        name="compras_seleccionar_proveedor_para_insumo",
    ),
    path(
        "compras/orden/<int:oc_id>/", compras_detalle_oc_view, name="compras_detalle_oc"
    ),
    path(
        "compras/orden/<int:oc_id>/editar/",
        compras_editar_oc_view,
        name="compras_editar_oc",
    ),
    path(
        "compras/orden/<int:oc_id>/aprobar-directo/",
        compras_aprobar_oc_directamente_view,
        name="compras_aprobar_oc_directamente",
    ),
    path(
        "ajax/get-oferta-proveedor/",
        get_oferta_proveedor_ajax,
        name="ajax_get_oferta_proveedor",
    ),
    path(
        "ajax/get-proveedores-for-insumo/",
        ajax_get_proveedores_for_insumo,
        name="ajax_get_proveedores_for_insumo",
    ),
]