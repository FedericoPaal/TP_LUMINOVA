from datetime import timedelta, timezone
import logging
from django import apps, forms
from django.contrib.auth.models import  Group, Permission
from .models import (
    Cliente,
    Factura,
    OfertaProveedor,
    Orden, 
    Proveedor, # Asegúrate de importar el modelo Proveedor
    OrdenVenta, ItemOrdenVenta, ProductoTerminado,
    OrdenProduccion, EstadoOrden, SectorAsignado, CategoriaInsumo, Insumo, CategoriaProductoTerminado,SectorAsignado, Reportes
)
from django.db.models import Q

logger = logging.getLogger(__name__)

class RolForm(forms.Form):
    nombre = forms.CharField(label="Nombre del Rol", max_length=150, required=True,
                             widget=forms.TextInput(attrs={'class': 'form-control'}))
    descripcion = forms.CharField(label="Descripción", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=False)
    rol_id = forms.IntegerField(widget=forms.HiddenInput(), required=False) # Para edición

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        rol_id = self.cleaned_data.get('rol_id')
        query = Group.objects.filter(name__iexact=nombre)
        if rol_id: # Si es edición, excluir el rol actual de la verificación de unicidad
            query = query.exclude(pk=rol_id)
        if query.exists():
            raise forms.ValidationError("Un rol con este nombre ya existe.")
        return nombre

class PermisosRolForm(forms.Form):
    rol_id = forms.IntegerField(widget=forms.HiddenInput())
    permisos_ids = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple, # No se usará directamente en el HTML, pero define el tipo
        required=False
    )

# TP_LUMINOVA-main/App_LUMINOVA/forms.py

from django import forms
from .models import (
    Cliente, Proveedor, OrdenVenta, ItemOrdenVenta, ProductoTerminado,
    OrdenProduccion, EstadoOrden, SectorAsignado, CategoriaInsumo, Insumo, CategoriaProductoTerminado
) # EstadoOrden y SectorAsignado son los que tenías para OP

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'direccion', 'telefono', 'email']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Nombre completo del cliente'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control mb-2', 'rows': 2, 'placeholder': 'Dirección completa'}), # Menos filas
            'telefono': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Número de teléfono'}),
            'email': forms.EmailInput(attrs={'class': 'form-control mb-2', 'placeholder': 'correo@ejemplo.com'}),
        }

