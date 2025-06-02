# TP_LUMINOVA-main/App_LUMINOVA/models.py

from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone  # Importar timezone
from django.core.exceptions import ValidationError


# --- CATEGORÍAS Y ENTIDADES BASE ---
class CategoriaProductoTerminado(models.Model):
    nombre = models.CharField(
        max_length=100, unique=True, verbose_name="Nombre Categoría PT"
    )  # Aumentado max_length
    imagen = models.ImageField(upload_to="categorias_productos/", null=True, blank=True)

    class Meta:
        verbose_name = "Categoría de Producto Terminado"
        verbose_name_plural = "Categorías de Productos Terminados"

    def __str__(self):
        return self.nombre


class ProductoTerminado(models.Model):
    descripcion = models.CharField(max_length=255)  # Aumentado max_length
    categoria = models.ForeignKey(
        CategoriaProductoTerminado,
        on_delete=models.PROTECT,
        related_name="productos_terminados",
    )
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock = models.IntegerField(default=0)
    modelo = models.CharField(max_length=50, blank=True, null=True)
    potencia = models.IntegerField(blank=True, null=True)
    acabado = models.CharField(max_length=50, blank=True, null=True)
    color_luz = models.CharField(max_length=50, blank=True, null=True)
    material = models.CharField(max_length=50, blank=True, null=True)
    imagen = models.ImageField(null=True, blank=True, upload_to="productos_terminados/")

    def __str__(self):
        return f"{self.descripcion} (Modelo: {self.modelo or 'N/A'})"


class CategoriaInsumo(models.Model):
    nombre = models.CharField(
        max_length=100, unique=True, verbose_name="Nombre Categoría Insumo"
    )  # Aumentado max_length
    imagen = models.ImageField(upload_to="categorias_insumos/", null=True, blank=True)

    class Meta:
        verbose_name = "Categoría de Insumo"
        verbose_name_plural = "Categorías de Insumos"

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    contacto = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=25, blank=True)  # Aumentado max_length
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class Fabricante(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    contacto = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=25, blank=True)  # Aumentado max_length
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    descripcion = models.CharField(max_length=255)
    categoria = models.ForeignKey(
        CategoriaInsumo, on_delete=models.PROTECT, related_name="insumos"
    )
    fabricante = models.CharField(max_length=100, blank=True)
    # ELIMINADOS: precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # ELIMINADOS: tiempo_entrega = models.IntegerField(default=0, verbose_name="Tiempo Entrega (días)")
    # ELIMINADOS: proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name="insumos_proveedor")
    fabricante = models.ForeignKey(
        Fabricante,
        on_delete=models.SET_NULL,  # O models.PROTECT si no quieres que se borre el insumo si se borra el fabricante
        null=True,
        blank=True,  # Permite insumos sin fabricante asignado o si es desconocido
        related_name="insumos_fabricados",
    )
    imagen = models.ImageField(null=True, blank=True, upload_to="insumos/")
    stock = models.IntegerField(default=0)
    cantidad_en_pedido = models.PositiveIntegerField(
        default=0, verbose_name="Cantidad en Pedido"
    )
    # Puedes añadir un campo para un precio de referencia o último costo si lo deseas aquí,
    # pero el precio de compra específico vendrá de OfertaProveedor.
    # ultimo_costo_compra = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.descripcion


# --- NUEVO MODELO INTERMEDIO ---
class OfertaProveedor(models.Model):
    insumo = models.ForeignKey(
        Insumo, on_delete=models.CASCADE, related_name="ofertas_de_proveedores"
    )
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.CASCADE, related_name="provee_insumos"
    )
    precio_unitario_compra = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Precio de Compra Unitario"
    )
    tiempo_entrega_estimado_dias = models.IntegerField(
        default=0, verbose_name="Tiempo de Entrega Estimado (días)"
    )
    fecha_actualizacion_precio = models.DateTimeField(
        default=timezone.now, verbose_name="Última Actualización del Precio"
    )
    # Puedes añadir más campos aquí:
    # - codigo_producto_proveedor = models.CharField(max_length=50, blank=True, null=True)
    # - cantidad_minima_pedido = models.PositiveIntegerField(default=1)
    # - moneda = models.CharField(max_length=3, default='USD')
    # - notas_oferta = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = (
            "insumo",
            "proveedor",
        )  # Un proveedor ofrece un insumo específico una sola vez (con un precio/plazo)
        verbose_name = "Oferta de Proveedor por Insumo"
        verbose_name_plural = "Ofertas de Proveedores por Insumos"
        ordering = ["insumo__descripcion", "proveedor__nombre"]

    def __str__(self):
        return f"{self.insumo.descripcion} - {self.proveedor.nombre} (${self.precio_unitario_compra})"


