from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib import colors

# Importante: Usamos importación relativa porque estamos dentro de la misma app.
from ..models import OrdenVenta, ItemOrdenVenta, OrdenProduccion


def generar_pdf_factura(factura):
    """
    Genera un HttpResponse con el contenido de un PDF para una factura.
    Esta función NO es una vista. Recibe un objeto 'Factura' y devuelve una respuesta HTTP.
    """
    orden_venta = factura.orden_venta

    # Crear la respuesta HTTP con el tipo de contenido PDF.
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="factura_{factura.numero_factura}.pdf"'
    )

    p = canvas.Canvas(response, pagesize=letter)
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]

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

    # ... (Datos del Cliente) ...
    p.setFont("Helvetica-Bold", 12)
    p.drawString(1 * inch, height - 2.5 * inch, "Cliente:")
    p.setFont("Helvetica", 10)
    p.drawString(1 * inch, height - 2.7 * inch, orden_venta.cliente.nombre)
    p.line(1 * inch, height - 3.5 * inch, width - 1 * inch, height - 3.5 * inch)

    p.setFont("Helvetica-Bold", 12)
    p.drawString(1 * inch, height - 3.8 * inch, "Detalle de Productos/Servicios:")

    data = [["Cant.", "Descripción", "P. Unit.", "Subtotal"]]

    # Tu lógica para determinar qué ítems se facturan es correcta.
    ops_asociadas_a_ov = orden_venta.ops_generadas.all()
    productos_completados_ids = {
        op.producto_a_producir_id
        for op in ops_asociadas_a_ov
        if op.estado_op and op.estado_op.nombre.lower() == "completada"
    }

    total_calculado_pdf = 0
    for item in orden_venta.items_ov.all():
        if item.producto_terminado_id in productos_completados_ids:
            data.append(
                [
                    str(item.cantidad),
                    Paragraph(item.producto_terminado.descripcion, style_normal),
                    f"${item.precio_unitario_venta:.2f}",
                    f"${item.subtotal:.2f}",
                ]
            )
            total_calculado_pdf += item.subtotal

    y_position = height - 4.2 * inch
    if len(data) > 1:
        table = Table(data, colWidths=[0.5 * inch, 4.5 * inch, 1 * inch, 1 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("ALIGN", (1, 1), (1, -1), "LEFT"),
                    ("ALIGN", (0, 1), (0, -1), "RIGHT"),
                    ("ALIGN", (2, 1), (3, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        table.wrapOn(p, width - 2 * inch, y_position)
        table_height = table._height
        table.drawOn(p, 1 * inch, y_position - table_height)
        y_position -= table_height + 0.3 * inch

    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(width - 1 * inch, y_position, f"TOTAL: ${factura.total_facturado:.2f}")

    p.showPage()
    p.save()
    return response