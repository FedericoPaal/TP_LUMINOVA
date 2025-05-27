from django import forms
from django.contrib.auth.models import  Group, Permission
from .models import (
    Cliente,
    Factura,
    Orden, 
    Proveedor, # Asegúrate de importar el modelo Proveedor
    OrdenVenta, ItemOrdenVenta, ProductoTerminado,
    OrdenProduccion, EstadoOrden, SectorAsignado, CategoriaInsumo, Insumo, CategoriaProductoTerminado
)


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado_op'].queryset = EstadoOrden.objects.all().order_by('nombre')
        self.fields['estado_op'].empty_label = "Seleccionar Estado..."
        self.fields['sector_asignado_op'].queryset = SectorAsignado.objects.all().order_by('nombre')
        self.fields['sector_asignado_op'].empty_label = "Seleccionar Sector..."
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
        super().__init__(*args, **kwargs)
        
        # Poblar QuerySets y empty_labels
        self.fields['proveedor'].queryset = Proveedor.objects.all().order_by('nombre')
        self.fields['proveedor'].empty_label = "Seleccionar Proveedor..."
        
        self.fields['insumo_principal'].queryset = Insumo.objects.all().order_by('descripcion')
        self.fields['insumo_principal'].empty_label = "Seleccionar Insumo..."

        # Campos opcionales (no requeridos por defecto si blank=True en el modelo)
        self.fields['fecha_estimada_entrega'].required = False
        self.fields['numero_tracking'].required = False
        self.fields['notas'].required = False
        self.fields['precio_unitario_compra'].required = False # Puede ser que el precio se defina después
        self.fields['cantidad_principal'].required = False # Puede ser que la cantidad se defina después

        # Sugerir N° de OC si es una instancia nueva (no se está editando)
        if not self.instance.pk: 
            last_oc = Orden.objects.filter(tipo='compra').order_by('id').last()
            # Genera un número simple basado en el último ID. Puedes hacerlo más robusto.
            next_id = (last_oc.id + 1) if last_oc else 1
            next_oc_number = f"OC-{str(next_id).zfill(5)}" 
            # Asegurarse de que el número no exista ya (en caso de borrados o IDs no secuenciales)
            while Orden.objects.filter(numero_orden=next_oc_number).exists():
                next_id += 1
                next_oc_number = f"OC-{str(next_id).zfill(5)}"
            self.fields['numero_orden'].initial = next_oc_number
        
        # Si se está editando o si hay un insumo preseleccionado, y no hay precio,
        # intenta obtener el precio del insumo.
        if self.instance and self.instance.insumo_principal and not self.initial.get('precio_unitario_compra'):
            self.initial['precio_unitario_compra'] = self.instance.insumo_principal.precio_unitario
        elif 'insumo_principal' in self.initial and self.initial['insumo_principal'] and not self.initial.get('precio_unitario_compra'):
             insumo_obj = Insumo.objects.get(pk=self.initial['insumo_principal'].pk) # o self.initial['insumo_principal'] si es ID
             self.initial['precio_unitario_compra'] = insumo_obj.precio_unitario


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