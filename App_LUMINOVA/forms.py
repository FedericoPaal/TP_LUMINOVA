import logging
from datetime import timedelta, timezone

from django import apps, forms
from django.contrib.auth.models import Group, Permission
from django.db.models import Q

from .models import (
    CategoriaInsumo,
    CategoriaProductoTerminado,
    Cliente,
    EstadoOrden,
    Factura,
    Insumo,
    ItemOrdenVenta,
    OfertaProveedor,
    Orden,
    OrdenProduccion,
    OrdenVenta,
    ProductoTerminado,
    Proveedor,
    Reportes,
    SectorAsignado,
)

logger = logging.getLogger(__name__)


class RolForm(forms.Form):
    nombre = forms.CharField(
        label="Nombre del Rol",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    descripcion = forms.CharField(
        label="Descripción",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        required=False,
    )
    rol_id = forms.IntegerField(
        widget=forms.HiddenInput(), required=False
    )  # Para edición

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre")
        rol_id = self.cleaned_data.get("rol_id")
        query = Group.objects.filter(name__iexact=nombre)
        if (
            rol_id
        ):  # Si es edición, excluir el rol actual de la verificación de unicidad
            query = query.exclude(pk=rol_id)
        if query.exists():
            raise forms.ValidationError("Un rol con este nombre ya existe.")
        return nombre


class PermisosRolForm(forms.Form):
    rol_id = forms.IntegerField(widget=forms.HiddenInput())
    permisos_ids = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,  # No se usará directamente en el HTML, pero define el tipo
        required=False,
    )


# TP_LUMINOVA-main/App_LUMINOVA/forms.py

from django import forms

from .models import (  # EstadoOrden y SectorAsignado son los que tenías para OP
    CategoriaInsumo,
    CategoriaProductoTerminado,
    Cliente,
    EstadoOrden,
    Insumo,
    ItemOrdenVenta,
    OrdenProduccion,
    OrdenVenta,
    ProductoTerminado,
    Proveedor,
    SectorAsignado,
)


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "direccion", "telefono", "email"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Nombre completo del cliente",
                }
            ),
            "direccion": forms.Textarea(
                attrs={
                    "class": "form-control mb-2",
                    "rows": 2,
                    "placeholder": "Dirección completa",
                }
            ),  # Menos filas
            "telefono": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Número de teléfono",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "correo@ejemplo.com",
                }
            ),
        }


class ItemOrdenVentaForm(forms.ModelForm):
    class Meta:
        model = ItemOrdenVenta
        fields = ["producto_terminado", "cantidad", "precio_unitario_venta"]
        widgets = {
            "producto_terminado": forms.Select(
                attrs={"class": "form-select form-select-sm producto-selector-ov-item"}
            ),
            "cantidad": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-sm cantidad-ov-item",
                    "min": "1",
                    "value": "1",
                }
            ),
            "precio_unitario_venta": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-sm precio-ov-item",
                    "step": "0.01",
                    "readonly": True,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto_terminado"].queryset = (
            ProductoTerminado.objects.all().order_by("descripcion")
        )
        self.fields["producto_terminado"].empty_label = "Seleccionar Producto..."
        # Mostrar precio y stock en el dropdown del producto para ayudar al usuario
        self.fields["producto_terminado"].label_from_instance = (
            lambda obj: f"{obj.descripcion} (Stock: {obj.stock} | P.U: ${obj.precio_unitario})"
        )
        # El precio unitario se llenará con JS al seleccionar el producto.


# FormSet para los ítems de la Orden de Venta
ItemOrdenVentaFormSet = forms.inlineformset_factory(
    OrdenVenta,
    ItemOrdenVenta,
    form=ItemOrdenVentaForm,
    fields=["producto_terminado", "cantidad", "precio_unitario_venta"],
    extra=0,  # Empieza con 1 form para ítem
    can_delete=True,  # Permite marcar para eliminar ítems existentes
    can_delete_extra=True,  # Permite eliminar forms "extra" añadidos por JS antes de guardar
)

# FormSet para la vista de CREACIÓN (con 1 formulario extra por defecto)
ItemOrdenVentaFormSetCreacion = forms.inlineformset_factory(
    OrdenVenta,
    ItemOrdenVenta,
    form=ItemOrdenVentaForm,
    fields=["producto_terminado", "cantidad", "precio_unitario_venta"],
    extra=1,
    can_delete=True,
    can_delete_extra=True,
)


