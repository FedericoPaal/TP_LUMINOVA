def es_admin(user):
    """Verifica si un usuario es superusuario o pertenece al grupo 'administrador'."""
    return user.groups.filter(name='administrador').exists() or user.is_superuser

def es_admin_o_rol(user, roles_permitidos=None):
    """Verifica si el usuario es superusuario, admin o pertenece a una lista de roles."""
    if user.is_superuser:
        return True
    if roles_permitidos is None:
        roles_permitidos = []
    # Agregamos 'administrador' a los roles permitidos por defecto
    if 'administrador' not in roles_permitidos:
        roles_permitidos.append('administrador')
    return user.groups.filter(name__in=[rol.lower() for rol in roles_permitidos]).exists()