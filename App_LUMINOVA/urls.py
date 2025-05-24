from django.urls import path
from django.contrib.auth import views as auth_views
from .views import *

app_name = 'App_LUMINOVA'

urlpatterns = [
    path("", inicio, name="inicio"), # Esta URL raíz ahora mostrará la página de login
    
    path("compras/", compras, name="compras"),
    path("produccion/", produccion, name="produccion"),
    path("ventas/", ventas, name="ventas"),
    path("deposito/", deposito, name="deposito"),
    path("control_calidad/", control_calidad, name="control_calidad"),

    path('login/', auth_views.LoginView.as_view(template_name='login.html', next_page='App_LUMINOVA:dashboard'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='App_LUMINOVA:login'), name='logout'),

    path('dashboard/', dashboard_view, name='dashboard'),
    path('roles-permisos/', roles_permisos_view, name='roles-permisos'),
    path('auditoria/', auditoria_view, name='auditoria'),

    path('usuarios/', lista_usuarios, name='lista_usuarios'),
    path('usuarios/crear/', crear_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:id>/', editar_usuario, name='editar_usuario'),
    path('usuarios/eliminar/<int:id>/', eliminar_usuario, name='eliminar_usuario'),

    path("compras/desglose/", desglose, name="desglose"),
    path("compras/seguimiento/", seguimiento, name="seguimiento"),
    path("compras/tracking/", tracking, name="tracking"),
    path("compras/desglose2/", desglose2, name="desglose2"),

    path('produccion/ordenes/', ordenes, name='ordenes'),
    path('produccion/planificacion/', planificacion, name='planificacion'),
    path('produccion/reportes/', reportes, name='reportes'),

    path('deposito/seleccion/', depo_seleccion, name='depo_seleccion'),
    path('deposito/enviar/', depo_enviar, name='depo_enviar'),

    # URLs para Categorias de Insumo
    path('deposito/categorias-insumo/<int:pk>/', Categoria_IDetailView.as_view(), name='categoria_i_detail'),
    path('deposito/categorias-insumo/crear/', Categoria_ICreateView.as_view(), name='categoria_i_create'),
    path('deposito/categorias-insumo/editar/<int:pk>/', Categoria_IUpdateView.as_view(), name='categoria_i_edit'),
    path('deposito/categorias-insumo/eliminar/<int:pk>/', Categoria_IDeleteView.as_view(), name='categoria_i_delete'),

    # URLs para Categorias de Producto Terminado
    path('deposito/categorias-producto-terminado/<int:pk>/', Categoria_PTDetailView.as_view(), name='categoria_pt_detail'),
    path('deposito/categorias-producto-terminado/crear/', Categoria_PTCreateView.as_view(), name='categoria_pt_create'),
    path('deposito/categorias-producto-terminado/editar/<int:pk>/', Categoria_PTUpdateView.as_view(), name='categoria_pt_edit'),
    path('deposito/categorias-producto-terminado/eliminar/<int:pk>/', Categoria_PTDeleteView.as_view(), name='categoria_pt_delete'),

    # URLs para Insumos
    path('deposito/insumos/', InsumosListView.as_view(), name='insumos_list'), # Si quieres una lista general
    path('deposito/insumos/<int:pk>/', InsumoDetailView.as_view(), name='insumo_detail'),
    path('deposito/insumos/crear/', InsumoCreateView.as_view(), name='insumo_create'),
    path('deposito/insumos/editar/<int:pk>/', InsumoUpdateView.as_view(), name='insumo_edit'),
    path('deposito/insumos/eliminar/<int:pk>/', InsumoDeleteView.as_view(), name='insumo_delete'),

    # URLs para Productos Terminados
    path('deposito/productos-terminados/',ProductoTerminadosListView.as_view(), name='productos_terminados_list'), # Si quieres una lista general
    path('deposito/productos-terminados/<int:pk>/', ProductoTerminadoDetailView.as_view(), name='producto_terminado_detail'),
    path('deposito/productos-terminados/crear/', ProductoTerminadoCreateView.as_view(), name='producto_terminado_create'),
    path('deposito/productos-terminados/editar/<int:pk>/', ProductoTerminadoUpdateView.as_view(), name='producto_terminado_edit'),
    path('deposito/productos-terminados/eliminar/<int:pk>/', ProductoTerminadoDeleteView.as_view(), name='producto_terminado_delete'),

    # URLs AJAX para Roles y Permisos
    path('ajax/crear-rol/', crear_rol_ajax, name='crear_rol_ajax'),
    path('ajax/get-rol-data/', get_rol_data_ajax, name='get_rol_data_ajax'),
    path('ajax/editar-rol/', editar_rol_ajax, name='editar_rol_ajax'),
    path('ajax/eliminar-rol/', eliminar_rol_ajax, name='eliminar_rol_ajax'),
    path('ajax/get-permisos-rol/', get_permisos_rol_ajax, name='get_permisos_rol_ajax'),
    path('ajax/actualizar-permisos-rol/', actualizar_permisos_rol_ajax, name='actualizar_permisos_rol_ajax'),
    
    # La URL 'categoria_detalle' probablemente ya no es necesaria con las DetailView específicas
    # path('categoria-detalle/', categoria_detail, name='categoria_detalle') 
]