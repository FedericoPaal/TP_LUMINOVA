from django.shortcuts import redirect
from django.urls import reverse

from .models import PasswordChangeRequired


class PasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_paths = [
            reverse("App_LUMINOVA:change_password"),
            reverse("App_LUMINOVA:logout"),
        ]

    def __call__(self, request):
        # Primero, procesamos la solicitud para obtener la respuesta.
        # Esto permite que otras partes de Django (como la sesión) se carguen.
        response = self.get_response(request)

        # El middleware solo actúa si el usuario está autenticado y no es superusuario
        # (los superusuarios pueden necesitar acceso total para depurar)
        if not request.user.is_authenticated or request.user.is_superuser:
            return response

        # Ignorar peticiones para archivos estáticos/media y para el panel de admin de Django
        if request.path_info.startswith(("/static/", "/media/", "/admin/")):
            return response

        # Si el usuario está en una de las páginas permitidas, no hacemos nada más
        if request.path_info in self.allowed_paths:
            return response

        # La comprobación clave: ¿Necesita cambiar la contraseña?
        if PasswordChangeRequired.objects.filter(user=request.user).exists():
            # Si está aquí, significa que intentó acceder a una página no permitida.
            # Lo redirigimos forzosamente.
            return redirect("App_LUMINOVA:change_password")

        # Si no se cumple ninguna de las condiciones de redirección, devolvemos la respuesta original.
        return response
