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
        fields = ['numero_ov', 'cliente', 'estado', 'notas'] # total_ov se calcula
        widgets = {
            'numero_ov': forms.TextInput(attrs={'class': 'form-control'}),
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = Cliente.objects.all().order_by('nombre')
        self.fields['cliente'].empty_label = "Seleccione un Cliente"
        self.fields['estado'].choices = OrdenVenta.ESTADO_CHOICES
        self.fields['estado'].initial = 'PENDIENTE'

# Formulario para actualizar una OP (usado en la vista de detalle de OP)
class OrdenProduccionUpdateForm(forms.ModelForm):
    class Meta:
        model = OrdenProduccion
        fields = ['estado_op', 'sector_asignado_op', 'fecha_inicio_planificada', 'fecha_fin_planificada', 'notas']
        widgets = {
            'estado_op': forms.Select(attrs={'class': 'form-select'}),
            'sector_asignado_op': forms.Select(attrs={'class': 'form-select'}),
            'fecha_inicio_planificada': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin_planificada': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'estado_op': 'Cambiar Estado de OP',
            'sector_asignado_op': 'Asignar Sector de Producción',
            # ... (otras etiquetas)
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['sector_asignado_op'].queryset = SectorAsignado.objects.all().order_by('nombre')
        self.fields['sector_asignado_op'].empty_label = "Seleccionar Sector..."
        
        instance = getattr(self, 'instance', None)
        
        # Definición de nombres de estado (minúsculas para comparación)
        ESTADO_PENDIENTE = "pendiente"
        ESTADO_INSUMOS_SOLICITADOS = "insumos solicitados"
        ESTADO_INSUMOS_RECIBIDOS = "insumos recibidos"
        ESTADO_PRODUCCION_INICIADA = "producción iniciada"
        ESTADO_EN_PROCESO = "en proceso"
        ESTADO_PRODUCCION_PARCIAL = "producción parcial"
        ESTADO_PAUSADA = "pausada"
        ESTADO_COMPLETADA = "completada"
        ESTADO_CANCELADA = "cancelada"

        nombres_estados_permitidos_dropdown = [] # Estados que aparecerán en el dropdown
        campos_a_deshabilitar = []
        
        if instance and instance.pk and instance.estado_op:
            estado_actual_nombre_lower = instance.estado_op.nombre.lower()
            estado_actual_nombre_original = instance.estado_op.nombre

            if estado_actual_nombre_lower == ESTADO_PENDIENTE:
                nombres_estados_permitidos_dropdown = [estado_actual_nombre_original, 'Pausada', 'Cancelada']
                # Deshabilitar otros campos de planificación
                campos_a_deshabilitar = ['sector_asignado_op', 'fecha_inicio_planificada', 'fecha_fin_planificada', 'notas']
            
            elif estado_actual_nombre_lower == ESTADO_INSUMOS_SOLICITADOS:
                nombres_estados_permitidos_dropdown = [estado_actual_nombre_original, 'Pausada', 'Cancelada']
                campos_a_deshabilitar = ['sector_asignado_op', 'fecha_inicio_planificada', 'fecha_fin_planificada', 'notas']

            elif estado_actual_nombre_lower == ESTADO_INSUMOS_RECIBIDOS:
                # ¡AHORA SE HABILITAN LOS CAMPOS!
                nombres_estados_permitidos_dropdown = [estado_actual_nombre_original, 'Producción Iniciada', 'Pausada', 'Cancelada']
                # No hay campos a deshabilitar, o solo notas si prefieres
            
            elif estado_actual_nombre_lower == ESTADO_PRODUCCION_INICIADA:
                 nombres_estados_permitidos_dropdown = [estado_actual_nombre_original, 'En Proceso', 'Producción Parcial', 'Pausada', 'Completada', 'Cancelada']
            
            elif estado_actual_nombre_lower == ESTADO_PRODUCCION_PARCIAL:
                 nombres_estados_permitidos_dropdown = [estado_actual_nombre_original, 'En Proceso', 'Pausada', 'Completada', 'Cancelada']

            elif estado_actual_nombre_lower == ESTADO_EN_PROCESO:
                 nombres_estados_permitidos_dropdown = [estado_actual_nombre_original, 'Producción Parcial', 'Pausada', 'Completada', 'Cancelada']
            
            elif estado_actual_nombre_lower == ESTADO_PAUSADA:
                nombres_estados_permitidos_dropdown = [estado_actual_nombre_original, 'Pendiente', 'Cancelada']
                # Al volver a Pendiente, los campos de planificación deberían volver a deshabilitarse
                # hasta que pase a Insumos Recibidos de nuevo.
                # Si reanuda a un estado productivo, se habilitan.
                # Por ahora, si vuelve a pendiente, se deshabilitarán en la próxima carga del form.
                # Podrías añadir lógica aquí para deshabilitar si el estado seleccionado es Pendiente.
            
            elif estado_actual_nombre_lower in [ESTADO_COMPLETADA, ESTADO_CANCELADA]:
                nombres_estados_permitidos_dropdown = [estado_actual_nombre_original]
                campos_a_deshabilitar = ['sector_asignado_op', 'fecha_inicio_planificada', 'fecha_fin_planificada', 'notas'] # Todo deshabilitado

            else: 
                logger.warning(f"Estado OP '{instance.estado_op.nombre}' no tiene transiciones/habilitaciones definidas en Form. Mostrando todos.")
                self.fields['estado_op'].queryset = EstadoOrden.objects.all().order_by('nombre')

            if nombres_estados_permitidos_dropdown:
                q_objects = Q()
                for nombre_estado in nombres_estados_permitidos_dropdown:
                    q_objects |= Q(nombre__iexact=nombre_estado)
                self.fields['estado_op'].queryset = EstadoOrden.objects.filter(q_objects).order_by('nombre')
            elif not self.fields['estado_op'].queryset and instance and instance.estado_op:
                 self.fields['estado_op'].queryset = EstadoOrden.objects.filter(id=instance.estado_op.id)
        else:
            self.fields['estado_op'].queryset = EstadoOrden.objects.all().order_by('nombre')
            
        self.fields['estado_op'].empty_label = None 

        # Deshabilitar campos según la lógica
        for field_name in campos_a_deshabilitar:
            if field_name in self.fields:
                self.fields[field_name].disabled = True
                # Opcionalmente, añadir un placeholder o cambiar el widget si está deshabilitado
                # self.fields[field_name].widget.attrs['placeholder'] = "No editable en este estado"
                # self.fields[field_name].widget.attrs['readonly'] = True # Alternativa a disabled

        # Campos opcionales (su 'required' es False si blank=True en el modelo)
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
            'proveedor', # Este es el proveedor al que se le hace la OC
            'insumo_principal', # El insumo principal de la OC
            'cantidad_principal', 
            'precio_unitario_compra', # Precio ACORDADO para esta OC para este insumo con este proveedor
            'fecha_estimada_entrega',
            'numero_tracking', 
            'notas',
        ]
        # 'tipo' y 'estado' se manejarán en la vista o tendrán defaults en el modelo.
        # 'total_orden_compra' se calcula automáticamente en el save() del modelo si los campos necesarios están.
        
        widgets = {
            'numero_orden': forms.TextInput(attrs={'class': 'form-control mb-2'}),
            'proveedor': forms.Select(attrs={'class': 'form-select mb-2'}),
            'insumo_principal': forms.Select(attrs={'class': 'form-select mb-2'}),
            'cantidad_principal': forms.NumberInput(attrs={'class': 'form-control mb-2', 'min': '1'}),
            'precio_unitario_compra': forms.NumberInput(attrs={'class': 'form-control mb-2', 'step': '0.01', 'placeholder': '0.00'}),
            'fecha_estimada_entrega': forms.DateInput(attrs={'class': 'form-control mb-2', 'type': 'date'}),
            'numero_tracking': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Opcional'}),
            'notas': forms.Textarea(attrs={'class': 'form-control mb-2', 'rows': 3, 'placeholder': 'Notas adicionales...'}),
        }
        labels = {
            'numero_orden': 'N° Orden de Compra',
            'proveedor': 'Proveedor Asociado',
            'insumo_principal': 'Insumo Principal a Comprar',
            'cantidad_principal': 'Cantidad del Insumo Principal',
            'precio_unitario_compra': 'Precio Unitario de Compra ($)',
            'fecha_estimada_entrega': 'Fecha Estimada de Entrega',
            'numero_tracking': 'Número de Seguimiento (Tracking)',
            'notas': 'Notas Adicionales',
        }

    def __init__(self, *args, **kwargs):
        self.insumo_para_ofertas = kwargs.pop('insumo_para_ofertas', None) # Nuevo: para pasar el insumo objetivo
        super().__init__(*args, **kwargs)
        
        self.fields['insumo_principal'].queryset = Insumo.objects.all().order_by('descripcion')
        self.fields['insumo_principal'].empty_label = "Seleccionar Insumo..."

        # El queryset de proveedores ahora podría filtrarse si un insumo está preseleccionado
        # y si queremos mostrar solo proveedores que *ofrecen* ese insumo.
        if self.insumo_para_ofertas:
            # Obtener IDs de proveedores que tienen una oferta para self.insumo_para_ofertas
            proveedor_ids_con_oferta = OfertaProveedor.objects.filter(insumo=self.insumo_para_ofertas).values_list('proveedor_id', flat=True)
            self.fields['proveedor'].queryset = Proveedor.objects.filter(id__in=proveedor_ids_con_oferta).order_by('nombre')
            if not self.fields['proveedor'].queryset.exists(): # Fallback si no hay ofertas registradas
                 self.fields['proveedor'].queryset = Proveedor.objects.all().order_by('nombre')
        else:
            self.fields['proveedor'].queryset = Proveedor.objects.all().order_by('nombre')
        self.fields['proveedor'].empty_label = "Seleccionar Proveedor..."
        
        # ... (lógica de campos opcionales y número de OC inicial) ...
        if not self.instance.pk:
            # ... (sugerencia de numero_orden)
            last_oc = Orden.objects.filter(tipo='compra').order_by('id').last()
            next_id = (last_oc.id + 1) if last_oc else 1
            next_oc_number = f"OC-{str(next_id).zfill(5)}" 
            while Orden.objects.filter(numero_orden=next_oc_number).exists():
                next_id += 1
                next_oc_number = f"OC-{str(next_id).zfill(5)}"
            self.fields['numero_orden'].initial = next_oc_number

        # Si hay un insumo y proveedor preseleccionados (ej. desde la vista de selección),
        # intentar obtener el precio de la oferta.
        insumo_inicial = self.initial.get('insumo_principal')
        proveedor_inicial = self.initial.get('proveedor')

        if insumo_inicial and proveedor_inicial and not self.initial.get('precio_unitario_compra'):
            try:
                # Asegurarse de que insumo_inicial y proveedor_inicial sean objetos o IDs
                insumo_obj = insumo_inicial if isinstance(insumo_inicial, Insumo) else Insumo.objects.get(pk=insumo_inicial)
                proveedor_obj = proveedor_inicial if isinstance(proveedor_inicial, Proveedor) else Proveedor.objects.get(pk=proveedor_inicial)
                
                oferta = OfertaProveedor.objects.filter(insumo=insumo_obj, proveedor=proveedor_obj).first()
                if oferta:
                    self.initial['precio_unitario_compra'] = oferta.precio_unitario_compra
                    # También podrías pre-rellenar fecha_estimada_entrega si está en OfertaProveedor
                    # self.initial['fecha_estimada_entrega'] = ...
            except (Insumo.DoesNotExist, Proveedor.DoesNotExist, TypeError):
                pass # No hacer nada si los objetos no se pueden obtener


    def clean_numero_orden(self):
        numero_orden = self.cleaned_data.get('numero_orden')
        # Si estamos editando una instancia existente, no verificamos la unicidad contra sí misma
        if self.instance and self.instance.pk and self.instance.numero_orden == numero_orden:
            return numero_orden
        # Si es una nueva instancia o el número_orden ha cambiado, verificar unicidad
        if Orden.objects.filter(numero_orden=numero_orden).exists():
            raise forms.ValidationError("Una orden de compra con este número ya existe.")
        return numero_orden

    def clean(self):
        cleaned_data = super().clean()
        insumo = cleaned_data.get("insumo_principal")
        cantidad = cleaned_data.get("cantidad_principal")
        precio = cleaned_data.get("precio_unitario_compra")

        # Si se proporciona un insumo, la cantidad y el precio deberían ser requeridos
        # para calcular el total, a menos que permitas OCs sin estos detalles inicialmente.
        # Por ahora, lo haremos opcional, el cálculo del total en el modelo lo manejará.
        # Si quieres que sean requeridos si hay un insumo:
        # if insumo:
        #     if not cantidad:
        #         self.add_error('cantidad_principal', 'La cantidad es requerida si se selecciona un insumo.')
        #     if not precio:
        #         self.add_error('precio_unitario_compra', 'El precio unitario es requerido si se selecciona un insumo.')
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