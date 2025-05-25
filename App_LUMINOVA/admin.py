# TP_LUMINOVA-main/App_LUMINOVA/admin.py

from django.contrib import admin
from .models import (
    CategoriaProductoTerminado, ProductoTerminado, CategoriaInsumo, Insumo,
    ComponenteProducto, Proveedor, Cliente,
    OrdenVenta, ItemOrdenVenta,
    EstadoOrden, SectorAsignado, OrdenProduccion, # Usando tus nombres actuales para EstadoOrden y SectorAsignado
    Reportes, Factura, RolDescripcion, AuditoriaAcceso, Fabricante
)

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
    list_display = ('descripcion', 'categoria', 'proveedor', 'stock', 'precio_unitario') # cambiado a proveedor
    list_filter = ('categoria', 'proveedor')
    search_fields = ('descripcion', 'fabricante', 'categoria__nombre', 'proveedor__nombre') # Asegurado que funcione
    autocomplete_fields = ['categoria', 'proveedor']

class ItemOrdenVentaInline(admin.TabularInline):
    model = ItemOrdenVenta
    fields = ('producto_terminado', 'cantidad', 'precio_unitario_venta', 'subtotal')
    readonly_fields = ('subtotal',)
    extra = 1
    autocomplete_fields = ['producto_terminado'] # ProductoTerminadoAdmin ya tiene search_fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto_terminado":
            kwargs["queryset"] = ProductoTerminado.objects.order_by('descripcion')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(OrdenVenta)
class OrdenVentaAdmin(admin.ModelAdmin):
    list_display = ('numero_ov', 'cliente', 'fecha_creacion', 'estado', 'total_ov')
    list_filter = ('estado', 'fecha_creacion', 'cliente')
    search_fields = ('numero_ov', 'cliente__nombre') # <--- AÑADIDO/ASEGURADO
    inlines = [ItemOrdenVentaInline]
    readonly_fields = ('fecha_creacion', 'total_ov')

@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(admin.ModelAdmin):
    list_display = ('numero_op', 'producto_a_producir', 'cantidad_a_producir', 'get_estado_op_nombre', 'get_sector_asignado_nombre', 'fecha_solicitud')
    list_filter = ('estado_op', 'sector_asignado_op', 'fecha_solicitud')
    search_fields = ('numero_op', 'producto_a_producir__descripcion', 'orden_venta_origen__numero_ov', 'cliente_final__nombre') # Añadido cliente_final__nombre
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
    search_fields = ('nombre', 'email') # Ya lo tenías

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    search_fields = ('nombre',) # Ya lo tenías

@admin.register(CategoriaInsumo)
class CategoriaInsumoAdmin(admin.ModelAdmin):
    search_fields = ('nombre',) # Ya lo tenías

@admin.register(CategoriaProductoTerminado)
class CategoriaProductoTerminadoAdmin(admin.ModelAdmin):
    search_fields = ('nombre',) # Ya lo tenías

@admin.register(EstadoOrden) # Usando tu modelo EstadoOrden
class EstadoOrdenAdmin(admin.ModelAdmin):
    search_fields = ['nombre'] # <--- AÑADIDO

@admin.register(SectorAsignado) # Usando tu modelo SectorAsignado
class SectorAsignadoAdmin(admin.ModelAdmin):
    search_fields = ['nombre'] # <--- AÑADIDO

# Registros simples
admin.site.register(Reportes)
admin.site.register(Factura)
admin.site.register(RolDescripcion)
admin.site.register(AuditoriaAcceso)
#admin.site.register(CategoriaProductoTerminado)
#admin.site.register(Proveedor)
admin.site.register(ComponenteProducto) # Descomentado, puede ser útil para verlos todos
admin.site.register(Fabricante)