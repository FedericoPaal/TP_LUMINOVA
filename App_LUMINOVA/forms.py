from email.headerregistry import Group
from django import forms
from django.contrib.auth.models import Group, Permission


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