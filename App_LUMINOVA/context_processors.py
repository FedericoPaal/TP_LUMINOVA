# TP_LUMINOVA-main/App_LUMINOVA/context_processors.py
from .models import OrdenProduccion, Reportes, Orden

def notificaciones_context(request):
    if not request.user.is_authenticated:
        return {}

    ops_con_problemas_count = Reportes.objects.filter(
        resuelto=False,
        orden_produccion_asociada__isnull=False
    ).values('orden_produccion_asociada_id').distinct().count()

    solicitudes_insumos_count = OrdenProduccion.objects.filter(
        estado_op__nombre__iexact='Insumos Solicitados'
    ).count()
    
    ocs_para_aprobar_count = Orden.objects.filter(
        tipo='compra',
        estado='BORRADOR'
    ).count()
    
    total_notificaciones = ops_con_problemas_count + solicitudes_insumos_count + ocs_para_aprobar_count

    return {
        'ops_con_problemas_count': ops_con_problemas_count,
        'solicitudes_insumos_count': solicitudes_insumos_count,
        'ocs_para_aprobar_count': ocs_para_aprobar_count,
        'total_notificaciones': total_notificaciones,
    }