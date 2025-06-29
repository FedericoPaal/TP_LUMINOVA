# TP_LUMINOVA-main/App_LUMINOVA/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    # Vistas Principales y Autenticación
    ajax_get_proveedores_for_insumo, inicio, login_view, dashboard_view, recepcion_pedidos_view, recibir_pedido_oc_view, 

    # Admin
    roles_permisos_view, auditoria_view,
    lista_usuarios, crear_usuario, editar_usuario, eliminar_usuario, solicitar_insumos_op_view, ventas_cancelar_ov_view, ventas_detalle_ov_view, ventas_editar_ov_view, ventas_generar_factura_view, change_password_view, custom_logout_view,

    # Ventas
    ventas_lista_ov_view, ventas_crear_ov_view,
    lista_clientes_view, crear_cliente_view, editar_cliente_view, eliminar_cliente_view,
    proveedor_create_view,
    ventas_ver_factura_pdf_view,

    # Compras (Renombrar vistas si es necesario en views.py)
    compras_lista_oc_view, # Vista para el listado principal de Órdenes de Compra
    compras_desglose_detalle_oc_view, compras_desglose_view,
    compras_seguimiento_view, compras_tracking_pedido_view,
    compras_crear_oc_view,
    compras_seleccionar_proveedor_para_insumo_view,
    compras_detalle_oc_view, compras_editar_oc_view, compras_aprobar_oc_directamente_view,
    get_oferta_proveedor_ajax,

    # Producción

    produccion_lista_op_view,
    produccion_detalle_op_view,
    planificacion_produccion_view,
    reportes_produccion_view,
    crear_reporte_produccion_view,
    # Depósito
    deposito_view, # Vista principal de depósito (categorías)
    deposito_solicitudes_insumos_view,
    deposito_detalle_solicitud_op_view,
    deposito_enviar_insumos_op_view,
    deposito_enviar_lote_pt_view,


    # CRUDs para Categorías, Insumos, Productos Terminados (Class-Based Views)
    Categoria_IDetailView, Categoria_ICreateView, Categoria_IUpdateView, Categoria_IDeleteView,
    Categoria_PTDetailView, Categoria_PTCreateView, Categoria_PTUpdateView, Categoria_PTDeleteView,
    InsumosListView, InsumoDetailView, InsumoCreateView, InsumoUpdateView, InsumoDeleteView,
    ProductoTerminadosListView, ProductoTerminadoDetailView, ProductoTerminadoCreateView, ProductoTerminadoUpdateView, ProductoTerminadoDeleteView,
    ProveedorDetailView, ProveedorListView, ProveedorUpdateView, ProveedorDeleteView,
    FabricanteCreateView, FabricanteDetailView, FabricanteListView, FabricanteUpdateView, FabricanteDeleteView,

    # Control de Calidad (Placeholder)
    control_calidad_view,

    # Vistas AJAX para Roles
    crear_rol_ajax, get_rol_data_ajax, editar_rol_ajax, eliminar_rol_ajax,
    get_permisos_rol_ajax, actualizar_permisos_rol_ajax,
)


app_name = 'App_LUMINOVA'

