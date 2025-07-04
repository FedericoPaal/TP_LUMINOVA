from django.urls import path, include
from ..views import (
    lista_usuarios,
    crear_usuario,
    editar_usuario,
    eliminar_usuario,
    roles_permisos_view,
    auditoria_view,
)

from . import ajax_urls

# Rutas de Administración
urlpatterns = [
    path("admin/usuarios/", lista_usuarios, name="lista_usuarios"),
    path("admin/usuarios/crear/", crear_usuario, name="crear_usuario"),
    path("admin/usuarios/editar/<int:id>/", editar_usuario, name="editar_usuario"),
    path(
        "admin/usuarios/eliminar/<int:id>/", eliminar_usuario, name="eliminar_usuario"
    ),
    path("admin/roles-permisos/", roles_permisos_view, name="roles-permisos"),
    path("admin/auditoria/", auditoria_view, name="auditoria"),
    
    path('ajax/', include(ajax_urls))
]