class OrdenVentaForm(forms.ModelForm):
    class Meta:
        model = OrdenVenta
        fields = ["numero_ov", "cliente", "estado", "notas"]
        widgets = {
            "numero_ov": forms.TextInput(attrs={"class": "form-control"}),
            "cliente": forms.Select(attrs={"class": "form-select"}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "notas": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Anotaciones adicionales...",
                }
            ),
        }
        labels = {
            "numero_ov": "Nº Orden de Venta",
            "cliente": "Cliente Asociado",
            "estado": "Estado Actual de la Orden",
            "notas": "Notas Adicionales",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["cliente"].queryset = Cliente.objects.all().order_by("nombre")
        self.fields["cliente"].empty_label = "Seleccione un Cliente..."

        instance = getattr(self, "instance", None)
        is_new_instance = instance is None or not instance.pk

        if is_new_instance:
            # CREACIÓN DE NUEVA OV
            self.initial["estado"] = "PENDIENTE"
            self.fields["estado"].widget.attrs["disabled"] = True
            self.fields["estado"].required = False  # No se envía, la vista lo asigna

            # El numero_ov se sugiere en la vista ventas_crear_ov_view y se pasa como initial.
            # Podríamos hacerlo readonly aquí también si siempre viene de initial.
            if self.initial.get("numero_ov"):
                self.fields["numero_ov"].widget.attrs["readonly"] = True

        else:  # EDICIÓN DE OV EXISTENTE
            # Hacer numero_ov siempre readonly después de la creación
            self.fields["numero_ov"].widget.attrs["readonly"] = True

            # Hacer estado siempre disabled (o readonly si prefieres que el valor se envíe)
            # Si está disabled, el valor no se envía en el POST, la vista no debe intentar guardarlo desde el form.
            self.fields["estado"].widget.attrs["disabled"] = True
            self.fields["estado"].required = (
                False  # No es requerido del POST si está disabled
            )

            # Si lo pones readonly, el valor SÍ se envía, pero el widget Select no tiene un buen estado readonly nativo.
            # 'disabled' es visualmente más claro para un Select que no se debe cambiar.
            # La vista 'ventas_editar_ov_view' DEBE OMITIR la actualización del campo 'estado' desde el formulario
            # si se decide que el estado solo cambia por acciones específicas.

        # Opcional: quitar el "---------" si siempre quieres un estado seleccionado y el campo está habilitado
        if not self.fields["estado"].widget.attrs.get("disabled"):
            self.fields["estado"].empty_label = None


# Formulario para actualizar una OP (usado en la vista de detalle de OP)
class OrdenProduccionUpdateForm(forms.ModelForm):
    class Meta:
        model = OrdenProduccion
        fields = [
            "estado_op",
            "sector_asignado_op",
            "fecha_inicio_planificada",
            "fecha_fin_planificada",
            "notas",
        ]
        widgets = {
            "estado_op": forms.Select(attrs={"class": "form-select"}),
            "sector_asignado_op": forms.Select(attrs={"class": "form-select"}),
            "fecha_inicio_planificada": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "fecha_fin_planificada": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "notas": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Notas adicionales de producción...",
                }
            ),
        }
        labels = {
            "estado_op": "Cambiar Estado de OP",
            "sector_asignado_op": "Asignar Sector de Producción",
            "fecha_inicio_planificada": "Fecha Inicio Planificada",
            "fecha_fin_planificada": "Fecha Fin Planificada",
            "notas": "Notas Adicionales de Producción",
        }

    def __init__(self, *args, **kwargs):
        # El queryset para los estados se puede pasar opcionalmente desde la vista
        estado_op_queryset_personalizado = kwargs.pop("estado_op_queryset", None)
        super().__init__(*args, **kwargs)

        instance = getattr(self, "instance", None)

        # --- LÓGICA DE VISUALIZACIÓN (CORRECCIÓN DEFINITIVA) ---
        if instance:
            # Para los campos de fecha, forzamos el valor en el formato que el widget HTML espera.
            if instance.fecha_inicio_planificada:
                self.fields["fecha_inicio_planificada"].widget.attrs["value"] = (
                    instance.fecha_inicio_planificada.strftime("%Y-%m-%d")
                )
            if instance.fecha_fin_planificada:
                self.fields["fecha_fin_planificada"].widget.attrs["value"] = (
                    instance.fecha_fin_planificada.strftime("%Y-%m-%d")
                )

            # Para los campos ForeignKey (Select), establecemos el valor inicial del formulario.
            # Esto es más robusto que depender de la renderización automática.
            if instance.estado_op:
                self.initial["estado_op"] = instance.estado_op.pk
            if instance.sector_asignado_op:
                self.initial["sector_asignado_op"] = instance.sector_asignado_op.pk
        # --- FIN DE LA CORRECCIÓN ---

        self.fields["sector_asignado_op"].queryset = (
            SectorAsignado.objects.all().order_by("nombre")
        )
        self.fields["sector_asignado_op"].empty_label = "Seleccionar Sector..."

        if estado_op_queryset_personalizado is not None:
            self.fields["estado_op"].queryset = estado_op_queryset_personalizado
        else:
            self.fields["estado_op"].queryset = EstadoOrden.objects.all().order_by(
                "nombre"
            )

        self.fields["estado_op"].empty_label = None

        # --- LÓGICA PARA DESHABILITAR CAMPOS ---
        campos_a_deshabilitar = []
        if instance and instance.pk and instance.estado_op:
            estado_actual_nombre_lower = instance.estado_op.nombre.lower()

            estados_sin_planificacion_activa = [
                "insumos solicitados",
                "insumos recibidos",
                "producción iniciada",
                "en proceso",
                "completada",
                "cancelada",
                "pausada",
            ]

            if estado_actual_nombre_lower in estados_sin_planificacion_activa:
                campos_a_deshabilitar = [
                    "sector_asignado_op",
                    "fecha_inicio_planificada",
                    "fecha_fin_planificada",
                ]

                if estado_actual_nombre_lower in ["completada", "cancelada"]:
                    self.fields["estado_op"].disabled = True
                    self.fields["notas"].disabled = True

        for field_name in campos_a_deshabilitar:
            if field_name in self.fields:
                self.fields[field_name].disabled = True

        # Definir campos como no requeridos
        self.fields["fecha_inicio_planificada"].required = False
        self.fields["fecha_fin_planificada"].required = False
        self.fields["sector_asignado_op"].required = False
        self.fields["notas"].required = False


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre", "contacto", "telefono", "email"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Nombre del Proveedor",
                }
            ),
            "contacto": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Persona de contacto",
                }
            ),
            "telefono": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Teléfono de contacto",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "correo@proveedor.com",
                }
            ),
        }


