from django.db.models import Model

def generar_siguiente_numero_documento(model: Model, prefix: str, field_name: str) -> str:
    """
    Genera el siguiente número de documento secuencial para un modelo dado.

    Args:
        model: La clase del modelo de Django (ej: OrdenVenta).
        prefix: El prefijo para el número (ej: 'OV').
        field_name: El nombre del campo que almacena el número (ej: 'numero_ov').

    Returns:
        Una cadena con el nuevo número de documento único (ej: 'OV-00005').
    """
    
    last_item = model.objects.order_by('id').last()
    next_id = (last_item.id + 1) if last_item else 1

    while True:
        # Crea un diccionario para el filtro dinámico
        filter_kwargs = {f"{field_name}__exact": f"{prefix}-{str(next_id).zfill(5)}"}

        if not model.objects.filter(**filter_kwargs).exists():
            return f"{prefix}-{str(next_id).zfill(5)}"
        next_id += 1