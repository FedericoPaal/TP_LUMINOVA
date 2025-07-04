from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Prefetch
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib import colors
from App_LUMINOVA.models import Factura, ItemOrdenVenta


@login_required
def generar_pdf_factura(request, factura_id):
    # Obtener la factura y pre-cargar los datos necesarios de forma eficiente
    try:
        factura = (
            Factura.objects.select_related(
                "orden_venta__cliente"  # Para el cliente de la orden de venta
            )
            .prefetch_related(
                # Prefetch para los ítems de la orden de venta y sus productos terminados
                Prefetch(
                    "orden_venta__items_ov",
                    queryset=ItemOrdenVenta.objects.select_related(
                        "producto_terminado"
                    ),
                )
            )
            .get(id=factura_id)
        )
    except Factura.DoesNotExist:
        messages.error(request, "La factura solicitada no existe.")
        return redirect("App_LUMINOVA:ventas_lista_ov")  # O a donde sea apropiado

    orden_venta = factura.orden_venta  # Acceder a la orden de venta asociada

    # Crear la respuesta HTTP con el tipo de contenido PDF.
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="factura_{factura.numero_factura}.pdf"'
    )

    p = canvas.Canvas(response, pagesize=letter)
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    # ... (resto de tu código de generación de PDF como lo tenías) ...

    # --- COMIENZO DEL DIBUJO DEL PDF ---
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawString(1 * inch, height - 1 * inch, f"FACTURA N°: {factura.numero_factura}")

    # ... (Datos de la Empresa) ...
    p.setFont("Helvetica", 10)
    p.drawString(1 * inch, height - 1.5 * inch, "LUMINOVA S.A.")
    p.drawString(1 * inch, height - 1.65 * inch, "Calle Falsa 123, Ciudad")
    p.drawString(1 * inch, height - 1.80 * inch, "CUIT: 30-XXXXXXXX-X")

    p.setFont("Helvetica", 10)
    p.drawString(
        width - 3 * inch,
        height - 1.5 * inch,
        f"Fecha Emisión: {factura.fecha_emision.strftime('%d/%m/%Y')}",
    )
    p.drawString(
        width - 3 * inch, height - 1.65 * inch, f"OV N°: {orden_venta.numero_ov}"
    )

    # ... (Datos del Cliente, usando factura.orden_venta.cliente) ...
    p.setFont("Helvetica-Bold", 12)
    p.drawString(1 * inch, height - 2.5 * inch, "Cliente:")
    p.setFont("Helvetica", 10)
    p.drawString(1 * inch, height - 2.7 * inch, orden_venta.cliente.nombre)
    # ... (más datos del cliente) ...

    p.line(1 * inch, height - 3.5 * inch, width - 1 * inch, height - 3.5 * inch)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(1 * inch, height - 3.8 * inch, "Detalle de Productos/Servicios:")

    data = [["Cant.", "Descripción", "P. Unit.", "Subtotal"]]  # Encabezados de la tabla

    # Lógica para determinar qué ítems de la OV se incluyen en la factura
    # (basado en si sus OPs asociadas fueron completadas, o si eran de stock)
    ops_asociadas_a_ov = (
        orden_venta.ops_generadas.all()
    )  # Obtener todas las OPs de la OV
    productos_completados_en_ops_ids = {
        op.producto_a_producir_id
        for op in ops_asociadas_a_ov
        if op.estado_op and op.estado_op.nombre.lower() == "completada"
    }

    total_factura_recalculado_para_pdf = 0  # Para verificar o usar si es necesario

    for item in orden_venta.items_ov.all():  # Iterar sobre los items pre-cargados
        facturar_este_item = False
        if (
            not ops_asociadas_a_ov.exists()
        ):  # Si la OV no generó OPs (todo era de stock)
            facturar_este_item = True
        elif (
            item.producto_terminado_id in productos_completados_en_ops_ids
        ):  # Si la OP del producto se completó
            facturar_este_item = True

        # Podrías añadir una condición adicional: si la OV está en 'LISTA_ENTREGA' o 'COMPLETADA'
        # y un item no tuvo OP (asumiendo que era de stock), también facturarlo.
        elif not ops_asociadas_a_ov.filter(
            producto_a_producir=item.producto_terminado
        ).exists() and orden_venta.estado in ["LISTA_ENTREGA", "COMPLETADA"]:
            facturar_este_item = True

        if facturar_este_item:
            data.append(
                [
                    str(item.cantidad),
                    Paragraph(item.producto_terminado.descripcion, style_normal),
                    f"${item.precio_unitario_venta:.2f}",
                    f"${item.subtotal:.2f}",
                ]
            )
            total_factura_recalculado_para_pdf += item.subtotal

    # Es mejor usar el factura.total_facturado que ya fue calculado y guardado
    # a menos que quieras que el PDF siempre recalcule.
    # total_a_mostrar = factura.total_facturado
    total_a_mostrar = total_factura_recalculado_para_pdf  # O usa este si quieres que el PDF siempre refleje los items listados

    y_position = height - 4.2 * inch
    if len(data) > 1:  # Si hay ítems
        table = Table(
            data, colWidths=[0.5 * inch, 4.5 * inch, 1 * inch, 1 * inch]
        )  # Ajusta anchos
        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.darkblue,
                    ),  # Color de encabezado
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("ALIGN", (1, 1), (1, -1), "LEFT"),
                    ("ALIGN", (0, 1), (0, -1), "RIGHT"),  # Cantidad a la derecha
                    ("ALIGN", (2, 1), (3, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                    ("TOPPADDING", (0, 1), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        table.wrapOn(p, width - 2 * inch, y_position)
        table_height = table._height
        table.drawOn(p, 1 * inch, y_position - table_height)
        y_position -= table_height + 0.3 * inch
    else:
        p.drawString(1 * inch, y_position, "No hay ítems facturados para esta orden.")
        y_position -= 0.3 * inch

    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(
        width - 1 * inch, y_position, f"TOTAL: ${total_a_mostrar:.2f}"
    )  # Usar total_a_mostrar

    # ... (Notas Adicionales si las tienes en el modelo Factura)

    p.showPage()
    p.save()
    return response