class ComponenteProducto(models.Model):  # NUEVO: Bill Of Materials (BOM)
    producto_terminado = models.ForeignKey(
        ProductoTerminado,
        on_delete=models.CASCADE,
        related_name="componentes_requeridos",
    )
    insumo = models.ForeignKey(
        Insumo, on_delete=models.PROTECT
    )  # PROTECT para no borrar insumos si se borra el componente
    cantidad_necesaria = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("producto_terminado", "insumo")
        verbose_name = "Componente de Producto (BOM)"
        verbose_name_plural = "Componentes de Productos (BOM)"

    def __str__(self):
        return f"{self.cantidad_necesaria} x {self.insumo.descripcion} para {self.producto_terminado.descripcion}"


# --- MODELOS DE GESTIÓN ---
class Cliente(models.Model):
    nombre = models.CharField(max_length=150, unique=True)  # Aumentado max_length
    direccion = models.TextField(blank=True)
    telefono = models.CharField(max_length=25, blank=True)  # Aumentado max_length
    email = models.EmailField(unique=True, null=True, blank=True)

    def __str__(self):
        return self.nombre


class OrdenVenta(models.Model):  # NUEVO: Específico para Ventas
    ESTADO_CHOICES = [
        ("PENDIENTE", "Pendiente Confirmación"),
        ("CONFIRMADA", "Confirmada (Esperando Producción)"),
        ("INSUMOS_SOLICITADOS", "Insumos Solicitados"),
        ("PRODUCCION_INICIADA", "Producción Iniciada"),
        ("PRODUCCION_CON_PROBLEMAS", "Producción con Problemas"),
        ("LISTA_ENTREGA", "Lista para Entrega"),
        ("COMPLETADA", "Completada/Entregada"),
        ("CANCELADA", "Cancelada"),
    ]
    numero_ov = models.CharField(
        max_length=20, unique=True, verbose_name="N° Orden de Venta"
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="ordenes_venta"
    )
    fecha_creacion = models.DateTimeField(default=timezone.now)
    estado = models.CharField(
        max_length=50, choices=ESTADO_CHOICES, default="PENDIENTE"
    )
    total_ov = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00, verbose_name="Total OV"
    )
    notas = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"OV: {self.numero_ov} - {self.cliente.nombre}"

    def actualizar_total(self):
        nuevo_total = sum(item.subtotal for item in self.items_ov.all())
        if self.total_ov != nuevo_total:
            self.total_ov = nuevo_total
            self.save(
                update_fields=["total_ov"]
            )  # Solo guarda el campo total para evitar recursión


