from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save
from .models import AuditoriaAcceso, HistorialOV, OrdenProduccion, OrdenVenta

@receiver(user_logged_in)
def registrar_acceso(sender, user, request, **kwargs):
    AuditoriaAcceso.objects.create(
        usuario=user,
        accion="Inicio de sesión"
    )

@receiver(post_save, sender=OrdenVenta)
def registrar_creacion_y_cambio_estado_ov(sender, instance, created, **kwargs):
    """
    Registra la creación de una OV y los cambios en su estado.
    """
    if created:
        HistorialOV.objects.create(
            orden_venta=instance,
            descripcion=f"Orden de Venta creada en estado '{instance.get_estado_display()}'."
        )
    else:
        # Para registrar cambios de estado, necesitamos el estado anterior.
        # Esto se puede hacer en pre_save.
        pass

@receiver(pre_save, sender=OrdenVenta)
def registrar_cambio_estado_ov_presave(sender, instance, **kwargs):
    """
    Compara el estado antiguo con el nuevo antes de guardar y registra el cambio.
    """
    if not instance.pk: # Si es un objeto nuevo, no hacer nada aquí.
        return
    try:
        estado_anterior = OrdenVenta.objects.get(pk=instance.pk).estado
        if estado_anterior != instance.estado:
            HistorialOV.objects.create(
                orden_venta=instance,
                descripcion=f"Estado de la Orden de Venta cambió de '{OrdenVenta.objects.get(pk=instance.pk).get_estado_display()}' a '{instance.get_estado_display()}'."
            )
    except OrdenVenta.DoesNotExist:
        pass # El objeto aún no existe en la DB

@receiver(post_save, sender=OrdenProduccion)
def registrar_cambio_estado_op(sender, instance, created, **kwargs):
    """
    Registra eventos en el historial de la OV cuando el estado de una OP asociada cambia.
    """
    if instance.orden_venta_origen:
        if created:
             HistorialOV.objects.create(
                orden_venta=instance.orden_venta_origen,
                descripcion=f"Se generó la Orden de Producción {instance.numero_op} para el producto '{instance.producto_a_producir.descripcion}'."
            )
        else:
            # Similar a la OV, necesitamos el estado anterior.
            pass

@receiver(pre_save, sender=OrdenProduccion)
def registrar_cambio_estado_op_presave(sender, instance, **kwargs):
    """
    Compara el estado antiguo de la OP con el nuevo y registra el cambio en la OV.
    """
    if not instance.pk or not instance.orden_venta_origen:
        return
    try:
        op_anterior = OrdenProduccion.objects.get(pk=instance.pk)
        if op_anterior.estado_op != instance.estado_op:
            descripcion_evento = f"La OP {instance.numero_op} ('{instance.producto_a_producir.descripcion}') cambió su estado a '{instance.estado_op.nombre if instance.estado_op else 'N/A'}'."
            HistorialOV.objects.create(
                orden_venta=instance.orden_venta_origen,
                descripcion=descripcion_evento
            )
    except OrdenProduccion.DoesNotExist:
        pass