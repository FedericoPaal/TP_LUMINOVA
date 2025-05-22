"""
URL configuration for Proyecto_LUMINOVA project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import *

app_name = 'App_LUMINOVA'

urlpatterns = [
    path("", inicio, name="inicio"),
    path("compras/", compras, name="compras"),
    path("produccion/", produccion, name="produccion"),
    path("ventas/", ventas, name="ventas"),
    path("deposito/", deposito, name="deposito"),
    path("control_calidad/", control_calidad, name="control_calidad"),

    path('login/', auth_views.LoginView.as_view(template_name='login.html', next_page='App_LUMINOVA:inicio'), name='login'),  # Página de login
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),  # Cerrar sesión

#  Paths para los botones del sidebar de Admin

    path('dashboard/', dashboard_view, name='dashboard'),
    #path('usuarios/', usuarios, name='usuarios'),
    path('roles-permisos/', roles_permisos_view, name='roles-permisos'),
    path('auditoria/', auditoria_view, name='auditoria'),

    # Path para el crud de Usuario
    path('usuarios/', lista_usuarios, name='lista_usuarios'),
    path('usuarios/crear/', crear_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:id>/', editar_usuario, name='editar_usuario'),
    path('usuarios/eliminar/<int:id>/', eliminar_usuario, name='eliminar_usuario'),

#  Paths para los botones del sidebar de Compras
    path("desglose/", desglose, name="desglose"),
    path("seguimiento/", seguimiento, name="seguimiento"),
    path("tracking/", tracking, name="tracking"),
    path("desglose2/", desglose2, name="desglose2"),

#  Paths para los botones del sidebar de Produccion
    path('ordenes/', ordenes, name='ordenes'),
    path('planificacion/', planificacion, name='planificacion'),
    path('reportes/', reportes, name='reportes'),

#  Paths para el boton Seleccionar de la tabla de OP// los botones del sidebar de Deposito
    path('depo-seleccion/', depo_seleccion, name='depo_seleccion'),
    path('depo-enviar/', depo_enviar, name='depo_enviar'),

    path('categorias_i/', Categoria_IListView.as_view(), name='categoria_i_list'),
    path('categorias_i/<pk>', Categoria_IDetailView.as_view(), name='categoria_i_detail'),
    path('categorias_i/nuevo/', Categoria_ICreateView.as_view(), name='categoria_i_create'),
    path('categorias_i/editar/<pk>', Categoria_IUpdateView.as_view(), name='categoria_i_edit'),
    path('categorias_i/eliminar/<pk>', Categoria_IDeleteView.as_view(), name='categoria_i_delete'),

    path('categorias_pt/', Categoria_PTListView.as_view(), name='categoria_pt_list'),
    path('categorias_pt/<pk>', Categoria_PTDetailView.as_view(), name='categoria_pt_detail'),
    path('categorias_pt/nuevo/', Categoria_PTCreateView.as_view(), name='categoria_pt_create'),
    path('categorias_pt/editar/<pk>', Categoria_PTUpdateView.as_view(), name='categoria_pt_edit'),
    path('categorias_pt/eliminar/<pk>', Categoria_PTDeleteView.as_view(), name='categoria_pt_delete'),

    path('insumos/', InsumosListView.as_view(), name='insumos_list'),
    path('insumos/<pk>', InsumoDetailView.as_view(), name='insumo_detail'),
    path('insumos/nuevo/', InsumoCreateView.as_view(), name='insumo_create'),
    path('insumos/editar/<pk>', InsumoUpdateView.as_view(), name='insumo_edit'),
    path('insumos/eliminar/<pk>', InsumoDeleteView.as_view(), name='insumo_delete'),

    path('productosterminados/',ProductoTerminadosListView.as_view(), name='productos_terminados_list'),
    path('productosterminados/<pk>', ProductoTerminadoDetailView.as_view(), name='producto_terminado_detail'),
    path('productosterminados/nuevo/', ProductoTerminadoCreateView.as_view(), name='producto_terminado_create'),
    path('productosterminados/editar/<pk>', ProductoTerminadoUpdateView.as_view(), name='producto_terminado_edit'),
    path('productosterminados/eliminar/<pk>', ProductoTerminadoDeleteView.as_view(), name='producto_terminado_delete'),

    path('categoria-detalle/', categoria_detail, name='categoria_detalle')

]