class ItemOrdenVenta(models.Model):  # NUEVO: Detalle de la OV
    orden_venta = models.ForeignKey(
        OrdenVenta, on_delete=models.CASCADE, related_name="items_ov"
    )
    producto_terminado = models.ForeignKey(ProductoTerminado, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario_venta = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Precio Unit. en Venta"
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario_venta
        super().save(*args, **kwargs)
        # La actualización del total de la OV se manejará en la vista o con una señal para evitar recursión infinita aquí.

    def __str__(self):
        return f"{self.cantidad} x {self.producto_terminado.descripcion} en OV {self.orden_venta.numero_ov}"


class EstadoOrden(
    models.Model
):  # Renombrar a EstadoOrdenProduccion o similar si es solo para OP
    # Este modelo lo tenías, pero su nombre "EstadoOrden" es genérico.
    # Si es específico para `OrdenProduccion`, sería mejor llamarlo `EstadoOrdenProduccion`.
    # Por ahora lo dejo como `EstadoOrden` y asumimos que los valores que cargues serán para OP.
    nombre = models.CharField(
        max_length=50, unique=True
    )  # Ej: Pendiente, En Proceso, Terminado

    def __str__(self):
        return self.nombre


class SectorAsignado(
    models.Model
):  # También, si es para OP, `SectorProduccion` sería más claro.
    nombre = models.CharField(
        max_length=50, unique=True
    )  # Ej: Grupo A, Taller Principal

    def __str__(self):
        return self.nombre


class OrdenProduccion(models.Model):
    numero_op = models.CharField(
        max_length=20, unique=True, verbose_name="N° Orden de Producción"
    )  # Cambiado de numero_orden
    orden_venta_origen = models.ForeignKey(
        OrdenVenta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_generadas",
    )

    producto_a_producir = models.ForeignKey(
        ProductoTerminado, on_delete=models.PROTECT, related_name="ordenes_produccion"
    )  # Cambiado related_name
    cantidad_a_producir = models.PositiveIntegerField()  # Cambiado de cantidad_prod
    estado_op = models.ForeignKey(
        EstadoOrden,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_estado",
    )

    # El campo 'cliente' en OrdenProduccion es redundante si ya está en OrdenVenta.
    # Se puede acceder a través de orden_venta_origen.cliente. Lo quitamos para normalizar.
    # cliente_op = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cliente (Referencia)")

    estado_op = models.ForeignKey(
        EstadoOrden,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_estado",
    )  # Cambiado related_name
    fecha_solicitud = models.DateTimeField(default=timezone.now)  # Añadido
    fecha_inicio_real = models.DateTimeField(null=True, blank=True)
    fecha_inicio_planificada = models.DateField(
        null=True, blank=True
    )  # Cambiado de fecha_inicio
    fecha_fin_real = models.DateTimeField(null=True, blank=True)
    fecha_fin_planificada = models.DateField(null=True, blank=True)  # Añadido
    sector_asignado_op = models.ForeignKey(
        SectorAsignado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_sector",
    )  # Cambiado related_name
    notas = models.TextField(null=True, blank=True, verbose_name="Notas")  # Añadido

    # Eliminado 'insumos_req' como ForeignKey a un solo Insumo. Se usará ComponenteProducto.
    # Eliminado 'nombre_categoria' y 'nombre_prod' ya que se accede vía producto_a_producir.

    def get_estado_op_display(self):  # Nombre del método que estás intentando llamar
        if self.estado_op:
            return self.estado_op.nombre
        return "Sin Estado Asignado"

    def __str__(self):
        return f"OP: {self.numero_op} - {self.cantidad_a_producir} x {self.producto_a_producir.descripcion}"


class Reportes(models.Model):
    orden_produccion_asociada = models.ForeignKey(
        OrdenProduccion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reportes_incidencia",
    )
    n_reporte = models.CharField(max_length=20, unique=True)
    fecha = models.DateTimeField(default=timezone.now)
    tipo_problema = models.CharField(max_length=100)
    informe_reporte = models.TextField(
        blank=True, null=True
    )  # O descripcion_problema si lo renombraste aquí

    # ESTOS SON LOS CAMPOS EN CUESTIÓN:
    reportado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  # Decide qué hacer si el usuario se elimina
        null=True,
        blank=True,
        related_name="reportes_creados",
    )
    sector_reporta = models.ForeignKey(
        SectorAsignado,
        on_delete=models.SET_NULL,  # Decide qué hacer si el sector se elimina
        null=True,
        blank=True,
        related_name="reportes_originados_aqui",
    )

    def __str__(self):
        op_num = (
            self.orden_produccion_asociada.numero_op
            if self.orden_produccion_asociada
            else "N/A"
        )
        return f"Reporte {self.n_reporte} (OP: {op_num})"


class Factura(models.Model):
    numero_factura = models.CharField(
        max_length=50, unique=True
    )  # Aumentado max_length
    orden_venta = models.OneToOneField(
        OrdenVenta, on_delete=models.PROTECT, related_name="factura_asociada"
    )
    fecha_emision = models.DateTimeField(
        default=timezone.now
    )  # Cambiado a DateTimeField
    total_facturado = models.DecimalField(
        max_digits=12, decimal_places=2
    )  # Aumentado max_digits

    def __str__(self):
        return f"Factura {self.numero_factura} para OV {self.orden_venta.numero_ov}"