class ItemOrdenVentaForm(forms.ModelForm):
    class Meta:
        model = ItemOrdenVenta
        fields = ['producto_terminado', 'cantidad', 'precio_unitario_venta']
        widgets = {
            'producto_terminado': forms.Select(attrs={'class': 'form-select form-select-sm producto-selector-ov-item'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control form-control-sm cantidad-ov-item', 'min': '1', 'value': '1'}),
            'precio_unitario_venta': forms.NumberInput(attrs={'class': 'form-control form-control-sm precio-ov-item', 'step': '0.01', 'readonly': True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto_terminado'].queryset = ProductoTerminado.objects.all().order_by('descripcion')
        self.fields['producto_terminado'].empty_label = "Seleccionar Producto..."
        # Mostrar precio y stock en el dropdown del producto para ayudar al usuario
        self.fields['producto_terminado'].label_from_instance = lambda obj: f"{obj.descripcion} (Stock: {obj.stock} | P.U: ${obj.precio_unitario})"
        # El precio unitario se llenará con JS al seleccionar el producto.

# FormSet para los ítems de la Orden de Venta
ItemOrdenVentaFormSet = forms.inlineformset_factory(
    OrdenVenta, ItemOrdenVenta, form=ItemOrdenVentaForm,
    fields=['producto_terminado', 'cantidad', 'precio_unitario_venta'],
    extra=1, # Empieza con 1 form para ítem
    can_delete=True, # Permite marcar para eliminar ítems existentes
    can_delete_extra=True # Permite eliminar forms "extra" añadidos por JS antes de guardar
)

class OrdenVentaForm(forms.ModelForm):
    class Meta:
        model = OrdenVenta
        fields = ['numero_ov', 'cliente', 'estado', 'notas']
        widgets = {
            'numero_ov': forms.TextInput(attrs={'class': 'form-control'}),
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'estado': forms.Select(attrs={'class': 'form-select'}), 
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Anotaciones adicionales...'}),
        }
        labels = {
            'numero_ov': "Nº Orden de Venta",
            'cliente': "Cliente Asociado",
            'estado': "Estado Actual de la Orden",
            'notas': "Notas Adicionales"
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) # Llamar al __init__ del padre primero

        self.fields['cliente'].queryset = Cliente.objects.all().order_by('nombre')
        self.fields['cliente'].empty_label = "Seleccione un Cliente..."
        
        # Las choices para el campo 'estado' ya se toman del modelo OrdenVenta.ESTADO_CHOICES
        
        instance = getattr(self, 'instance', None)
        is_new_instance = instance is None or not instance.pk

        if is_new_instance:
            # Para una nueva OV (creación):
            # 1. Establecer el valor inicial que se mostrará en el campo.
            self.initial['estado'] = 'PENDIENTE' # El valor que se seleccionará por defecto
            
            # 2. Deshabilitar el widget para que el usuario no pueda cambiarlo visualmente.
            self.fields['estado'].widget.attrs['disabled'] = True
            
            # 3. Hacer el campo no requerido a nivel de validación del formulario.
            #    Esto es crucial para que form.is_valid() no falle si el campo está deshabilitado
            #    y, por lo tanto, no se envía en el POST. La vista se encargará de setear el valor.
            self.fields['estado'].required = False 
        else: # Es una instancia existente (edición)
            # Asegurarse de que el campo 'estado' esté habilitado y sea requerido.
            if 'disabled' in self.fields['estado'].widget.attrs:
                del self.fields['estado'].widget.attrs['disabled']
            # También es buena práctica asegurar que 'disabled' como atributo del campo no esté True
            if hasattr(self.fields['estado'], 'disabled'): # Verificar si el atributo existe
                 self.fields['estado'].disabled = False
            self.fields['estado'].required = True # En edición, el estado sí debe ser enviado

# Formulario para actualizar una OP (usado en la vista de detalle de OP)
class OrdenProduccionUpdateForm(forms.ModelForm):
    class Meta:
        model = OrdenProduccion
        fields = ['estado_op', 'sector_asignado_op', 'fecha_inicio_planificada', 'fecha_fin_planificada', 'notas']
        widgets = {
            'estado_op': forms.Select(attrs={'class': 'form-select'}),
            'sector_asignado_op': forms.Select(attrs={'class': 'form-select'}),
            'fecha_inicio_planificada': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'DD/MM/YYYY'}),
            'fecha_fin_planificada': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'DD/MM/YYYY'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas adicionales de producción...'}),
        }
        labels = {
            'estado_op': 'Cambiar Estado de OP',
            'sector_asignado_op': 'Asignar Sector de Producción',
            'fecha_inicio_planificada': 'Fecha Inicio Planificada',
            'fecha_fin_planificada': 'Fecha Fin Planificada',
            'notas': 'Notas Adicionales de Producción',
        }

    def __init__(self, *args, **kwargs):
        # Pop el queryset personalizado antes de llamar a super()
        estado_op_queryset_personalizado = kwargs.pop('estado_op_queryset', None)
        super().__init__(*args, **kwargs)
        
        self.fields['sector_asignado_op'].queryset = SectorAsignado.objects.all().order_by('nombre')
        self.fields['sector_asignado_op'].empty_label = "Seleccionar Sector..."
        
        # Aplicar el queryset personalizado si se proporcionó
        if estado_op_queryset_personalizado is not None:
            self.fields['estado_op'].queryset = estado_op_queryset_personalizado
        else:
            # Fallback si no se pasa queryset (aunque la vista siempre debería pasarlo)
            self.fields['estado_op'].queryset = EstadoOrden.objects.all().order_by('nombre')
            logger.warning("OrdenProduccionUpdateForm recibió estado_op_queryset=None. Usando todos los estados.")
        
        self.fields['estado_op'].empty_label = None # No mostrar "---------"

        # Lógica para deshabilitar campos basada en el estado *inicial* de la instancia
        # cuando el formulario se carga por primera vez.
        instance = getattr(self, 'instance', None)
        campos_a_deshabilitar = []
        
        if instance and instance.pk and instance.estado_op:
            estado_actual_nombre_lower = instance.estado_op.nombre.lower()
            
            # Estados donde la planificación/asignación no tiene sentido o ya pasó
            estados_sin_planificacion_activa = [
                "pendiente", 
                "insumos solicitados", # Esperando a depósito
                "completada", 
                "cancelada"
            ]
            # El estado "Pausada" es un caso especial, podría permitir edición de notas
            # pero no necesariamente de fechas/sector si se espera reanudar tal cual.
            # Si desde "Pausada" se permite volver a "Pendiente", entonces sí se deshabilitarían.
            # Por ahora, si está Pausada, los campos de planificación no se deshabilitan explícitamente aquí,
            # la lógica de qué estados permite la vista al reanudar es más importante.

            if estado_actual_nombre_lower in estados_sin_planificacion_activa:
                campos_a_deshabilitar = ['sector_asignado_op', 'fecha_inicio_planificada', 'fecha_fin_planificada']
                # Notas podría seguir siendo editable en algunos de estos estados.
                if estado_actual_nombre_lower in ["completada", "cancelada"]:
                    self.fields['estado_op'].disabled = True # No se puede cambiar el estado si ya está finalizado/cancelado
                    self.fields['notas'].disabled = True # Tampoco las notas
            
            # Si está pausada, solo notas editables, el resto no.
            elif estado_actual_nombre_lower == "pausada":
                campos_a_deshabilitar = ['sector_asignado_op', 'fecha_inicio_planificada', 'fecha_fin_planificada']


        for field_name in campos_a_deshabilitar:
            if field_name in self.fields:
                self.fields[field_name].disabled = True
                self.fields[field_name].widget.attrs['placeholder'] = "No editable en este estado"
        
        # Definir campos como no requeridos si el modelo lo permite (blank=True)
        self.fields['fecha_inicio_planificada'].required = False
        self.fields['fecha_fin_planificada'].required = False
        self.fields['sector_asignado_op'].required = False 
        self.fields['notas'].required = False

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'telefono', 'email']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Nombre del Proveedor'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Persona de contacto'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Teléfono de contacto'}),
            'email': forms.EmailInput(attrs={'class': 'form-control mb-2', 'placeholder': 'correo@proveedor.com'}),
        }
# Formulario para crear Factura
class FacturaForm(forms.ModelForm): # Formulario básico para la factura
    class Meta:
        model = Factura
        fields = ['numero_factura'] # El total se podría calcular, la fecha es auto, la orden_venta se asigna en la vista
        widgets = {
            'numero_factura': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sugerir N° de Factura
        last_factura = Factura.objects.order_by('id').last()
        next_factura_number = f"FACT-{str(last_factura.id + 1).zfill(5)}" if last_factura else "FACT-00001"
        self.fields['numero_factura'].initial = next_factura_number

class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = Orden
        fields = [
            'numero_orden', 
            'proveedor', 
            'insumo_principal', 
            'cantidad_principal', 
            'precio_unitario_compra', 
            'fecha_estimada_entrega', 
            'numero_tracking', 
            'notas'
        ]
        widgets = {
            'numero_orden': forms.TextInput(attrs={'class': 'form-control mb-3'}),
            'proveedor': forms.Select(attrs={'class': 'form-select mb-3'}),
            'insumo_principal': forms.Select(attrs={'class': 'form-select mb-3'}),
            'cantidad_principal': forms.NumberInput(attrs={'class': 'form-control mb-3', 'min': '1', 'placeholder':'Cantidad a comprar'}),
            'precio_unitario_compra': forms.NumberInput(attrs={'class': 'form-control mb-3', 'step': '0.01', 'placeholder': '0.00 (de la oferta)'}),
            'fecha_estimada_entrega': forms.DateInput(
                attrs={'class': 'form-control mb-3', 'type': 'date'},
                format='%Y-%m-%d' 
            ),
            'numero_tracking': forms.TextInput(attrs={'class': 'form-control mb-3', 'placeholder': 'Opcional'}),
            'notas': forms.Textarea(attrs={'class': 'form-control mb-3', 'rows': 3, 'placeholder': 'Notas adicionales...'}),
        }
        labels = {
            'numero_orden': 'N° Orden de Compra',
            'proveedor': 'Proveedor Seleccionado',
            'insumo_principal': 'Insumo Principal Requerido',
            'cantidad_principal': 'Cantidad a Comprar',
            'precio_unitario_compra': 'Precio Unitario de Compra ($)',
            'fecha_estimada_entrega': 'Fecha Estimada de Entrega',
            'numero_tracking': 'Número de Seguimiento (Tracking)',
            'notas': 'Notas Adicionales',
        }

    def __init__(self, *args, **kwargs):
        # Extraer argumentos personalizados ANTES de llamar a super().__init__()
        # 'insumo_fijado' es el objeto Insumo que no debe cambiarse en el form.
        self.insumo_fijado_por_vista = kwargs.pop('insumo_fijado', None)
        # 'proveedor_fijado' es el objeto Proveedor si ya fue seleccionado y no debe cambiarse.
        self.proveedor_fijado_por_vista = kwargs.pop('proveedor_fijado', None) 
        
        super().__init__(*args, **kwargs) # Llamar al __init__ del padre DESPUÉS de extraer
        
        instance = getattr(self, 'instance', None)
        is_new_instance = not (instance and instance.pk)

        # Configuración Insumo Principal
        if self.insumo_fijado_por_vista:
            self.fields['insumo_principal'].queryset = Insumo.objects.filter(pk=self.insumo_fijado_por_vista.pk)
            self.fields['insumo_principal'].initial = self.insumo_fijado_por_vista
            self.fields['insumo_principal'].widget.attrs['disabled'] = True
            self.fields['insumo_principal'].empty_label = None
        else: # Si no está fijado (ej. creación manual de OC, o edición de borrador donde se permite cambiar)
            self.fields['insumo_principal'].queryset = Insumo.objects.all().order_by('descripcion')
            self.fields['insumo_principal'].empty_label = "Seleccionar Insumo..."
        
        # Configuración Proveedor
        if self.proveedor_fijado_por_vista:
            self.fields['proveedor'].queryset = Proveedor.objects.filter(pk=self.proveedor_fijado_por_vista.pk)
            self.fields['proveedor'].initial = self.proveedor_fijado_por_vista
            self.fields['proveedor'].widget.attrs['disabled'] = True
            self.fields['proveedor'].empty_label = None
        else: # Permitir seleccionar cualquier proveedor si no está fijado
            self.fields['proveedor'].queryset = Proveedor.objects.all().order_by('nombre')
            self.fields['proveedor'].empty_label = "Seleccionar Proveedor..."
        
        # Lógica de campos deshabilitados / iniciales para creación y edición
        if is_new_instance:
            if not self.initial.get('numero_orden'): # Solo si la vista no lo pasó ya en initial
                last_oc = Orden.objects.filter(tipo='compra').order_by('id').last()
                next_id = (last_oc.id + 1) if last_oc else 1
                next_oc_number = f"OC-{str(next_id).zfill(5)}"
                while Orden.objects.filter(numero_orden=next_oc_number).exists():
                    next_id += 1; next_oc_number = f"OC-{str(next_id).zfill(5)}"
                self.initial['numero_orden'] = next_oc_number # Usar self.initial para que el widget lo tome
            
            # Si el insumo y proveedor están fijados (vienen de la selección de oferta),
            # el precio y fecha de entrega también se consideran "fijados" por esa oferta.
            if self.insumo_fijado_por_vista and self.proveedor_fijado_por_vista:
                if self.initial.get('precio_unitario_compra') is not None:
                    self.fields['precio_unitario_compra'].widget.attrs['disabled'] = True
                if self.initial.get('fecha_estimada_entrega'):
                    self.fields['fecha_estimada_entrega'].widget.attrs['disabled'] = True
        else: # Editando una OC existente
            self.fields['numero_orden'].widget.attrs['readonly'] = True # N° OC no se edita una vez creada
            if instance.estado != 'BORRADOR': # Restricciones más fuertes si ya no es borrador
                # self.fields['proveedor'].widget.attrs['disabled'] = True # Ya manejado si proveedor_fijado_por_vista se pasa
                self.fields['insumo_principal'].widget.attrs['disabled'] = True # Insumo no cambia después de borrador
                self.fields['cantidad_principal'].widget.attrs['disabled'] = True
                self.fields['precio_unitario_compra'].widget.attrs['disabled'] = True
                # fecha_estimada_entrega podría ser editable si el proveedor actualiza
                # self.fields['fecha_estimada_entrega'].widget.attrs['disabled'] = True

        # Configuración de campos requeridos/opcionales
        self.fields['fecha_estimada_entrega'].required = False
        self.fields['numero_tracking'].required = False
        self.fields['notas'].required = False
        
        # Cantidad y Precio son requeridos si hay un insumo
        current_insumo_for_validation = cleaned_data.get('insumo_principal') if hasattr(self, 'cleaned_data') else self.initial.get('insumo_principal', getattr(instance, 'insumo_principal', None))
        if current_insumo_for_validation:
            self.fields['cantidad_principal'].required = True
            self.fields['precio_unitario_compra'].required = True
        else:
            self.fields['cantidad_principal'].required = False
            self.fields['precio_unitario_compra'].required = False

    def clean_numero_orden(self):
        numero_orden = self.cleaned_data.get('numero_orden')
        instance = getattr(self, 'instance', None)
        if instance and instance.pk and instance.numero_orden == numero_orden:
            return numero_orden
        if Orden.objects.filter(numero_orden=numero_orden).exists():
            raise forms.ValidationError("Una orden de compra con este número ya existe.")
        return numero_orden

    def clean(self):
        cleaned_data = super().clean()
        instance = getattr(self, 'instance', None)
        is_new_instance = not (instance and instance.pk)

        # Restaurar valores de campos deshabilitados para que estén en cleaned_data
        # Esto es crucial porque los campos 'disabled' no se envían en el POST.
        fields_potentially_disabled = [
            'insumo_principal', 'proveedor', 
            'precio_unitario_compra', 'fecha_estimada_entrega'
        ]
        # El campo 'numero_orden' si es readonly en edición
        if not is_new_instance and self.fields['numero_orden'].widget.attrs.get('readonly'):
             if 'numero_orden' not in cleaned_data and hasattr(instance, 'numero_orden'):
                 cleaned_data['numero_orden'] = instance.numero_orden


        for field_name in fields_potentially_disabled:
            if field_name in self.fields and self.fields[field_name].widget.attrs.get('disabled', False):
                # Si el campo está deshabilitado, su valor no vendrá en el POST.
                # Necesitamos tomarlo de 'initial' (si es creación) o 'instance' (si es edición).
                if field_name in self.initial: # Priorizar initial si existe (para creación con pre-relleno)
                    cleaned_data[field_name] = self.initial[field_name]
                elif instance and instance.pk and hasattr(instance, field_name): # Para edición
                    cleaned_data[field_name] = getattr(instance, field_name)
        
        # Re-validaciones que dependen de los valores (ahora completos en cleaned_data)
        insumo = cleaned_data.get("insumo_principal")
        cantidad = cleaned_data.get("cantidad_principal")
        precio = cleaned_data.get("precio_unitario_compra")

        if insumo: # Si hay un insumo (ya sea fijado o seleccionado)
            if not cantidad and self.fields['cantidad_principal'].required:
                self.add_error('cantidad_principal', 'La cantidad es requerida si se ha seleccionado un insumo.')
            if precio is None and self.fields['precio_unitario_compra'].required:
                self.add_error('precio_unitario_compra', 'El precio unitario es requerido si se ha seleccionado un insumo.')
        elif not insumo and (cantidad or precio is not None):
            # Si no hay insumo pero se ingresó cantidad o precio, es un error
            if not insumo:
                 self.add_error('insumo_principal', 'Debe seleccionar un insumo si ingresa cantidad o precio.')
            if cantidad:
                 self.add_error('cantidad_principal', 'No puede ingresar cantidad sin un insumo.')
            if precio is not None:
                 self.add_error('precio_unitario_compra', 'No puede ingresar precio sin un insumo.')
        return cleaned_data
    
class ReporteProduccionForm(forms.ModelForm):
    TIPO_PROBLEMA_CHOICES = [
        ('', 'Seleccionar tipo...'),
        ('Falta de Insumos', 'Falta de Insumos'),
        ('Falla de Maquinaria', 'Falla de Maquinaria'),
        ('Error de Calidad', 'Error de Calidad Detectado'),
        ('Problema de Personal', 'Problema de Personal'),
        ('Otro', 'Otro (especificar)'),
    ]
    tipo_problema = forms.ChoiceField(
        choices=TIPO_PROBLEMA_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select mb-3'}) # Añadido mb-3 para espaciado
    )
    sector_reporta = forms.ModelChoiceField(
        queryset=SectorAsignado.objects.all().order_by('nombre'), # Añadido order_by
        required=False,
        widget=forms.Select(attrs={'class': 'form-select mb-3'}),
        label="Sector que Reporta (Opcional)"
    )

    class Meta:
        model = Reportes
        # USA EL NOMBRE CORRECTO DEL CAMPO DEL MODELO AQUÍ:
        fields = ['tipo_problema', 'informe_reporte', 'sector_reporta'] # Cambiado 'descripcion_problema' a 'informe_reporte'
        widgets = {
            # Y AQUÍ TAMBIÉN:
            'informe_reporte': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Describa detalladamente el problema...'}),
        }
        labels = {
            'tipo_problema': 'Tipo de Problema Reportado',
            # Y AQUÍ:
            'informe_reporte': 'Descripción Detallada del Problema',
            # 'sector_reporta' ya está definido arriba
        }

    def __init__(self, *args, **kwargs):
        self.orden_produccion = kwargs.pop('orden_produccion', None)
        super().__init__(*args, **kwargs)
        
        if self.orden_produccion and self.orden_produccion.sector_asignado_op:
            self.fields['sector_reporta'].initial = self.orden_produccion.sector_asignado_op