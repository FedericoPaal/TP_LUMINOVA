from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import AuditoriaAcceso

@receiver(user_logged_in)
def registrar_acceso(sender, user, request, **kwargs):
    AuditoriaAcceso.objects.create(
        usuario=user,
        accion="Inicio de sesión"
    )