class RolDescripcion(models.Model):
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, related_name="descripcion_extendida"
    )
    descripcion = models.TextField("Descripción del rol", blank=True)

    def __str__(self):
        return f"Descripción para rol: {self.group.name}"


class AuditoriaAcceso(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=255)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    def __str__(self):
        user_display = (
            self.usuario.username if self.usuario else "Usuario Desconocido/Eliminado"
        )
        return f"{user_display} - {self.accion} @ {self.fecha_hora.strftime('%Y-%m-%d %H:%M')}"


class Orden(models.Model):  # Este será para Órdenes de Compra
    TIPO_ORDEN_CHOICES = [
        ("compra", "Orden de Compra"),
        # Podrías añadir otros tipos si este modelo se vuelve más genérico en el futuro
    ]
    ESTADO_ORDEN_COMPRA_CHOICES = [
        ("BORRADOR", "Borrador"),
        ("PENDIENTE_APROBACION", "Pendiente Aprobación"),
        ("APROBADA", "Aprobada"),
        ("ENVIADA_PROVEEDOR", "Enviada al Proveedor"),
        ("CONFIRMADA_PROVEEDOR", "Confirmada por Proveedor"),
        ("EN_TRANSITO", "En Tránsito"),
        ("RECIBIDA_PARCIAL", "Recibida Parcialmente"),
        ("RECIBIDA_TOTAL", "Recibida Totalmente"),
        ("COMPLETADA", "Completada"),  # Si hay un paso post-recepción
        ("CANCELADA", "Cancelada"),
    ]

    numero_orden = models.CharField(
        max_length=20, unique=True, verbose_name="N° Orden de Compra"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_ORDEN_CHOICES, default="compra")
    fecha_creacion = models.DateTimeField(default=timezone.now)
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name="ordenes_de_compra_a_proveedor",
    )
    estado = models.CharField(
        max_length=30, choices=ESTADO_ORDEN_COMPRA_CHOICES, default="BORRADOR"
    )

    # Para el total de la OC, necesitaríamos items. Similar a OrdenVenta e ItemOrdenVenta.
    # Por ahora, lo dejamos simple o asumimos un solo insumo por OC.
    # Si es un solo insumo:
    insumo_principal = models.ForeignKey(
        Insumo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Insumo Principal",
    )
    # El campo 'proveedor' en Orden se refiere al proveedor AL QUE SE LE HACE LA ORDEN.
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name="ordenes_de_compra_a_proveedor",
    )
    cantidad_principal = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Cantidad Insumo Principal"
    )
    precio_unitario_compra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Precio Unit. Compra (de la oferta)",
    )

    total_orden_compra = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )

    fecha_estimada_entrega = models.DateField(null=True, blank=True)
    numero_tracking = models.CharField(max_length=50, null=True, blank=True)
    notas = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"OC: {self.numero_orden} - Proveedor: {self.proveedor.nombre}"

    def get_estado_display_custom(self):
        # Esto es idéntico a get_estado_display(), pero puedes personalizarlo si es necesario.
        # Por ejemplo, podrías añadir lógica extra aquí.
        return dict(self.ESTADO_ORDEN_COMPRA_CHOICES).get(self.estado, self.estado)

    def save(self, *args, **kwargs):
        if (
            self.insumo_principal
            and self.cantidad_principal
            and self.precio_unitario_compra is not None
        ):
            self.total_orden_compra = (
                self.cantidad_principal * self.precio_unitario_compra
            )
        # Si vas a tener múltiples items, el total se calcularía iterando los items.
        super().save(*args, **kwargs)


# Si necesitas múltiples insumos por Orden de Compra, crearías:
# class ItemOrdenCompra(models.Model):
#     orden_compra = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name='items_oc')
#     insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT)
#     cantidad = models.PositiveIntegerField()
#     precio_unitario_compra = models.DecimalField(max_digits=10, decimal_places=2)
#     subtotal = models.DecimalField(max_digits=12, decimal_places=2)

#     def save(self, *args, **kwargs):
#         self.subtotal = self.cantidad * self.precio_unitario_compra
#         super().save(*args, **kwargs)
#         self.orden_compra.actualizar_total_oc() # Necesitarías un método en Orden para actualizar
