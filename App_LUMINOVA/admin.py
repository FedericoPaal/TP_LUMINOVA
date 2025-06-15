# TP_LUMINOVA-main/App_LUMINOVA/admin.py

from django.contrib import admin
from .models import (
    CategoriaProductoTerminado, ProductoTerminado, CategoriaInsumo, Insumo,
    ComponenteProducto, Proveedor, Cliente,
    OrdenVenta, ItemOrdenVenta,
    EstadoOrden, SectorAsignado, OrdenProduccion, # Usando tus nombres actuales para EstadoOrden y SectorAsignado
    Reportes, Factura, RolDescripcion, AuditoriaAcceso, Fabricante, OfertaProveedor, Orden
)

class OfertaProveedorInline(admin.TabularInline): # O admin.StackedInline
    model = OfertaProveedor
    extra = 1
    fields = ('proveedor', 'precio_unitario_compra', 'tiempo_entrega_estimado_dias', 'fecha_actualizacion_precio')
    autocomplete_fields = ['proveedor']
    verbose_name = "Oferta de Proveedor"
    verbose_name_plural = "Ofertas de Proveedores para este Insumo"

class ComponenteProductoInline(admin.TabularInline):
    model = ComponenteProducto
    extra = 1
    autocomplete_fields = ['insumo']
    verbose_name_plural = "Componentes Requeridos para este Producto (BOM)"
    fields = ('insumo', 'cantidad_necesaria')

@admin.register(ProductoTerminado)
class ProductoTerminadoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'categoria', 'stock', 'precio_unitario', 'modelo')
    list_filter = ('categoria',)
    search_fields = ('descripcion', 'modelo')
    inlines = [ComponenteProductoInline]
    autocomplete_fields = ['categoria']

@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'categoria', 'stock', 'fabricante', 'mostrar_ofertas_resumen') # 'mostrar_ofertas_resumen' es el nombre del método
    list_filter = ('categoria', 'fabricante')
    search_fields = ('descripcion', 'fabricante', 'categoria__nombre')
    autocomplete_fields = ['categoria']
    inlines = [OfertaProveedorInline]

    # No necesitas @admin.display aquí si el método está en la clase ModelAdmin
    def mostrar_ofertas_resumen(self, obj):
        # 'obj' aquí es una instancia del modelo Insumo
        ofertas = obj.ofertas_de_proveedores.all() # Usando el related_name de OfertaProveedor.insumo
        if not ofertas:
            return "Ninguna"
        
        resumen = []
        for o in ofertas[:3]: # Mostrar hasta 3 ofertas
            resumen.append(f"{o.proveedor.nombre}: ${o.precio_unitario_compra} ({o.tiempo_entrega_estimado_dias}d)")
        
        if ofertas.count() > 3:
            resumen.append("...")
        
        return ", ".join(resumen)
    
    mostrar_ofertas_resumen.short_description = 'Ofertas de Proveedores (Resumen)' # Esto sí es útil para el 

class ItemOrdenVentaInline(admin.TabularInline):
    model = ItemOrdenVenta
    fields = ('producto_terminado', 'cantidad', 'precio_unitario_venta', 'subtotal')
    readonly_fields = ('subtotal',)
    extra = 1
    autocomplete_fields = ['producto_terminado']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto_terminado":
            kwargs["queryset"] = ProductoTerminado.objects.order_by('descripcion')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(OrdenVenta)
class OrdenVentaAdmin(admin.ModelAdmin):
    list_display = ('numero_ov', 'cliente', 'fecha_creacion', 'estado', 'total_ov')
    list_filter = ('estado', 'fecha_creacion', 'cliente')
    search_fields = ('numero_ov', 'cliente__nombre')
    inlines = [ItemOrdenVentaInline]
    readonly_fields = ('fecha_creacion', 'total_ov')

@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(admin.ModelAdmin):
    list_display = ('numero_op', 'producto_a_producir', 'cantidad_a_producir', 'get_estado_op_nombre', 'get_sector_asignado_nombre', 'fecha_solicitud')
    list_filter = ('estado_op', 'sector_asignado_op', 'fecha_solicitud')
    search_fields = ('numero_op', 'producto_a_producir__descripcion', 'orden_venta_origen__numero_ov', 'cliente_final__nombre')
    autocomplete_fields = ['producto_a_producir', 'orden_venta_origen', 'estado_op', 'sector_asignado_op']
    readonly_fields = ('fecha_solicitud',)

    @admin.display(description='Estado')
    def get_estado_op_nombre(self, obj):
        return obj.estado_op.nombre if obj.estado_op else '-'

    @admin.display(description='Sector Asignado')
    def get_sector_asignado_nombre(self, obj):
        return obj.sector_asignado_op.nombre if obj.sector_asignado_op else '-'


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    search_fields = ('nombre', 'email')

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    search_fields = ('nombre',)

@admin.register(CategoriaInsumo)
class CategoriaInsumoAdmin(admin.ModelAdmin):
    search_fields = ('nombre',)

@admin.register(CategoriaProductoTerminado)
class CategoriaProductoTerminadoAdmin(admin.ModelAdmin):
    search_fields = ('nombre',)

@admin.register(EstadoOrden)
class EstadoOrdenAdmin(admin.ModelAdmin):
    search_fields = ['nombre']

@admin.register(SectorAsignado)
class SectorAsignadoAdmin(admin.ModelAdmin):
    search_fields = ['nombre']

# Registros simples
admin.site.register(Reportes)
admin.site.register(Factura)
admin.site.register(RolDescripcion)
admin.site.register(AuditoriaAcceso)
#admin.site.register(CategoriaProductoTerminado)
#admin.site.register(Proveedor)

admin.site.register(ComponenteProducto) # Descomentado, puede ser útil para verlos todos
admin.site.register(Fabricante)
# admin.site.register(Orden) # Descomenta y configura si quieres 'Orden' en el admin

# Si quieres un admin más detallado para Orden (Órdenes de Compra)
@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('numero_orden', 'tipo', 'proveedor', 'insumo_principal', 'cantidad_principal', 'estado', 'fecha_creacion', 'total_orden_compra')
    list_filter = ('tipo', 'estado', 'proveedor', 'fecha_creacion')
    search_fields = ('numero_orden', 'proveedor__nombre', 'insumo_principal__descripcion', 'notas')
    autocomplete_fields = ['proveedor', 'insumo_principal']
    readonly_fields = ('fecha_creacion', 'total_orden_compra') # El total se calcula en el save del modelo
    fieldsets = (
        (None, {
            'fields': ('numero_orden', 'tipo', 'estado')
        }),
        ('Detalles del Proveedor y Pedido', {
            'fields': ('proveedor', 'insumo_principal', 'cantidad_principal', 'precio_unitario_compra')
        }),
        ('Seguimiento y Entrega', {
            'fields': ('fecha_estimada_entrega', 'numero_tracking')
        }),
        ('Información Adicional', {
            'fields': ('notas', 'total_orden_compra', 'fecha_creacion')
        }),
    )

from .models import LoteProductoTerminado

@admin.register(LoteProductoTerminado)
class LoteProductoTerminadoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'op_asociada', 'cantidad', 'enviado', 'fecha_creacion')
    list_filter = ('enviado', 'producto')
    search_fields = ('producto__descripcion', 'op_asociada__numero_op')