urlpatterns = [
    # --- Rutas Principales y Autenticación ---
    path("", inicio, name="inicio"),
    path('login/', login_view, name='login'),
    path('change-password/', change_password_view, name='change_password'),
    path('logout/', custom_logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),

    # --- Rutas de Administración ---
    path('admin/usuarios/', lista_usuarios, name='lista_usuarios'),
    path('admin/usuarios/crear/', crear_usuario, name='crear_usuario'),
    path('admin/usuarios/editar/<int:id>/', editar_usuario, name='editar_usuario'),
    path('admin/usuarios/eliminar/<int:id>/', eliminar_usuario, name='eliminar_usuario'),
    path('admin/roles-permisos/', roles_permisos_view, name='roles-permisos'),
    path('admin/auditoria/', auditoria_view, name='auditoria'),

    # --- Rutas de Ventas ---
    path('ventas/', ventas_lista_ov_view, name='ventas_lista_ov'),
    path('ventas/orden/crear/', ventas_crear_ov_view, name='ventas_crear_ov'),
    path('ventas/clientes/', lista_clientes_view, name='lista_clientes'),
    path('ventas/clientes/crear/', crear_cliente_view, name='crear_cliente'),
    path('ventas/clientes/editar/<int:cliente_id>/', editar_cliente_view, name='editar_cliente'),
    path('ventas/clientes/eliminar/<int:cliente_id>/', eliminar_cliente_view, name='eliminar_cliente'),
    path('ventas/orden/<int:ov_id>/', ventas_detalle_ov_view, name='ventas_detalle_ov'),
    path('ventas/orden/<int:ov_id>/generar-factura/', ventas_generar_factura_view, name='ventas_generar_factura'),
    path('ventas/orden/<int:ov_id>/editar/', ventas_editar_ov_view, name='ventas_editar_ov'),   # NUEVA
    path('ventas/orden/<int:ov_id>/cancelar/', ventas_cancelar_ov_view, name='ventas_cancelar_ov'), # NUEVA
    path('ventas/factura/<int:factura_id>/pdf/', ventas_ver_factura_pdf_view, name='ventas_ver_factura_pdf'),
    path('ventas/orden/<int:ov_id>/editar/', ventas_editar_ov_view, name='ventas_editar_ov'),

    # --- Rutas de Compras ---
    path('compras/', compras_lista_oc_view, name='compras_lista_oc'), # Vista principal de compras
    path('compras/desglose/', compras_desglose_view, name='compras_desglose'),
    
    path('compras/seguimiento/', compras_seguimiento_view, name='compras_seguimiento'),
    path('compras/tracking/<int:oc_id>/', compras_tracking_pedido_view, name='compras_tracking_pedido'),    
    path('compras/desglose-oc/<str:numero_orden_desglose>/', compras_desglose_detalle_oc_view, name='compras_desglose_detalle_oc'),
    path('compras/orden/crear/', compras_crear_oc_view, name='compras_crear_oc'), # Vista para crear una nueva OC
    path('compras/orden/crear/desde-insumo/<int:insumo_id>/proveedor/<int:proveedor_id>/', compras_crear_oc_view, name='compras_crear_oc_desde_insumo_y_proveedor'),
    path('compras/orden/seleccionar-proveedor/insumo/<int:insumo_id>/', compras_seleccionar_proveedor_para_insumo_view, name='compras_seleccionar_proveedor_para_insumo'),
    path('compras/orden/<int:oc_id>/', compras_detalle_oc_view, name='compras_detalle_oc'),      
    path('compras/orden/<int:oc_id>/editar/', compras_editar_oc_view, name='compras_editar_oc'),
    path('compras/orden/<int:oc_id>/aprobar-directo/', compras_aprobar_oc_directamente_view, name='compras_aprobar_oc_directamente'),
    path('ajax/get-oferta-proveedor/', get_oferta_proveedor_ajax, name='ajax_get_oferta_proveedor'),
    path('ajax/get-proveedores-for-insumo/', ajax_get_proveedores_for_insumo, name='ajax_get_proveedores_for_insumo'),

    # --- Rutas de Producción ---
    path('produccion/', produccion_lista_op_view, name='produccion_principal'),
    #path('produccion/vista-general/', produccion_view, name='produccion_vista_general'), # Si necesitas una página "marco" separada
    path('produccion/lista-op/', produccion_lista_op_view, name='produccion_lista_op'),
    path('produccion/orden/<int:op_id>/', produccion_detalle_op_view, name='produccion_detalle_op'),
    path('produccion/planificacion/', planificacion_produccion_view, name='planificacion_produccion'),
    path('produccion/orden/<int:op_id>/solicitar-insumos/', solicitar_insumos_op_view, name='produccion_solicitar_insumos_op'),
    path('produccion/reportes/', reportes_produccion_view, name='reportes_produccion'),
    path('produccion/orden/<int:op_id>/crear-reporte/', crear_reporte_produccion_view, name='crear_reporte_produccion'),
    path('produccion/reportes/resolver/<int:reporte_id>/', reportes_produccion_view, {'resolver': True}, name='produccion_resolver_reporte'),

    # --- Rutas de Depósito ---
    path('deposito/', deposito_view, name='deposito_view'),
    path('deposito/solicitudes-insumos/', deposito_solicitudes_insumos_view, name='deposito_solicitudes_insumos'),
    path('deposito/solicitud-op/<int:op_id>/', deposito_detalle_solicitud_op_view, name='deposito_detalle_solicitud_op'),
    path('deposito/enviar-insumos-op/<int:op_id>/', deposito_enviar_insumos_op_view, name='deposito_enviar_insumos_op'),
    path('deposito/enviar-lote-pt/<int:lote_id>/', deposito_enviar_lote_pt_view, name='deposito_enviar_lote_pt'),
    path('deposito/recepcion-pedidos/', recepcion_pedidos_view, name='deposito_recepcion_pedidos'),
    path('deposito/recibir-pedido/<int:oc_id>/', recibir_pedido_oc_view, name='deposito_recibir_pedido'),
    

    # CRUDs para Fabricantes, Proveedores (Class-Based Views)
    path('ventas/proveedores/proveedor/', ProveedorListView.as_view(), name='proveedor_list'),
    path('ventas/proveedores/proveedor/<int:pk>/', ProveedorDetailView.as_view(), name='proveedor_detail'),
    path('ventas/proveedores/proveedor/crear/', proveedor_create_view, name='proveedor_create'),
    path('ventas/proveedores/proveedor/editar/<int:pk>/', ProveedorUpdateView.as_view(), name='proveedor_edit'),
    path('ventas/proveedores/proveedor/eliminar/<int:pk>/', ProveedorDeleteView.as_view(), name='proveedor_delete'),

    path('ventas/fabricantes/<int:pk>/', FabricanteDetailView.as_view(), name='fabricante_detail'),
    path('ventas/fabricantes/crear/', FabricanteCreateView.as_view(), name='fabricante_create'),
    path('ventas/fabricantes/editar/<int:pk>/', FabricanteUpdateView.as_view(), name='fabricante_edit'),
    path('ventas/fabricantes/eliminar/<int:pk>/', FabricanteDeleteView.as_view(), name='fabricante_delete'),


    # CRUDs para Categorías, Insumos, Productos Terminados (Class-Based Views)
    path('deposito/categorias-insumo/<int:pk>/', Categoria_IDetailView.as_view(), name='categoria_i_detail'),
    path('deposito/categorias-insumo/crear/', Categoria_ICreateView.as_view(), name='categoria_i_create'),
    path('deposito/categorias-insumo/editar/<int:pk>/', Categoria_IUpdateView.as_view(), name='categoria_i_edit'),
    path('deposito/categorias-insumo/eliminar/<int:pk>/', Categoria_IDeleteView.as_view(), name='categoria_i_delete'),

    path('deposito/categorias-producto-terminado/<int:pk>/', Categoria_PTDetailView.as_view(), name='categoria_pt_detail'),
    path('deposito/categorias-producto-terminado/crear/', Categoria_PTCreateView.as_view(), name='categoria_pt_create'),
    path('deposito/categorias-producto-terminado/editar/<int:pk>/', Categoria_PTUpdateView.as_view(), name='categoria_pt_edit'),
    path('deposito/categorias-producto-terminado/eliminar/<int:pk>/', Categoria_PTDeleteView.as_view(), name='categoria_pt_delete'),

    path('deposito/insumos/crear/', InsumoCreateView.as_view(), name='insumo_create'),
    path('deposito/insumos/editar/<int:pk>/', InsumoUpdateView.as_view(), name='insumo_edit'),
    path('deposito/insumos/eliminar/<int:pk>/', InsumoDeleteView.as_view(), name='insumo_delete'),
    # path('deposito/insumos/', InsumosListView.as_view(), name='insumos_list'), # Descomentar si necesitas una lista general de todos los insumos

    path('deposito/productos-terminados/crear/', ProductoTerminadoCreateView.as_view(), name='producto_terminado_create'),
    path('deposito/productos-terminados/editar/<int:pk>/', ProductoTerminadoUpdateView.as_view(), name='producto_terminado_edit'),
    path('deposito/productos-terminados/eliminar/<int:pk>/', ProductoTerminadoDeleteView.as_view(), name='producto_terminado_delete'),
    # path('deposito/productos-terminados/',ProductoTerminadosListView.as_view(), name='productos_terminados_list'),


    # --- Ruta de Control de Calidad (Placeholder) ---
    path('control_calidad/', control_calidad_view, name='control_calidad_view'),

    # --- URLs AJAX para Roles y Permisos ---
    path('ajax/crear-rol/', crear_rol_ajax, name='crear_rol_ajax'),
    path('ajax/get-rol-data/', get_rol_data_ajax, name='get_rol_data_ajax'),
    path('ajax/editar-rol/', editar_rol_ajax, name='editar_rol_ajax'),
    path('ajax/eliminar-rol/', eliminar_rol_ajax, name='eliminar_rol_ajax'),
    path('ajax/get-permisos-rol/', get_permisos_rol_ajax, name='get_permisos_rol_ajax'),
    path('ajax/actualizar-permisos-rol/', actualizar_permisos_rol_ajax, name='actualizar_permisos_rol_ajax'),
]