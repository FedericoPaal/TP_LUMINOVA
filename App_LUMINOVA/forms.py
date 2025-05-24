from django import forms
from django.contrib.auth.models import  Group, Permission
from .models import (
    Cliente, 
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
        # Usando los nombres de modelo correctos de tu models.py
        self.fields['estado_op'].queryset = EstadoOrden.objects.all().order_by('nombre') # Tu modelo se llama EstadoOrden
        self.fields['estado_op'].empty_label = "Seleccionar Estado..."
        self.fields['sector_asignado_op'].queryset = SectorAsignado.objects.all().order_by('nombre') # Tu modelo se llama SectorAsignado
        self.fields['sector_asignado_op'].empty_label = "Seleccionar Sector..."
        # Hacer opcionales los campos que pueden serlo
        self.fields['fecha_inicio_planificada'].required = False
        self.fields['fecha_fin_planificada'].required = False
        self.fields['sector_asignado_op'].required = False
        self.fields['notas'].required = False

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'telefono', 'email'] # O los campos que quieras en el form
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Nombre del Proveedor'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Persona de contacto'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Teléfono de contacto'}),
            'email': forms.EmailInput(attrs={'class': 'form-control mb-2', 'placeholder': 'correo@proveedor.com'}),
        }