# Formulario para crear Factura
class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = ["numero_factura"]
        widgets = {
            "numero_factura": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sugerir N° de Factura
        last_factura = Factura.objects.order_by("id").last()
        next_factura_number = (
            f"FACT-{str(last_factura.id + 1).zfill(5)}"
            if last_factura
            else "FACT-00001"
        )
        self.fields["numero_factura"].initial = next_factura_number

        # Hacer que el campo sea de solo lectura para el usuario
        self.fields["numero_factura"].widget.attrs["readonly"] = True
        self.fields["numero_factura"].widget.attrs[
            "class"
        ] = "form-control-plaintext text-muted"


class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = Orden
        fields = [
            "numero_orden",
            "insumo_principal",
            "proveedor",
            "cantidad_principal",
            "precio_unitario_compra",
            "fecha_estimada_entrega",
            "numero_tracking",
            "notas",
        ]
        widgets = {
            "numero_orden": forms.TextInput(
                attrs={"class": "form-control mb-3"}
            ),  # Se hará readonly en __init__
            "proveedor": forms.Select(attrs={"class": "form-select mb-3"}),
            "insumo_principal": forms.Select(attrs={"class": "form-select mb-3"}),
            "cantidad_principal": forms.NumberInput(
                attrs={"class": "form-control mb-3", "min": "1"}
            ),
            "precio_unitario_compra": forms.NumberInput(
                attrs={"class": "form-control mb-3", "step": "0.01"}
            ),  # Se hará readonly
            "fecha_estimada_entrega": forms.DateInput(
                attrs={"class": "form-control mb-3", "type": "date"}
            ),  # Se hará readonly
            "numero_tracking": forms.TextInput(
                attrs={
                    "class": "form-control mb-3",
                    "placeholder": "Gestionado por LUMINOVA",
                }
            ),  # Placeholder actualizado
            "notas": forms.Textarea(
                attrs={
                    "class": "form-control mb-3",
                    "rows": 3,
                    "placeholder": "Notas adicionales...",
                }
            ),
        }
        labels = {
            "numero_orden": "N° Orden de Compra",
            "proveedor": "Proveedor Seleccionado",
            "insumo_principal": "Insumo Principal Requerido",
            "cantidad_principal": "Cantidad a Comprar",
            "precio_unitario_compra": "Precio Unitario de Compra ($)",
            "fecha_estimada_entrega": "Fecha Estimada de Entrega",
            "numero_tracking": "Número de Seguimiento (Tracking)",
            "notas": "Notas Adicionales",
        }

    insumo_principal = forms.ModelChoiceField(
        queryset=Insumo.objects.all(), required=False, label="Insumo principal"
    )

    def __init__(self, *args, **kwargs):
        self.insumo_fijo = kwargs.pop("insumo_fijado", None)
        super().__init__(*args, **kwargs)

        instance = getattr(self, "instance", None)
        is_new_instance = not (instance and instance.pk)

        # --- Configuración de N° Orden ---
        self.fields["numero_orden"].widget.attrs["readonly"] = True
        self.fields["numero_orden"].widget.attrs[
            "class"
        ] = "form-control-plaintext mb-3 text-muted"
        if is_new_instance and not self.initial.get("numero_orden"):
            last_oc = Orden.objects.filter(tipo="compra").order_by("id").last()
            next_id = (last_oc.id + 1) if last_oc else 1
            next_oc_number = f"OC-{str(next_id).zfill(5)}"
            while Orden.objects.filter(numero_orden=next_oc_number).exists():
                next_id += 1
                next_oc_number = f"OC-{str(next_id).zfill(5)}"
            self.initial["numero_orden"] = next_oc_number

        # --- Configuración de Insumo Principal ---
        if self.insumo_fijo:
            self.fields["insumo_principal"].queryset = Insumo.objects.filter(
                pk=self.insumo_fijo.pk
            )
            self.fields["insumo_principal"].initial = self.insumo_fijo
            self.fields["insumo_principal"].widget.attrs["disabled"] = True
            self.fields["insumo_principal"].empty_label = None
        elif instance and instance.insumo_principal and instance.estado != "BORRADOR":
            self.fields["insumo_principal"].queryset = Insumo.objects.filter(
                pk=instance.insumo_principal.pk
            )
            self.fields["insumo_principal"].initial = instance.insumo_principal
            self.fields["insumo_principal"].widget.attrs["disabled"] = True
            self.fields["insumo_principal"].empty_label = None
        else:
            self.fields["insumo_principal"].queryset = Insumo.objects.all().order_by(
                "descripcion"
            )
            self.fields["insumo_principal"].empty_label = "Seleccionar Insumo..."

        # --- Configuración de Proveedor ---
        self.fields["proveedor"].queryset = Proveedor.objects.none()

        insumo_for_filter = None
        # 1. Caso POST: El insumo viene en `self.data`
        if "insumo_principal" in self.data:
            try:
                insumo_pk = int(self.data.get("insumo_principal"))
                insumo_for_filter = Insumo.objects.get(pk=insumo_pk)
            except (Insumo.DoesNotExist, ValueError, TypeError):
                pass
        # 2. Caso GET para editar: El insumo está en la instancia
        elif instance and instance.insumo_principal:
            insumo_for_filter = instance.insumo_principal
        # 3. Caso GET para crear con datos iniciales: El insumo viene en `self.initial`
        elif self.initial.get("insumo_principal"):
            # self.initial puede contener el ID o el objeto, nos aseguramos de tener el objeto
            initial_insumo = self.initial.get("insumo_principal")
            if isinstance(initial_insumo, Insumo):
                insumo_for_filter = initial_insumo
            else:
                try:
                    insumo_for_filter = Insumo.objects.get(pk=int(initial_insumo))
                except (Insumo.DoesNotExist, ValueError, TypeError):
                    pass

        # Si determinamos un insumo, filtramos los proveedores
        if insumo_for_filter:
            proveedor_ids = (
                OfertaProveedor.objects.filter(insumo=insumo_for_filter)
                .values_list("proveedor_id", flat=True)
                .distinct()
            )
            self.fields["proveedor"].queryset = Proveedor.objects.filter(
                id__in=proveedor_ids
            ).order_by("nombre")

        # --- Configuración de Precio y Fecha ---
        self.fields["precio_unitario_compra"].widget.attrs["readonly"] = True
        self.fields["precio_unitario_compra"].widget.attrs[
            "class"
        ] = "form-control-plaintext mb-3 text-muted"
        self.fields["fecha_estimada_entrega"].widget.attrs["readonly"] = True
        self.fields["fecha_estimada_entrega"].widget.attrs[
            "class"
        ] = "form-control-plaintext mb-3 text-muted"

        self.fields["numero_tracking"].widget.attrs["readonly"] = True
        self.fields["numero_tracking"].widget.attrs[
            "class"
        ] = "form-control-plaintext mb-3 text-muted"
        # self.fields['numero_tracking'].help_text = "gestionado por LUMINOVA."

        # --- Campos Requeridos ---
        self.fields["fecha_estimada_entrega"].required = False
        self.fields["numero_tracking"].required = False
        self.fields["notas"].required = False
        self.fields["cantidad_principal"].required = True
        self.fields["precio_unitario_compra"].required = True

    def clean_numero_orden(self):
        numero_orden = self.cleaned_data.get("numero_orden")
        instance = getattr(self, "instance", None)
        if instance and instance.pk and instance.numero_orden == numero_orden:
            return numero_orden
        if Orden.objects.filter(numero_orden=numero_orden).exists():
            raise forms.ValidationError(
                "Una orden de compra con este número ya existe."
            )
        return numero_orden

    def clean(self):
        cleaned_data = super().clean()
        instance = getattr(self, "instance", None)
        fields_to_restore = {
            "numero_orden": "readonly",
            "insumo_principal": "disabled",
            "proveedor": "disabled",
            "precio_unitario_compra": "readonly",
            "fecha_estimada_entrega": "readonly",
        }
        if instance and instance.pk and instance.estado != "BORRADOR":
            fields_to_restore["cantidad_principal"] = "readonly"
        for field_name, attr_type in fields_to_restore.items():
            if field_name in self.fields:
                is_locked = self.fields[field_name].widget.attrs.get(attr_type, False)
                if is_locked and (
                    cleaned_data.get(field_name) is None
                    or field_name not in cleaned_data
                ):
                    value_to_restore = None
                    if (
                        field_name in self.initial
                        and self.initial[field_name] is not None
                    ):
                        value_to_restore = self.initial[field_name]
                    elif instance and instance.pk and hasattr(instance, field_name):
                        value_to_restore = getattr(instance, field_name)
                    if value_to_restore is not None:
                        if field_name == "insumo_principal" and isinstance(
                            value_to_restore, int
                        ):
                            from .models import Insumo

                            value_to_restore = Insumo.objects.get(pk=value_to_restore)
                        cleaned_data[field_name] = value_to_restore
        insumo = cleaned_data.get("insumo_principal")
        if insumo:
            if (
                not cleaned_data.get("cantidad_principal")
                and self.fields["cantidad_principal"].required
            ):
                self.add_error("cantidad_principal", "La cantidad es requerida.")
            if (
                cleaned_data.get("precio_unitario_compra") is None
                and self.fields["precio_unitario_compra"].required
            ):
                self.add_error(
                    "precio_unitario_compra",
                    "El precio unitario es requerido (se espera de la oferta del proveedor).",
                )
        return cleaned_data


class ReporteProduccionForm(forms.ModelForm):
    TIPO_PROBLEMA_CHOICES = [
        ("", "Seleccionar tipo..."),
        ("Falta de Insumos", "Falta de Insumos"),
        ("Falla de Maquinaria", "Falla de Maquinaria"),
        ("Error de Calidad", "Error de Calidad Detectado"),
        ("Problema de Personal", "Problema de Personal"),
        ("Otro", "Otro (especificar)"),
    ]
    tipo_problema = forms.ChoiceField(
        choices=TIPO_PROBLEMA_CHOICES,
        widget=forms.Select(
            attrs={"class": "form-select mb-3"}
        ),  # Añadido mb-3 para espaciado
    )
    sector_reporta = forms.ModelChoiceField(
        queryset=SectorAsignado.objects.all().order_by("nombre"),  # Añadido order_by
        required=False,
        widget=forms.Select(attrs={"class": "form-select mb-3"}),
        label="Sector que Reporta (Opcional)",
    )

    class Meta:
        model = Reportes
        fields = ["tipo_problema", "informe_reporte", "sector_reporta"]
        widgets = {
            "informe_reporte": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Describa detalladamente el problema...",
                }
            ),
        }
        labels = {
            "tipo_problema": "Tipo de Problema Reportado",
            "informe_reporte": "Descripción Detallada del Problema",
        }

    def __init__(self, *args, **kwargs):
        self.orden_produccion = kwargs.pop("orden_produccion", None)
        super().__init__(*args, **kwargs)

        if self.orden_produccion and self.orden_produccion.sector_asignado_op:
            self.fields["sector_reporta"].initial = (
                self.orden_produccion.sector_asignado_op
            )
