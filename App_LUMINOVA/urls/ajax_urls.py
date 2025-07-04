# App_LUMINOVA/urls/ajax_urls.py

from django.urls import path
from ..views import (
    # AJAX para Roles y Permisos
    crear_rol_ajax,
    get_rol_data_ajax,
    editar_rol_ajax,
    eliminar_rol_ajax,
    get_permisos_rol_ajax,
    actualizar_permisos_rol_ajax,

    # AJAX para Compras (ya las movemos aquí para el futuro)
    ajax_get_proveedores_for_insumo,
    get_oferta_proveedor_ajax,
)

# No necesitamos un app_name aquí, porque será heredado del include principal

urlpatterns = [
    # Rutas para Roles y Permisos
    path('roles/crear/', crear_rol_ajax, name='crear_rol_ajax'),
    path('roles/get-data/', get_rol_data_ajax, name='get_rol_data_ajax'),
    path('roles/editar/', editar_rol_ajax, name='editar_rol_ajax'),
    path('roles/eliminar/', eliminar_rol_ajax, name='eliminar_rol_ajax'),
    path('roles/get-permisos/', get_permisos_rol_ajax, name='get_permisos_rol_ajax'),
    path('roles/actualizar-permisos/', actualizar_permisos_rol_ajax, name='actualizar_permisos_rol_ajax'),

    # Rutas para otras funcionalidades (Compras)
    path('proveedores/get-for-insumo/', ajax_get_proveedores_for_insumo, name='ajax_get_proveedores_for_insumo'),
    path('ofertas/get-proveedor/', get_oferta_proveedor_ajax, name='ajax_get_oferta_proveedor'),
]