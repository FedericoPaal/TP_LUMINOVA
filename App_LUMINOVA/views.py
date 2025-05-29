import logging
from datetime import timedelta

# Django Core Imports
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt # Usar con precaución
from django.db import transaction, IntegrityError as DjangoIntegrityError
from django.db.models import ProtectedError, Q, F, Prefetch

# Django Contrib Imports
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

# ReportLab (Third-party for PDF generation)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors

# Local Application Imports (Models)
from .models import (
    AuditoriaAcceso, CategoriaProductoTerminado, OfertaProveedor, ProductoTerminado,
    CategoriaInsumo, Insumo, ComponenteProducto, Proveedor, Cliente, Orden,
    OrdenVenta, ItemOrdenVenta, EstadoOrden, SectorAsignado, OrdenProduccion,
    Reportes, Factura, RolDescripcion, Fabricante,
)

# Local Application Imports (Forms)
from .forms import (
    FacturaForm, OrdenCompraForm, RolForm, PermisosRolForm, ClienteForm, ProveedorForm,
    OrdenVentaForm, ItemOrdenVentaFormSet, OrdenProduccionUpdateForm, ReporteProduccionForm
    # Nota: 'Reportes' como formulario fue eliminado de la importación, ya que es un modelo.
)

logger = logging.getLogger(__name__)

# --- HELPER FUNCTIONS ---
def es_admin(user):
    return user.groups.filter(name='administrador').exists() or user.is_superuser

def es_admin_o_rol(user, roles_permitidos=None):
    if user.is_superuser:
        return True
    if roles_permitidos is None:
        roles_permitidos = []
    return user.groups.filter(name__in=[rol.lower() for rol in roles_permitidos]).exists()

# --- GENERAL VIEWS & AUTHENTICATION ---
def inicio(request): # Esta vista es la que se muestra si el usuario no está autenticado
    if request.user.is_authenticated:
        return redirect('App_LUMINOVA:dashboard')
    return redirect('App_LUMINOVA:login') # Redirige a login si no está autenticado

def login_view(request):
    if request.user.is_authenticated:
        return redirect('App_LUMINOVA:admin/dashboard')

    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password'),
        )
        if user:
            login(request, user)
            return redirect('App_LUMINOVA:admin/dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    # El template 'login.html' está en App_LUMINOVA/templates/login.html
    return render(request, 'login.html')

@login_required
def dashboard_view(request):
    return render(request, 'admin/dashboard.html')

# --- ADMINISTRATOR VIEWS ---
@login_required
@user_passes_test(es_admin)
def lista_usuarios(request):
    usuarios = User.objects.filter(is_superuser=False).prefetch_related('groups').order_by('id')
    context = {
        'usuarios': usuarios,
        'titulo_seccion': "Gestión de Usuarios"
    }
    return render(request, 'admin/usuarios.html', context)

@login_required
@user_passes_test(es_admin)
def crear_usuario(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        rol_name = request.POST.get('rol')
        estado_str = request.POST.get('estado')
        password = request.POST.get('password', 'temporal')

        errors = {}
        if not username: errors['username'] = 'Este campo es requerido.'
        if User.objects.filter(username=username).exists(): errors['username'] = 'Este nombre de usuario ya existe.'
        if not email: errors['email'] = 'Este campo es requerido.'
        if errors:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest': 
                return JsonResponse({'success': False, 'errors': errors})
            else: 
                for field, error_list in errors.items():
                    for err in error_list if isinstance(error_list, list) else [error_list]:
                         messages.error(request, f"Error en {field}: {err}")
                return redirect('App_LUMINOVA:lista_usuarios')
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password 
            )
            user.is_active = (estado_str == 'Activo')

            if rol_name:
                try:
                    group = Group.objects.get(name=rol_name)
                    user.groups.add(group)
                except Group.DoesNotExist:
                    user.delete() 
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'errors': {'rol': [f"El rol '{rol_name}' no existe."]}})
                    else:
                        messages.error(request, f"El rol '{rol_name}' no existe.")
                        return redirect('App_LUMINOVA:lista_usuarios')

            user.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'rol': rol_name if rol_name else "Sin Rol",
                        'estado': "Activo" if user.is_active else "Inactivo"
                    }
                })
            else:
                messages.success(request, f"Usuario '{user.username}' creado exitosamente.")
                return redirect('App_LUMINOVA:lista_usuarios')

        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'__all__': [str(e)]}})
            else:
                messages.error(request, f"Error al crear usuario: {str(e)}")
                return redirect('App_LUMINOVA:lista_usuarios')
    return redirect('App_LUMINOVA:lista_usuarios')

@login_required
@user_passes_test(es_admin)
@transaction.atomic
@require_POST 
def editar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if request.method == 'POST':
        usuario.username = request.POST.get('username', usuario.username)
        usuario.email = request.POST.get('email', usuario.email)
        # Actualizar rol
        rol_name = request.POST.get('rol')
        usuario.groups.clear()
        if rol_name:
            try:
                group = Group.objects.get(name=rol_name)
                usuario.groups.add(group)
            except Group.DoesNotExist:
                messages.error(request, f"El rol '{rol_name}' no existe.")

        # Actualizar estado
        estado_str = request.POST.get('estado')
        if estado_str:
            usuario.is_active = (estado_str == 'Activo')

        usuario.save()
        messages.success(request, f"Usuario '{usuario.username}' actualizado exitosamente.")
        return redirect('App_LUMINOVA:lista_usuarios')
    return redirect('App_LUMINOVA:lista_usuarios') # Si no es POST

@login_required
@user_passes_test(es_admin)
@transaction.atomic
@require_POST 
def eliminar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if usuario == request.user:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
        return redirect('App_LUMINOVA:lista_usuarios')
    try:
        nombre_usuario = usuario.username
        usuario.delete()
        messages.success(request, f"Usuario '{nombre_usuario}' eliminado exitosamente.")
    except Exception as e:
        messages.error(request, f"Error al eliminar usuario: {str(e)}")
    return redirect('App_LUMINOVA:lista_usuarios')

@login_required
def roles_permisos_view(request):
    roles = Group.objects.all().select_related('descripcion_extendida').prefetch_related('permissions').order_by('name')
    context = {
        'roles': roles,
        'titulo_seccion': "Gestión de Roles y Permisos"
    }
    return render(request, 'admin/roles_permisos.html', context)

@login_required
def auditoria_view(request):
    auditorias = AuditoriaAcceso.objects.select_related('usuario').order_by('-fecha_hora')
    context = {
        'auditorias': auditorias,
        'titulo_seccion': "Auditoría de Acceso"
    }
    return render(request, 'admin/auditoria.html', context)

# --- AJAX VIEWS FOR ROLES & PERMISSIONS ---
@login_required
@user_passes_test(es_admin)
@require_POST
@csrf_exempt # Considera csrf_protect y enviar token con JS
def crear_rol_ajax(request):
    form = RolForm(request.POST)
    if form.is_valid():
        nombre_rol = form.cleaned_data['nombre']
        descripcion_rol = form.cleaned_data['descripcion']
        try:
            with transaction.atomic(): # Para asegurar que ambas creaciones ocurran o ninguna
                nuevo_grupo = Group.objects.create(name=nombre_rol)
                if descripcion_rol:
                    RolDescripcion.objects.create(group=nuevo_grupo, descripcion=descripcion_rol)

                return JsonResponse({
                    'success': True,
                    'rol': {
                        'id': nuevo_grupo.id,
                        'nombre': nuevo_grupo.name,
                        'descripcion': descripcion_rol
                    }
                })
        except Exception as e:
            return JsonResponse({'success': False, 'errors': {'__all__': [str(e)]}})
    else:
        return JsonResponse({'success': False, 'errors': form.errors})

@login_required
@user_passes_test(es_admin)
@require_GET
def get_rol_data_ajax(request):
    rol_id = request.GET.get('rol_id')
    try:
        grupo = Group.objects.get(id=rol_id)
        descripcion_extendida = ""
        if hasattr(grupo, 'descripcion_extendida') and grupo.descripcion_extendida:
            descripcion_extendida = grupo.descripcion_extendida.descripcion

        return JsonResponse({
            'success': True,
            'rol': {
                'id': grupo.id,
                'nombre': grupo.name,
                'descripcion': descripcion_extendida
            }
        })
    except Group.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rol no encontrado.'}, status=404)

@login_required
@user_passes_test(es_admin)
@require_POST
@csrf_exempt # Considera csrf_protect
def editar_rol_ajax(request):
    rol_id = request.POST.get('rol_id') # rol_id viene del form
    try:
        grupo_a_editar = Group.objects.get(id=rol_id)
    except Group.DoesNotExist:
        return JsonResponse({'success': False, 'errors': {'__all__': ['Rol no encontrado.']}}, status=404)

    form = RolForm(request.POST, initial={'rol_id': rol_id}) # Pasar rol_id para validación de unicidad

    if form.is_valid():
        nombre_rol = form.cleaned_data['nombre']
        descripcion_rol = form.cleaned_data['descripcion']
        try:
            with transaction.atomic():
                grupo_a_editar.name = nombre_rol
                grupo_a_editar.save()

                desc_obj, created = RolDescripcion.objects.get_or_create(group=grupo_a_editar)
                desc_obj.descripcion = descripcion_rol
                desc_obj.save()

            return JsonResponse({
                'success': True,
                'rol': {
                    'id': grupo_a_editar.id,
                    'nombre': grupo_a_editar.name,
                    'descripcion': descripcion_rol
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'errors': {'__all__': [str(e)]}})
    else:
        return JsonResponse({'success': False, 'errors': form.errors})

@login_required
@require_POST # Debería ser POST para una acción de eliminación
@csrf_exempt # Considera csrf_protect
def eliminar_rol_ajax(request):
    import json # Para parsear el body si es JSON
    try:
        data = json.loads(request.body)
        rol_id = data.get('rol_id')
        grupo = Group.objects.get(id=rol_id)

        # Opcional: Verificar si hay usuarios en este grupo antes de eliminar
        if grupo.user_set.exists():
            return JsonResponse({'success': False, 'error': 'No se puede eliminar el rol porque tiene usuarios asignados.'}, status=400)

        grupo.delete() # RolDescripcion se borrará en cascada
        return JsonResponse({'success': True})
    except Group.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rol no encontrado.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@user_passes_test(es_admin)
@require_GET
def get_permisos_rol_ajax(request):
    rol_id = request.GET.get('rol_id')
    try:
        rol = Group.objects.get(id=rol_id)
        permisos_del_rol_ids = list(rol.permissions.values_list('id', flat=True))

        todos_los_permisos = Permission.objects.select_related('content_type').all()
        permisos_data = []
        for perm in todos_los_permisos:
            permisos_data.append({
                'id': perm.id,
                'name': perm.name, # Nombre legible
                'codename': perm.codename, # Codename (ej. add_user)
                'content_type_app_label': perm.content_type.app_label, # Nombre de la app (ej. auth, App_Luminova)
                'content_type_model': perm.content_type.model # Nombre del modelo (ej. user, insumo)
            })

        return JsonResponse({
            'success': True,
            'todos_los_permisos': permisos_data,
            'permisos_del_rol': permisos_del_rol_ids
        })
    except Group.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rol no encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@user_passes_test(es_admin)
@require_POST
@csrf_exempt # Considera csrf_protect
def actualizar_permisos_rol_ajax(request):
    import json
    try:
        data = json.loads(request.body)
        rol_id = data.get('rol_id')
        permisos_ids_str = data.get('permisos_ids', []) # Lista de IDs como strings
        permisos_ids = [int(pid) for pid in permisos_ids_str]


        rol = Group.objects.get(id=rol_id)

        # Actualizar permisos
        rol.permissions.set(permisos_ids) # set() maneja agregar y quitar

        return JsonResponse({'success': True, 'message': 'Permisos actualizados.'})
    except Group.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rol no encontrado.'}, status=404)
    except Permission.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Uno o más permisos no son válidos.'}, status=400)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'IDs de permisos inválidos.'}, status=400)
    except json.JSONDecodeError:
         return JsonResponse({'success': False, 'error': 'Datos JSON inválidos.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# --- VENTAS VIEWS ---
@login_required
def lista_clientes_view(request):
    if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
        messages.error(request, "Acceso denegado.")
        return redirect('App_LUMINOVA:dashboard')

    clientes = Cliente.objects.all().order_by('nombre')
    form_para_crear = ClienteForm() # Instancia para el modal de creación

    context = {
        'clientes_list': clientes,
        'cliente_form_crear': form_para_crear, # Para el modal de creación
        'ClienteFormClass': ClienteForm,      # Pasamos la clase del formulario
        'titulo_seccion': 'Gestión de Clientes',
    }
    return render(request, 'ventas/ventas_clientes.html', context)

@login_required
@transaction.atomic
def crear_cliente_view(request):
    if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
        messages.error(request, "Acción no permitida.")
        return redirect('App_LUMINOVA:lista_clientes')

    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Cliente creado exitosamente.')
            except DjangoIntegrityError:
                messages.error(request, 'Error: Un cliente con ese nombre o email ya existe.')
            except Exception as e:
                messages.error(request, f'Error inesperado al crear cliente: {e}')
            return redirect('App_LUMINOVA:lista_clientes')
        else:
            # Re-render con errores (para modales puede ser complejo, simplificamos)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label or field}: {error}")
            return redirect('App_LUMINOVA:lista_clientes')
    return redirect('App_LUMINOVA:lista_clientes')

# ... (editar_cliente_view y eliminar_cliente_view pueden permanecer similares a como estaban) ...
@login_required
@transaction.atomic
def editar_cliente_view(request, cliente_id):
    if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
        messages.error(request, "Acción no permitida.")
        return redirect('App_LUMINOVA:lista_clientes')
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Cliente actualizado exitosamente.')
            except DjangoIntegrityError:
                messages.error(request, 'Error: Otro cliente ya tiene ese nombre o email.')
            except Exception as e:
                messages.error(request, f'Error inesperado al actualizar cliente: {e}')
            return redirect('App_LUMINOVA:lista_clientes')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label or field}: {error}")
            return redirect('App_LUMINOVA:lista_clientes')
    return redirect('App_LUMINOVA:lista_clientes')

@login_required
@transaction.atomic
def eliminar_cliente_view(request, cliente_id):
    if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
        messages.error(request, "Acción no permitida.")
        return redirect('App_LUMINOVA:lista_clientes')
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == 'POST':
        try:
            nombre_cliente = cliente.nombre
            cliente.delete()
            messages.success(request, f'Cliente "{nombre_cliente}" eliminado exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar cliente: {e}. Verifique que no tenga órdenes asociadas.')
    return redirect('App_LUMINOVA:lista_clientes')

@login_required
def ventas_lista_ov_view(request):
    if not es_admin_o_rol(request.user, ['ventas', 'produccion', 'administrador']): # Producción también podría ver OVs
        messages.error(request, "Acceso denegado.")
        return redirect('App_LUMINOVA:dashboard')

    ordenes = OrdenVenta.objects.select_related('cliente').prefetch_related(
        'items_ov__producto_terminado',
        'ops_generadas' # Usando el related_name de OrdenProduccion.orden_venta_origen
    ).order_by('-fecha_creacion')

    context = {
        'ordenes_list': ordenes,
        'titulo_seccion': 'Órdenes de Venta',
    }
    return render(request, 'ventas/ventas_lista_ov.html', context)

@login_required
@transaction.atomic
def ventas_crear_ov_view(request):
    if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
        messages.error(request, "Acción no permitida.")
        return redirect('App_LUMINOVA:ventas_lista_ov')

    if request.method == 'POST':
        form_ov = OrdenVentaForm(request.POST, prefix='ov')
        formset_items = ItemOrdenVentaFormSet(request.POST, prefix='items')

        if form_ov.is_valid() and formset_items.is_valid():
            ov = form_ov.save(commit=False)
            # El estado viene del form, si no, default del modelo.
            # El total_ov se calcula después de guardar los items.
            ov.total_ov = 0

            try:
                ov.save() # Guardar OV para obtener ID

                total_orden_calculado = 0
                items_guardados_para_op = []

                for form_item in formset_items:
                    if form_item.is_valid() and not form_item.cleaned_data.get('DELETE', False):
                        if form_item.cleaned_data.get('producto_terminado') and form_item.cleaned_data.get('cantidad'):
                            item = form_item.save(commit=False)
                            item.orden_venta = ov
                            # Asegurar que el precio_unitario_venta se toma del producto
                            item.precio_unitario_venta = item.producto_terminado.precio_unitario
                            item.subtotal = item.cantidad * item.precio_unitario_venta
                            total_orden_calculado += item.subtotal
                            item.save()
                            items_guardados_para_op.append(item)

                # formset_items.save_m2m() # No es necesario si no hay M2M directos en ItemOrdenVenta

                if not items_guardados_para_op:
                    messages.error(request, "Debe añadir al menos un producto a la orden.")
                    # No guardamos la OV si no tiene items, o podrías permitirlo
                    ov.delete() # Eliminar la OV vacía creada
                    # Re-renderizar el form
                    context = {'form_ov': form_ov, 'formset_items': formset_items, 'titulo_seccion': 'Nueva Orden de Venta'}
                    return render(request, 'ventas/ventas_crear_ov.html', context)


                ov.total_ov = total_orden_calculado
                ov.save(update_fields=['total_ov']) # Solo actualizar el total

                messages.success(request, f'Orden de Venta "{ov.numero_ov}" creada con total ${ov.total_ov:.2f}.')

                # RF-02: Generación automática de Órdenes de Producción
                estado_op_inicial = EstadoOrden.objects.filter(nombre__iexact='Pendiente').first()
                if not estado_op_inicial:
                    messages.error(request, "Error crítico: El estado 'Pendiente' para OP no está configurado. Las OPs no se generarán.")
                else:
                    for item_ov in items_guardados_para_op: # Usar los items que realmente se guardaron
                        try:
                            op_count = OrdenProduccion.objects.count()
                            next_op_number = f"OP-{str(op_count + 1).zfill(5)}"
                            while OrdenProduccion.objects.filter(numero_op=next_op_number).exists():
                                op_count += 1
                                next_op_number = f"OP-{str(op_count + 1).zfill(5)}"

                            OrdenProduccion.objects.create(
                                numero_op=next_op_number,
                                orden_venta_origen=ov,
                                producto_a_producir=item_ov.producto_terminado,
                                cantidad_a_producir=item_ov.cantidad,
                                # cliente_final=ov.cliente, # Se puede obtener de ov.cliente en la plantilla
                                fecha_solicitud=timezone.now(),
                                estado_op=estado_op_inicial, # Usando el modelo EstadoOrden
                            )
                            messages.info(request, f'OP "{next_op_number}" para "{item_ov.producto_terminado.descripcion}" generada.')
                        except Exception as e_op:
                            messages.error(request, f'Error al generar OP para item "{item_ov.producto_terminado.descripcion}": {e_op}')

                return redirect('App_LUMINOVA:ventas_lista_ov')

            except DjangoIntegrityError as e_int:
                 if 'UNIQUE constraint' in str(e_int) and 'numero_ov' in str(e_int):
                    messages.error(request, f"El número de orden de venta '{form_ov.cleaned_data.get('numero_ov')}' ya existe.")
                 else:
                    messages.error(request, f"Error de base de datos: {e_int}")
            except Exception as e:
                messages.error(request, f'Error inesperado al crear OV: {e}')
        else:
            # Construir un mensaje de error más detallado
            error_txt = "Por favor, corrija los siguientes errores: "
            for field, errors in form_ov.errors.items():
                error_txt += f"{form_ov.fields[field].label or field}: {', '.join(errors)}. "
            for i, form_item_errors in enumerate(formset_items.errors):
                if form_item_errors:
                    error_txt += f"Ítem {i+1}: "
                    for field, errors in form_item_errors.items():
                         error_txt += f"{formset_items.forms[i].fields[field].label or field}: {', '.join(errors)}. "
            messages.error(request, error_txt)

    else: # GET
        form_ov = OrdenVentaForm(prefix='ov')
        ov_count = OrdenVenta.objects.count()
        next_ov_number = f"OV-{str(ov_count + 1).zfill(4)}"
        while OrdenVenta.objects.filter(numero_ov=next_ov_number).exists():
            ov_count += 1
            next_ov_number = f"OV-{str(ov_count + 1).zfill(4)}"
        form_ov.fields['numero_ov'].initial = next_ov_number
        form_ov.fields['estado'].initial = 'PENDIENTE'
        formset_items = ItemOrdenVentaFormSet(prefix='items', queryset=ItemOrdenVenta.objects.none())

    context = {
        'form_ov': form_ov,
        'formset_items': formset_items,
        'titulo_seccion': 'Nueva Orden de Venta',
    }
    return render(request, 'ventas/ventas_crear_ov.html', context)

@login_required
def ventas_detalle_ov_view(request, ov_id):
    orden_venta = get_object_or_404(
        OrdenVenta.objects.select_related('cliente').prefetch_related(
            'items_ov__producto_terminado',
            'ops_generadas__estado_op', # Necesitamos el estado de cada OP
            'factura_asociada'
        ),
        id=ov_id
    )

    factura_form = None
    puede_facturar = False
    detalle_cancelacion_factura = ""

    if not hasattr(orden_venta, 'factura_asociada') or not orden_venta.factura_asociada:
        # Lógica para determinar si se puede facturar
        ops_asociadas = orden_venta.ops_generadas.all()
        if not ops_asociadas.exists() and orden_venta.estado == 'CONFIRMADA': 
            # Si no hay OPs (ej. productos solo de stock) y está confirmada, podría facturarse.
            # Esto depende de tu flujo si una OV puede no generar OPs.
            # Por ahora, asumimos que OVs CONFIRMADAS sin OPs son para productos ya en stock.
            puede_facturar = True # O cambiar estado a LISTA_ENTREGA primero
        elif ops_asociadas.exists():
            ops_completadas = ops_asociadas.filter(estado_op__nombre__iexact="Completada").count()
            ops_canceladas = ops_asociadas.filter(estado_op__nombre__iexact="Cancelada").count()
            ops_totales = ops_asociadas.count()

            # Se puede facturar si todas las OPs no canceladas están completadas
            if ops_completadas + ops_canceladas == ops_totales and ops_completadas > 0:
                puede_facturar = True
                if ops_canceladas > 0:
                    detalle_cancelacion_factura = f"Nota: {ops_canceladas} orden(es) de producción asociada(s) fueron canceladas."
            elif orden_venta.estado == 'PRODUCCION_CON_PROBLEMAS' and ops_completadas > 0 and (ops_completadas + ops_canceladas == ops_totales):
                # Caso específico donde la OV está con problemas pero hay partes completadas
                puede_facturar = True
                detalle_cancelacion_factura = f"Facturación parcial. Nota: {ops_canceladas} orden(es) de producción asociada(s) fueron canceladas."
            elif orden_venta.estado == 'LISTA_ENTREGA': # Ya está explícitamente lista
                 puede_facturar = True


        if puede_facturar:
            factura_form = FacturaForm()
            # Si hay detalle de cancelación, podrías pasarlo al form o al contexto
            # para incluirlo en notas de la factura si el form lo permite.
            # form.fields['notas_factura'].initial = detalle_cancelacion_factura (si tuvieras ese campo)

    context = {
        'ov': orden_venta,
        'items_ov': orden_venta.items_ov.all(),
        'factura_form': factura_form,
        'puede_facturar': puede_facturar, # Para la plantilla
        'detalle_cancelacion_factura': detalle_cancelacion_factura, # Para la plantilla
        'titulo_seccion': f"Detalle Orden de Venta: {orden_venta.numero_ov}",
    }
    return render(request, 'ventas/ventas_detalle_ov.html', context)


@login_required
@transaction.atomic
def ventas_generar_factura_view(request, ov_id):
    orden_venta = get_object_or_404(OrdenVenta.objects.prefetch_related('items_ov__producto_terminado', 'ops_generadas__estado_op'), id=ov_id)

    if hasattr(orden_venta, 'factura_asociada') and orden_venta.factura_asociada:
        # ... (mensaje de advertencia existente) ...
        return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)

    # Re-evaluar la condición de facturación aquí también por seguridad
    puede_facturar_ahora = False
    total_a_facturar_calculado = 0
    items_a_facturar_desc = []

    ops_asociadas = orden_venta.ops_generadas.all()
    items_ov = orden_venta.items_ov.all()

    if not ops_asociadas.exists() and orden_venta.estado == 'CONFIRMADA': # Asumir stock para OV sin OPs
        puede_facturar_ahora = True
        total_a_facturar_calculado = orden_venta.total_ov
        for item_ov in items_ov:
             items_a_facturar_desc.append(f"{item_ov.cantidad} x {item_ov.producto_terminado.descripcion}")

    elif ops_asociadas.exists():
        ops_completadas_ids = [op.producto_a_producir_id for op in ops_asociadas if op.estado_op and op.estado_op.nombre.lower() == "completada"]
        
        if not ops_completadas_ids and orden_venta.estado not in ['LISTA_ENTREGA', 'COMPLETADA']: # Si no hay OPs completadas y no está lista/completada
             messages.error(request, f"No hay ítems completados para facturar en la OV {orden_venta.numero_ov}.")
             return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)

        for item_ov in items_ov:
            # Si la OP asociada a este item_ov (basada en producto) está completada, se factura
            # Esta lógica asume una OP por tipo de producto en la OV. Si un ítem de OV puede generar varias OPs, es más complejo.
            op_correspondiente = ops_asociadas.filter(producto_a_producir=item_ov.producto_terminado).first()
            if op_correspondiente and op_correspondiente.estado_op and op_correspondiente.estado_op.nombre.lower() == "completada":
                total_a_facturar_calculado += item_ov.subtotal
                items_a_facturar_desc.append(f"{item_ov.cantidad} x {item_ov.producto_terminado.descripcion}")
                puede_facturar_ahora = True # Al menos un item se puede facturar
            elif not op_correspondiente and orden_venta.estado in ['LISTA_ENTREGA', 'COMPLETADA']: 
                # Si no hay OP para este item pero la OV está lista (ej. producto de stock)
                total_a_facturar_calculado += item_ov.subtotal
                items_a_facturar_desc.append(f"{item_ov.cantidad} x {item_ov.producto_terminado.descripcion}")
                puede_facturar_ahora = True


    if not puede_facturar_ahora:
        messages.error(request, f"La Orden de Venta {orden_venta.numero_ov} no cumple las condiciones para ser facturada en este momento.")
        return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)

    if request.method == 'POST':
        form = FacturaForm(request.POST)
        if form.is_valid():
            try:
                factura = form.save(commit=False)
                factura.orden_venta = orden_venta
                factura.total_facturado = total_a_facturar_calculado # Usar el total calculado
                factura.cliente = orden_venta.cliente
                factura.fecha_emision = timezone.now()
                
                # Añadir notas sobre ítems cancelados o facturación parcial si es necesario
                notas_adicionales_factura = []
                ops_canceladas_nombres = [op.producto_a_producir.descripcion for op in ops_asociadas if op.estado_op and op.estado_op.nombre.lower() == "cancelada"]
                if ops_canceladas_nombres:
                    notas_adicionales_factura.append(f"Ítems no incluidos por cancelación de OP: {', '.join(ops_canceladas_nombres)}.")
                
                # Si tienes un campo de notas en el modelo Factura:
                # factura.notas = " ".join(notas_adicionales_factura) # o agrégalo a las notas de la OV

                factura.save()
                
                # Actualizar el estado de la OV a "COMPLETADA" (o un estado facturado) si es apropiado
                if orden_venta.estado != 'COMPLETADA' and puede_facturar_ahora: # Solo si se facturó algo
                    orden_venta.estado = 'COMPLETADA' # O 'FACTURADA' si tienes ese estado
                    orden_venta.save(update_fields=['estado'])
                    messages.info(request, f"Estado de OV {orden_venta.numero_ov} actualizado a 'Completada'.")

                messages.success(request, f"Factura N° {factura.numero_factura} generada por ${factura.total_facturado:.2f} para la OV {orden_venta.numero_ov}.")
                if notas_adicionales_factura:
                    messages.info(request, " ".join(notas_adicionales_factura))
                return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)
            # ... (manejo de errores de integridad y otros) ...
            except DjangoIntegrityError:
                 messages.error(request, f"Error: El número de factura '{form.cleaned_data.get('numero_factura')}' ya existe.")
            except Exception as e:
                messages.error(request, f"Error al generar la factura: {e}")
        else:
            # ... (manejo de formulario inválido) ...
            pass

    # Si es GET o el form no es válido, redirige
    return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)

@login_required
@transaction.atomic
def ventas_editar_ov_view(request, ov_id):
    # if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
    #     messages.error(request, "Acción no permitida.")
    #     return redirect('App_LUMINOVA:ventas_lista_ov')

    orden_venta = get_object_or_404(OrdenVenta, id=ov_id)

    # RESTRICCIÓN: Solo editar si está en estados permitidos y OPs no avanzadas
    if orden_venta.estado not in ['PENDIENTE', 'CONFIRMADA'] or \
       orden_venta.ops_generadas.exclude(estado_op__nombre__iexact='Pendiente').exists():
        messages.error(request, f"La Orden de Venta {orden_venta.numero_ov} no se puede editar porque su producción ya ha avanzado o su estado no lo permite.")
        return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)

    if request.method == 'POST':
        form_ov = OrdenVentaForm(request.POST, instance=orden_venta, prefix='ov')
        formset_items = ItemOrdenVentaFormSet(request.POST, instance=orden_venta, prefix='items')

        if form_ov.is_valid() and formset_items.is_valid():
            ov_actualizada = form_ov.save(commit=False)
            # Guardar ítems primero para recalcular total
            items_actualizados = formset_items.save(commit=False)

            total_recalculado = 0
            for item in items_actualizados:
                item.precio_unitario_venta = item.producto_terminado.precio_unitario # Re-asegurar precio
                item.subtotal = item.cantidad * item.precio_unitario_venta
                total_recalculado += item.subtotal
                item.save() # Guardar cada item

            # Guardar items marcados para eliminar
            for form_item_deleted in formset_items.deleted_forms:
                if form_item_deleted.instance.pk: # Solo si el item ya existía
                    form_item_deleted.instance.delete()

            formset_items.save_m2m()


            ov_actualizada.total_ov = total_recalculado
            ov_actualizada.save() # Guardar la OV actualizada

            messages.success(request, f"Orden de Venta {ov_actualizada.numero_ov} actualizada exitosamente.")
            # Aquí deberías decidir qué hacer con las OPs si los ítems cambiaron.
            # Por ahora, solo actualizamos la OV. Una lógica más compleja podría cancelar OPs antiguas y crear nuevas.
            return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=ov_actualizada.id)
        else:
            messages.error(request, "Por favor, corrija los errores en el formulario.")
    else: # GET
        form_ov = OrdenVentaForm(instance=orden_venta, prefix='ov')
        formset_items = ItemOrdenVentaFormSet(instance=orden_venta, prefix='items')

    context = {
        'form_ov': form_ov,
        'formset_items': formset_items,
        'orden_venta': orden_venta, # Para el título y otros datos
        'titulo_seccion': f'Editar Orden de Venta: {orden_venta.numero_ov}',
    }
    return render(request, 'ventas/ventas_editar_ov.html', context)


@login_required
@transaction.atomic
@require_POST # Esta acción solo debe ser por POST desde el modal
def ventas_cancelar_ov_view(request, ov_id):
    # if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
    #     messages.error(request, "Acción no permitida.")
    #     return redirect('App_LUMINOVA:ventas_lista_ov')

    orden_venta = get_object_or_404(OrdenVenta, id=ov_id)

    if orden_venta.estado in ['COMPLETADA', 'CANCELADA']:
        messages.warning(request, f"La Orden de Venta {orden_venta.numero_ov} ya está {orden_venta.get_estado_display()} y no puede cancelarse nuevamente.")
        return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=ov_id)

    estado_op_cancelada = EstadoOrden.objects.filter(nombre__iexact='Cancelada').first()
    estado_op_completada = EstadoOrden.objects.filter(nombre__iexact='Completada').first() # O 'Terminado'

    if not estado_op_cancelada:
        messages.error(request, "Error crítico: El estado 'Cancelada' para OP no está configurado.")
        return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=ov_id)

    ops_asociadas = orden_venta.ops_generadas.all()
    for op in ops_asociadas:
        if op.estado_op != estado_op_completada: # No cancelar OPs que ya se completaron
            op.estado_op = estado_op_cancelada
            op.save(update_fields=['estado_op'])
            messages.info(request, f"Orden de Producción {op.numero_op} asociada ha sido cancelada.")
        else:
            messages.warning(request, f"Orden de Producción {op.numero_op} ya está completada y no se cancelará.")


    orden_venta.estado = 'CANCELADA'
    orden_venta.save(update_fields=['estado'])
    messages.success(request, f"Orden de Venta {orden_venta.numero_ov} ha sido cancelada.")

    return redirect('App_LUMINOVA:ventas_lista_ov')

# --- COMPRAS VIEWS ---
@login_required
def compras_lista_oc_view(request):
    # if not es_admin_o_rol(request.user, ['compras', 'administrador']):
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    # Filtrar órdenes de tipo 'compra'
    # Asumiendo que tu modelo Orden tiene un campo 'tipo' y 'proveedor'
    ordenes_compra = Orden.objects.filter(tipo='compra').select_related(
        'proveedor', # Si el campo se llama 'proveedor' en el modelo Orden
        'insumo_principal'     # Si el campo se llama 'insumo' en el modelo Orden
    ).order_by('-fecha_creacion')

    # Para un futuro modal de creación de OC
    # from .forms import OrdenCompraForm # Necesitarás crear este formulario
    # form_oc = OrdenCompraForm()
    # oc_count = Orden.objects.filter(tipo='compra').count()
    # next_oc_number = f"OC-{str(oc_count + 1).zfill(4)}"
    # form_oc.fields['numero_orden'].initial = next_oc_number

    context = {
        'ordenes_list': ordenes_compra, # Nombre genérico para la plantilla
        'titulo_seccion': 'Listado de Órdenes de Compra',
        # 'form_orden': form_oc, # Para el modal de creación
        # 'tipo_orden_actual': 'compra',
    }
    # Necesitarás una plantilla para esto, ej. 'compras/compras_lista_oc.html'
    return render(request, 'compras/compras_lista_oc.html', context)

@login_required
def compras_desglose_view(request):
    logger.info("--- compras_desglose_view: INICIO ---")

    UMBRAL_STOCK_BAJO_INSUMOS = 15000
    insumos_criticos_query = Insumo.objects.filter(
        stock__lt=UMBRAL_STOCK_BAJO_INSUMOS
    ).select_related('categoria').order_by(
        'categoria__nombre', 'stock', 'descripcion'
    )
    
    insumos_criticos_list_con_estado_oc = []
    for insumo in insumos_criticos_query:
        # Verificar si existe una OC no finalizada/cancelada para este insumo
        oc_pendiente_existe = Orden.objects.filter(
            insumo_principal=insumo,
            tipo='compra'
        ).exclude(
            Q(estado='COMPLETADA') | Q(estado='RECIBIDA_TOTAL') | Q(estado='CANCELADA')
        ).exists()
        
        insumos_criticos_list_con_estado_oc.append({
            'insumo': insumo,
            'tiene_oc_pendiente': oc_pendiente_existe
        })
        
        if oc_pendiente_existe:
            logger.info(f"Insumo crítico '{insumo.descripcion}' (ID: {insumo.id}) YA TIENE una OC pendiente.")
        else:
            logger.info(f"Insumo crítico '{insumo.descripcion}' (ID: {insumo.id}) NO tiene OC pendiente.")

    logger.info(f"Compras_desglose_view: Total insumos críticos encontrados: {len(insumos_criticos_list_con_estado_oc)}")
    
    context = {
        'insumos_criticos_list_con_estado': insumos_criticos_list_con_estado_oc, # Nueva lista con el flag
        'umbral_stock_bajo': UMBRAL_STOCK_BAJO_INSUMOS,
        'titulo_seccion': 'Gestionar Compra por Stock Bajo',
    }
    return render(request, 'compras/compras_desglose.html', context)


@login_required
def compras_seguimiento_view(request):
    # Esta vista mostraría las OCs que ya fueron enviadas a proveedores y están en seguimiento
    # estado_solicitada = EstadoOrden.objects.filter(nombre__iexact='Solicitada').first() # Necesitarías EstadoOrden para OC
    # ordenes_en_seguimiento = []
    # if estado_solicitada:
    ordenes = Orden.objects.filter(tipo='compra', estado='estado_solicitada').order_by('-fecha_creacion')

    context = {
        # 'ordenes_solicitadas_list': ordenes_en_seguimiento,
        'ordenes_solicitadas_list': ordenes, # Placeholder por ahora
        'titulo_seccion': 'Seguimiento de Órdenes de Compra',
    }
    return render(request, 'compras/seguimiento.html', context)

@login_required
def compras_tracking_pedido_view(request, numero_orden_track):
    # Aquí buscarías la OC por 'numero_orden_track' y mostrarías su info de tracking
    # orden_compra = get_object_or_404(Orden, numero_orden=numero_orden_track, tipo='compra')
    context = {
        # 'orden': orden_compra,
        'numero_orden_track': numero_orden_track, # Pasar para mostrar en la plantilla
        'titulo_seccion': f'Tracking OC: {numero_orden_track}',
    }
    return render(request, 'compras/compras_tracking.html', context)

@login_required
def compras_desglose_detalle_oc_view(request, numero_orden_desglose):
    # Aquí mostrarías el detalle de una OC específica de la vista de desglose
    # orden_compra = get_object_or_404(Orden, numero_orden=numero_orden_desglose, tipo='compra')
    # Aquí podrías listar los insumos si una OC puede tener múltiples.
    context = {
        # 'orden': orden_compra,
        'numero_orden_desglose': numero_orden_desglose, # Pasar para mostrar en la plantilla
        'titulo_seccion': f'Detalle Desglose OC: {numero_orden_desglose}',
    }
    return render(request, 'compras/compras_desglose_detalle.html', context) # Nombre de plantilla sugerido

@login_required
def compras_seleccionar_proveedor_para_insumo_view(request, insumo_id):
    insumo_objetivo = get_object_or_404(Insumo.objects.select_related('categoria'), id=insumo_id)
    logger.info(f"Seleccionando proveedor para insumo: {insumo_objetivo.descripcion} (ID: {insumo_id})")

    if request.method == 'POST':
        oferta_id_seleccionada = request.POST.get('oferta_proveedor_id')
        proveedor_fallback_id_seleccionado = request.POST.get('proveedor_fallback_id')
        
        proveedor_id_final_para_oc = None # Renombrado para claridad
        
        if oferta_id_seleccionada:
            try:
                oferta = OfertaProveedor.objects.get(id=oferta_id_seleccionada, insumo_id=insumo_id) # Asegurar que la oferta sea para este insumo
                proveedor_id_final_para_oc = oferta.proveedor.id
                logger.info(f"Oferta ID {oferta_id_seleccionada} seleccionada. Proveedor ID: {proveedor_id_final_para_oc}")
            except OfertaProveedor.DoesNotExist:
                messages.error(request, "La oferta seleccionada no es válida o no corresponde al insumo.")
                return redirect('App_LUMINOVA:compras_seleccionar_proveedor_para_insumo', insumo_id=insumo_id)
        elif proveedor_fallback_id_seleccionado:
            proveedor_id_final_para_oc = proveedor_fallback_id_seleccionado
            logger.info(f"Proveedor fallback ID {proveedor_fallback_id_seleccionado} seleccionado.")
        else:
            messages.error(request, "Debe seleccionar un proveedor u oferta.")
            return redirect('App_LUMINOVA:compras_seleccionar_proveedor_para_insumo', insumo_id=insumo_id)

        # Redirigir a la vista de creación de OC con los nombres de parámetros que espera la URL pattern
        logger.info(f"Redirigiendo a crear OC con insumo_id={insumo_id} y proveedor_id={proveedor_id_final_para_oc}")
        return redirect('App_LUMINOVA:compras_crear_oc_desde_insumo_y_proveedor', 
                        insumo_id=insumo_id,  # <--- USA 'insumo_id'
                        proveedor_id=proveedor_id_final_para_oc) # <--- USA 'proveedor_id'
    # ... (resto de la lógica GET) ...
    # ... (código de la lógica GET de la vista) ...
    ofertas = OfertaProveedor.objects.filter(insumo_id=insumo_id).select_related('proveedor').order_by('precio_unitario_compra', 'tiempo_entrega_estimado_dias')
    insumo_objetivo = get_object_or_404(Insumo, id=insumo_id) # Necesario para el contexto GET

    proveedores_fallback = []
    if not ofertas.exists():
        proveedores_fallback = Proveedor.objects.all().order_by('nombre')[:5]

    UMBRAL_STOCK_BAJO_INSUMOS = 15000
    context = {
        'insumo_objetivo': insumo_objetivo,
        'ofertas_proveedores': ofertas,
        'proveedores_fallback': proveedores_fallback,
        'titulo_seccion': f"Seleccionar Oferta para: {insumo_objetivo.descripcion}",
        'umbral_stock_bajo': UMBRAL_STOCK_BAJO_INSUMOS,
    }
    return render(request, 'compras/compras_seleccionar_proveedor.html', context)


def compras_crear_oc_view(request, insumo_id=None, proveedor_id=None): # Nombres de parámetros ajustados
    insumo_preseleccionado_obj = None
    proveedor_preseleccionado_obj = None
    oferta_seleccionada = None
    initial_data = {}
    logger.info(f"Entrando a compras_crear_oc_view con insumo_id={insumo_id}, proveedor_id={proveedor_id}")

    if insumo_id:
        insumo_preseleccionado_obj = get_object_or_404(Insumo, id=insumo_id)
        initial_data['insumo_principal'] = insumo_preseleccionado_obj
        logger.info(f"Insumo preseleccionado: {insumo_preseleccionado_obj.descripcion}")

        if proveedor_id:
            proveedor_preseleccionado_obj = get_object_or_404(Proveedor, id=proveedor_id)
            initial_data['proveedor'] = proveedor_preseleccionado_obj
            logger.info(f"Proveedor preseleccionado: {proveedor_preseleccionado_obj.nombre}")

            oferta_seleccionada = OfertaProveedor.objects.filter(
                insumo=insumo_preseleccionado_obj, 
                proveedor=proveedor_preseleccionado_obj
            ).first()
            
            if oferta_seleccionada:
                initial_data['precio_unitario_compra'] = oferta_seleccionada.precio_unitario_compra
                if oferta_seleccionada.tiempo_entrega_estimado_dias is not None:
                    try:
                        dias_entrega = int(oferta_seleccionada.tiempo_entrega_estimado_dias)
                        fecha_actual = timezone.now().date()
                        fecha_estimada = fecha_actual + timedelta(days=dias_entrega)
                        initial_data['fecha_estimada_entrega'] = fecha_estimada.strftime('%Y-%m-%d')
                        logger.info(f"Oferta: Precio {oferta_seleccionada.precio_unitario_compra}, Entrega {dias_entrega} días. Fecha est: {initial_data['fecha_estimada_entrega']}")
                    except ValueError:
                        logger.warning(f"Tiempo de entrega '{oferta_seleccionada.tiempo_entrega_estimado_dias}' no es válido.")
                else:
                    logger.info("Oferta encontrada, sin tiempo de entrega estimado.")
            else:
                logger.warning(f"No se encontró oferta para insumo {insumo_preseleccionado_obj.id} y proveedor {proveedor_preseleccionado_obj.id}.")
        
        elif insumo_preseleccionado_obj.ofertas_de_proveedores.exists(): # Si no se pasa proveedor, pero el insumo tiene ofertas
            primera_oferta = insumo_preseleccionado_obj.ofertas_de_proveedores.order_by('precio_unitario_compra').first()
            if primera_oferta:
                initial_data['proveedor'] = primera_oferta.proveedor
                initial_data['precio_unitario_compra'] = primera_oferta.precio_unitario_compra
                proveedor_preseleccionado_obj = primera_oferta.proveedor # Para el contexto
                # Podrías calcular fecha estimada de entrega aquí también si la primera_oferta tiene tiempo_entrega
        
        UMBRAL_STOCK_BAJO_INSUMOS = 15000 
        cantidad_necesaria = UMBRAL_STOCK_BAJO_INSUMOS - insumo_preseleccionado_obj.stock
        initial_data['cantidad_principal'] = max(10, cantidad_necesaria) # Sugerir comprar al menos 10 o lo necesario

    if request.method == 'POST':
        form = OrdenCompraForm(request.POST, insumo_para_ofertas=insumo_preseleccionado_obj)
        if form.is_valid():
            try:
                orden_compra = form.save(commit=False)
                orden_compra.tipo = 'compra' 
                orden_compra.estado = 'BORRADOR' 
                
                # Si el precio no vino del form pero había una oferta seleccionada (y se pasó el proveedor_id), usar el de la oferta
                # Esta lógica es más para cuando el campo precio es opcional en el form
                if not form.cleaned_data.get('precio_unitario_compra') and oferta_seleccionada: # oferta_seleccionada se define en el GET si hay proveedor_id
                    orden_compra.precio_unitario_compra = oferta_seleccionada.precio_unitario_compra
                
                # Si la fecha de entrega no vino del form pero se calculó una en el GET (si había oferta), usarla
                # Esto también es por si el campo es opcional en el form y el usuario no lo llena
                if not form.cleaned_data.get('fecha_estimada_entrega') and initial_data.get('fecha_estimada_entrega'):
                     orden_compra.fecha_estimada_entrega = initial_data.get('fecha_estimada_entrega')

                # El cálculo del total se hace en el save() del modelo Orden si los campos están
                orden_compra.save() # Guardar la OC para que tenga un ID y se pueda referenciar

                # --- ACTUALIZAR CANTIDAD EN PEDIDO DEL INSUMO ---
                if orden_compra.insumo_principal and orden_compra.cantidad_principal and orden_compra.cantidad_principal > 0:
                    insumo_obj_actualizar = orden_compra.insumo_principal # Obtener el objeto Insumo
                    # Actualización atómica
                    Insumo.objects.filter(id=insumo_obj_actualizar.id).update(
                        cantidad_en_pedido=F('cantidad_en_pedido') + orden_compra.cantidad_principal
                    )
                    logger.info(f"Incrementada cantidad_en_pedido para '{insumo_obj_actualizar.descripcion}' en {orden_compra.cantidad_principal} unidades.")
                # --- FIN ACTUALIZACIÓN CANTIDAD EN PEDIDO ---
                
                # Asegúrate de que get_estado_display() exista o usa get_estado_display_custom() si lo definiste.
                # Asumiré que el modelo Orden tiene el campo 'estado' con choices, por lo que get_estado_display() está disponible.
                messages.success(request, f"Orden de Compra '{orden_compra.numero_orden}' creada exitosamente en estado '{orden_compra.get_estado_display()}'. Total: ${orden_compra.total_orden_compra or 0:.2f}")
                return redirect('App_LUMINOVA:compras_lista_oc') 
            except DjangoIntegrityError as e_int:
                if 'UNIQUE constraint' in str(e_int) and ('numero_orden' in str(e_int) or 'numero_orden' in str(e_int).lower()): 
                    messages.error(request, f"Error: El número de orden de compra '{form.cleaned_data.get('numero_orden')}' ya existe.")
                else:
                    messages.error(request, f"Error de base de datos al guardar la OC: {e_int}")
            except Exception as e:
                messages.error(request, f"Error inesperado al crear la Orden de Compra: {e}")
                logger.exception("Error inesperado en compras_crear_oc_view POST:")
        else: # Formulario no es válido
            logger.warning(f"Formulario OC inválido: {form.errors.as_json()}")
            # Los errores del formulario se mostrarán automáticamente por django-bootstrap5
            # Pero necesitamos repopular el contexto con los objetos preseleccionados para el renderizado
            if insumo_id: # Si veníamos con un insumo preseleccionado
                initial_data['insumo_principal'] = insumo_preseleccionado_obj
            if proveedor_id: # Si veníamos con un proveedor preseleccionado
                initial_data['proveedor'] = proveedor_preseleccionado_obj
            # No es necesario pasar initial_data al form aquí porque el form ya se creó con request.POST
            # y los errores se asociarán a esa instancia.

    else: # GET request
        form = OrdenCompraForm(initial=initial_data, insumo_para_ofertas=insumo_preseleccionado_obj)

    context = {
        'form_oc': form, # Pasa el formulario (ya sea nuevo o con errores POST)
        'titulo_seccion': 'Crear Nueva Orden de Compra',
        'insumo_preseleccionado': insumo_preseleccionado_obj,
        'proveedor_preseleccionado': proveedor_preseleccionado_obj,
        'oferta_seleccionada': oferta_seleccionada # Podría ser None si no se encontró oferta
    }
    return render(request, 'compras/compras_crear_editar_oc.html', context)

# --- PRODUCCIÓN VIEWS ---
def proveedor_create_view(request):
    if not request.user.is_authenticated:
        return redirect('App_LUMINOVA:login')

    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, f'Proveedor {proveedor.nombre} creado exitosamente.')
            return redirect('App_LUMINOVA:proveedor_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label or field}: {error}")
    else:
        form = ProveedorForm()

    context = {
        'form': form,
        'titulo_seccion': 'Crear Proveedor',
    }
    return render(request, 'ventas/proveedores/proveedor_crear.html', context)

@login_required
def produccion_lista_op_view(request):
    ordenes_prod = OrdenProduccion.objects.select_related(
        'producto_a_producir__categoria',
        'orden_venta_origen__cliente', # Para obtener el cliente
        'estado_op', # Nombre del campo en tu modelo OP
        'sector_asignado_op'  # Nombre del campo en tu modelo OP
    ).order_by('-fecha_solicitud')

    context = {
        'ordenes_produccion_list': ordenes_prod,
        'titulo_seccion': 'Listado de Órdenes de Producción',
        'form_update_op': OrdenProduccionUpdateForm(), # Para el modal de edición
    }
    return render(request, 'produccion/produccion_lista_op.html', context)

@login_required
def planificacion_produccion_view(request):
    # if not es_admin_o_rol(request.user, ['produccion', 'administrador']):
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    # Obtener OPs que están pendientes de planificación (ej. estado 'Pendiente')
    estado_pendiente = EstadoOrden.objects.filter(nombre__iexact='Pendiente').first()
    ops_para_planificar = []
    if estado_pendiente:
        ops_para_planificar = OrdenProduccion.objects.filter(
            estado_op=estado_pendiente
        ).select_related('producto_a_producir', 'orden_venta_origen__cliente').order_by('fecha_solicitud')

    # Para los dropdowns en el formulario de cada OP
    sectores = SectorAsignado.objects.all().order_by('nombre')
    # Posibles estados a los que se puede pasar desde planificación
    estados_siguientes = EstadoOrden.objects.filter(nombre__in=['En Proceso', 'Pendiente']).order_by('nombre')


    if request.method == 'POST':
        op_id_a_actualizar = request.POST.get('op_id')
        op_a_actualizar = get_object_or_404(OrdenProduccion, id=op_id_a_actualizar)

        # Usar un formulario específico para la actualización desde la planificación si es necesario,
        # o campos individuales. Por simplicidad, usamos campos individuales aquí.

        sector_id = request.POST.get(f'sector_asignado_op_{op_id_a_actualizar}')
        estado_id = request.POST.get(f'estado_op_{op_id_a_actualizar}')
        fecha_inicio_p = request.POST.get(f'fecha_inicio_planificada_{op_id_a_actualizar}')
        fecha_fin_p = request.POST.get(f'fecha_fin_planificada_{op_id_a_actualizar}')

        if sector_id:
            op_a_actualizar.sector_asignado_op_id = sector_id
        if estado_id:
            op_a_actualizar.estado_op_id = estado_id
        if fecha_inicio_p:
            op_a_actualizar.fecha_inicio_planificada = fecha_inicio_p
        if fecha_fin_p:
            op_a_actualizar.fecha_fin_planificada = fecha_fin_p

        op_a_actualizar.save()
        messages.success(request, f"OP {op_a_actualizar.numero_op} actualizada.")
        return redirect('App_LUMINOVA:planificacion_produccion')


    context = {
        'ops_para_planificar_list': ops_para_planificar,
        'sectores_list': sectores,
        'estados_op_list': estados_siguientes,
        'titulo_seccion': 'Planificación de Órdenes de Producción',
    }
    return render(request, 'produccion/planificacion.html', context)

def solicitar_insumos_op_view(request, op_id):
    op = get_object_or_404(OrdenProduccion.objects.select_related('orden_venta_origen', 'estado_op'), id=op_id)

    # Validar que la OP esté en un estado desde el cual se pueden solicitar insumos (ej. Pendiente)
    # Asumimos que tienes un estado 'Pendiente'
    estado_actual_op_nombre = op.estado_op.nombre.lower() if op.estado_op else ""
    if estado_actual_op_nombre not in ['pendiente', 'planificada']: # Ajusta 'planificada' si tienes ese estado
        messages.error(request, f"La OP {op.numero_op} no está en un estado válido para solicitar insumos (actual: {op.estado_op.nombre if op.estado_op else 'N/A'}).")
        return redirect('App_LUMINOVA:produccion_detalle_op', op_id=op.id)

    try:
        estado_insumos_solicitados_op = EstadoOrden.objects.get(nombre__iexact="Insumos Solicitados")
        op.estado_op = estado_insumos_solicitados_op
        op.save(update_fields=['estado_op'])
        messages.success(request, f"Solicitud de insumos para OP {op.numero_op} enviada a Depósito.")

        # Actualizar estado de la OV
        if op.orden_venta_origen:
            orden_venta_asociada = op.orden_venta_origen
            # Solo cambiar a 'INSUMOS_SOLICITADOS' si la OV no está ya más avanzada o con problemas
            estados_ov_no_modificables = ['PRODUCCION_INICIADA', 'PRODUCCION_CON_PROBLEMAS', 'LISTA_ENTREGA', 'COMPLETADA', 'CANCELADA']
            if orden_venta_asociada.estado not in estados_ov_no_modificables:
                orden_venta_asociada.estado = 'INSUMOS_SOLICITADOS'
                orden_venta_asociada.save(update_fields=['estado'])
                messages.info(request, f"Estado de OV {orden_venta_asociada.numero_ov} actualizado a 'Insumos Solicitados'.")

    except EstadoOrden.DoesNotExist:
        messages.error(request, "Error crítico: El estado 'Insumos Solicitados' para OP no está configurado.")
    except Exception as e:
        messages.error(request, f"Error al solicitar insumos: {str(e)}")

    return redirect('App_LUMINOVA:produccion_detalle_op', op_id=op.id)


@login_required
@transaction.atomic # Buena práctica para asegurar la consistencia de los datos
def produccion_detalle_op_view(request, op_id):
    op = get_object_or_404(
        OrdenProduccion.objects.select_related(
            'producto_a_producir',
            'orden_venta_origen__cliente',
            'estado_op',
            'sector_asignado_op'
        ).prefetch_related('orden_venta_origen__ops_generadas__estado_op'),
        id=op_id
    )
    
    # ... (lógica de insumos y puede_solicitar_insumos sin cambios) ...
    insumos_necesarios_data = []
    todos_los_insumos_disponibles = True
    if op.producto_a_producir:
        componentes_requeridos = ComponenteProducto.objects.filter(
            producto_terminado=op.producto_a_producir
        ).select_related('insumo')
        if not componentes_requeridos.exists():
            todos_los_insumos_disponibles = False
        for comp in componentes_requeridos:
            cantidad_total_requerida_para_op = comp.cantidad_necesaria * op.cantidad_a_producir
            suficiente = comp.insumo.stock >= cantidad_total_requerida_para_op
            if not suficiente:
                todos_los_insumos_disponibles = False
            insumos_necesarios_data.append({
                'insumo_descripcion': comp.insumo.descripcion,
                'cantidad_por_unidad_pt': comp.cantidad_necesaria,
                'cantidad_total_requerida_op': cantidad_total_requerida_para_op,
                'stock_actual_insumo': comp.insumo.stock,
                'suficiente_stock': suficiente,
                'insumo_id': comp.insumo.id
            })
    else:
        todos_los_insumos_disponibles = False

    puede_solicitar_insumos = False
    if op.estado_op:
        estados_para_solicitar_insumos = ['pendiente', 'planificada'] 
        puede_solicitar_insumos = op.estado_op.nombre.lower() in estados_para_solicitar_insumos
    # --- FIN Lógica insumos ---

    mostrar_boton_reportar = False # Bandera para el botón de reporte

    if request.method == 'POST':
        form_update = OrdenProduccionUpdateForm(request.POST, instance=op)
        if form_update.is_valid():
            estado_op_anterior_obj = OrdenProduccion.objects.get(pk=op.pk).estado_op
            op_actualizada = form_update.save(commit=False)
            nuevo_estado_op_obj = op_actualizada.estado_op
            
            # --- Lógica de Stock PT (sin cambios, pero asegúrate que esté aquí) ---
            NOMBRE_ESTADO_OP_COMPLETADA = "Completada"
            se_esta_completando_op_ahora = False
            if nuevo_estado_op_obj and nuevo_estado_op_obj.nombre.lower() == NOMBRE_ESTADO_OP_COMPLETADA.lower():
                if not estado_op_anterior_obj or estado_op_anterior_obj.nombre.lower() != NOMBRE_ESTADO_OP_COMPLETADA.lower():
                    se_esta_completando_op_ahora = True
            if se_esta_completando_op_ahora:
                # ... (código de actualización de stock PT) ...
                producto_terminado_obj = op_actualizada.producto_a_producir
                cantidad_producida = op_actualizada.cantidad_a_producir
                if producto_terminado_obj and cantidad_producida > 0:
                    ProductoTerminado.objects.filter(id=producto_terminado_obj.id).update(stock=F('stock') + cantidad_producida)
                    stock_actualizado_pt = ProductoTerminado.objects.get(id=producto_terminado_obj.id).stock
                    messages.success(request, f"Stock de '{producto_terminado_obj.descripcion}' incrementado en {cantidad_producida}. Nuevo stock: {stock_actualizado_pt}.")
                    logger.info(f"OP {op_actualizada.numero_op} completada. Stock de PT ID {producto_terminado_obj.id} incrementado. Nuevo stock: {stock_actualizado_pt}")
                    if not op_actualizada.fecha_fin_real:
                         op_actualizada.fecha_fin_real = timezone.now()
                else:
                    logger.error(f"No se pudo actualizar stock para OP {op_actualizada.numero_op}: producto/cantidad inválidos.")
                    messages.error(request, "No se pudo actualizar el stock del producto: producto no asignado o cantidad cero.")

            op_actualizada.save()
            messages.success(request, f"Orden de Producción {op_actualizada.numero_op} actualizada a '{op_actualizada.get_estado_op_display()}'.")
            
            # --- Lógica de actualización de estado de OV ---
            if op_actualizada.orden_venta_origen:
                orden_venta_asociada = op_actualizada.orden_venta_origen
                ESTADO_OP_PAUSADA_LOWER = "pausada"
                ESTADO_OP_CANCELADA_LOWER = "cancelada"
                # ... (resto de tus constantes de estado OP y OV) ...
                ESTADO_OP_COMPLETADA_LOWER = NOMBRE_ESTADO_OP_COMPLETADA.lower()
                ESTADOS_OP_EN_FABRICACION_LOWER = ["producción iniciada", "en proceso"]
                ESTADO_OP_INSUMOS_SOLICITADOS_LOWER = "insumos solicitados"
                ESTADO_OP_PENDIENTE_LOWER = "pendiente"
                OV_ESTADO_PRODUCCION_CON_PROBLEMAS = 'PRODUCCION_CON_PROBLEMAS'
                OV_ESTADO_LISTA_ENTREGA = 'LISTA_ENTREGA'
                OV_ESTADO_PRODUCCION_INICIADA = 'PRODUCCION_INICIADA'
                OV_ESTADO_INSUMOS_SOLICITADOS = 'INSUMOS_SOLICITADOS'
                OV_ESTADO_CONFIRMADA = 'CONFIRMADA'

                nuevo_estado_ov_sugerido = orden_venta_asociada.estado
                ops_de_la_ov = OrdenProduccion.objects.filter(orden_venta_origen=orden_venta_asociada).select_related('estado_op')

                # La lógica principal de actualización de OV
                if not ops_de_la_ov.exists():
                    pass
                elif all(op_h.estado_op and op_h.estado_op.nombre.lower() == ESTADO_OP_COMPLETADA_LOWER for op_h in ops_de_la_ov):
                    nuevo_estado_ov_sugerido = OV_ESTADO_LISTA_ENTREGA
                elif any(op_h.estado_op and op_h.estado_op.nombre.lower() in [ESTADO_OP_CANCELADA_LOWER, ESTADO_OP_PAUSADA_LOWER] for op_h in ops_de_la_ov):
                    nuevo_estado_ov_sugerido = OV_ESTADO_PRODUCCION_CON_PROBLEMAS # <--- CLAVE AQUÍ
                elif any(op_h.estado_op and op_h.estado_op.nombre.lower() in ESTADOS_OP_EN_FABRICACION_LOWER for op_h in ops_de_la_ov):
                    nuevo_estado_ov_sugerido = OV_ESTADO_PRODUCCION_INICIADA
                elif any(op_h.estado_op and op_h.estado_op.nombre.lower() == ESTADO_OP_INSUMOS_SOLICITADOS_LOWER for op_h in ops_de_la_ov):
                    if not any(op_h.estado_op and op_h.estado_op.nombre.lower() in ESTADOS_OP_EN_FABRICACION_LOWER for op_h in ops_de_la_ov):
                        nuevo_estado_ov_sugerido = OV_ESTADO_INSUMOS_SOLICITADOS
                    else:
                        nuevo_estado_ov_sugerido = OV_ESTADO_PRODUCCION_INICIADA
                elif all(op_h.estado_op and op_h.estado_op.nombre.lower() == ESTADO_OP_PENDIENTE_LOWER for op_h in ops_de_la_ov):
                    nuevo_estado_ov_sugerido = OV_ESTADO_CONFIRMADA
                # ... (lógica de prevención de retroceso de estado OV) ...

                if orden_venta_asociada.estado != nuevo_estado_ov_sugerido:
                    valid_ov_states_keys = [choice[0] for choice in OrdenVenta.ESTADO_CHOICES]
                    if nuevo_estado_ov_sugerido in valid_ov_states_keys:
                        orden_venta_asociada.estado = nuevo_estado_ov_sugerido
                        orden_venta_asociada.save(update_fields=['estado'])
                        messages.info(request, f"Estado de OV {orden_venta_asociada.numero_ov} actualizado a '{orden_venta_asociada.get_estado_display()}'.")
            
            # Determinar si mostrar el botón de reporte DESPUÉS de guardar los cambios
            if op_actualizada.estado_op and op_actualizada.estado_op.nombre.lower() in ["pausada", "cancelada"]:
                mostrar_boton_reportar = True
            
            # No redirigir inmediatamente si queremos que el botón de reporte aparezca en la misma página
            # Si prefieres redirigir y que el botón esté siempre si el estado es pausado/cancelado, entonces redirige:
            # return redirect('App_LUMINOVA:produccion_detalle_op', op_id=op_actualizada.id)
            # Por ahora, no redirigimos para que el botón aparezca tras el POST.
        else:
            messages.error(request, "Error al actualizar la OP. Revise los datos del formulario.")
            logger.warning(f"Formulario OrdenProduccionUpdateForm inválido para OP {op.id}: {form_update.errors.as_json()}")
            # Si el form es inválido, también verificamos si el estado actual de la OP (antes del intento de POST)
            # justifica mostrar el botón de reporte.
            if op.estado_op and op.estado_op.nombre.lower() in ["pausada", "cancelada"]:
                mostrar_boton_reportar = True

    else: # GET request
        form_update = OrdenProduccionUpdateForm(instance=op)
        if op.estado_op and op.estado_op.nombre.lower() in ["pausada", "cancelada"]:
            mostrar_boton_reportar = True


    context = {
        'op': op,
        'insumos_necesarios_list': insumos_necesarios_data,
        'form_update_op': form_update, # Se pasa el form (con errores si es un POST fallido, o nuevo si es GET)
        'todos_los_insumos_disponibles_variable_de_contexto': todos_los_insumos_disponibles,
        'puede_solicitar_insumos': puede_solicitar_insumos,
        'mostrar_boton_reportar': mostrar_boton_reportar, # NUEVA VARIABLE DE CONTEXTO
        'titulo_seccion': f'Detalle OP: {op.numero_op}',
    }
    return render(request, 'produccion/produccion_detalle_op.html', context)

@login_required
def reportes_produccion_view(request):
    # if not es_admin_o_rol(request.user, ['produccion', 'administrador']):
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    lista_reportes = Reportes.objects.select_related(
        'orden_produccion_asociada',
        'reportado_por',
        'sector_reporta'
    ).order_by('-fecha')

    context = {
        'reportes_list': lista_reportes,
        'titulo_seccion': 'Reportes de Producción',
    }
    return render(request, 'produccion/reportes.html', context)

@login_required
@transaction.atomic
def crear_reporte_produccion_view(request, op_id):
    orden_produccion = get_object_or_404(OrdenProduccion, id=op_id)

    # Solo permitir reportar si la OP está en un estado problemático o según tu lógica
    # if not (orden_produccion.estado_op and orden_produccion.estado_op.nombre.lower() in ["pausada", "cancelada", "producción con problemas"]):
    #     messages.error(request, "Solo se pueden crear reportes para Órdenes de Producción en estados problemáticos.")
    #     return redirect('App_LUMINOVA:produccion_detalle_op', op_id=op_id)

    if request.method == 'POST':
        form = ReporteProduccionForm(request.POST, orden_produccion=orden_produccion)
        if form.is_valid():
            reporte = form.save(commit=False)
            reporte.orden_produccion_asociada = orden_produccion
            reporte.reportado_por = request.user
            reporte.fecha = timezone.now()
            
            # Generar n_reporte único
            rp_count = Reportes.objects.count()
            next_rp_number = f"RP-{str(rp_count + 1).zfill(5)}"
            while Reportes.objects.filter(n_reporte=next_rp_number).exists():
                rp_count += 1
                next_rp_number = f"RP-{str(rp_count + 1).zfill(5)}"
            reporte.n_reporte = next_rp_number
            
            reporte.save()
            messages.success(request, f"Reporte '{reporte.n_reporte}' creado exitosamente para la OP {orden_produccion.numero_op}.")
            return redirect('App_LUMINOVA:reportes_produccion') # Ir a la lista de todos los reportes
        else:
            messages.error(request, "Por favor, corrija los errores en el formulario de reporte.")
    else: # GET
        # Pasar la OP al form para preseleccionar el sector si es posible
        form = ReporteProduccionForm(orden_produccion=orden_produccion)

    context = {
        'form_reporte': form,
        'orden_produccion': orden_produccion,
        'titulo_seccion': f'Crear Reporte para OP: {orden_produccion.numero_op}'
    }
    return render(request, 'produccion/crear_reporte.html', context)

# --- DEPÓSITO VIEWS ---
@login_required
@transaction.atomic
def deposito_enviar_insumos_op_view(request, op_id):
    op = get_object_or_404(
        OrdenProduccion.objects.select_related(
            'orden_venta_origen', 
            'producto_a_producir' # Necesario para los componentes
        ), 
        id=op_id
    )
    logger.info(f"Procesando envío de insumos para OP: {op.numero_op} (Estado actual: {op.estado_op.nombre if op.estado_op else 'N/A'})")

    if request.method == 'POST':
        # Solo permitir esta acción si la OP está en "Insumos Solicitados"
        if not op.estado_op or op.estado_op.nombre.lower() != "insumos solicitados":
            messages.error(request, f"La OP {op.numero_op} no está en estado 'Insumos Solicitados'. No se pueden enviar insumos.")
            return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

        insumos_descontados_correctamente = True
        errores_stock = []
        
        if not op.producto_a_producir:
            messages.error(request, f"Error crítico: La OP {op.numero_op} no tiene un producto asignado.")
            return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

        componentes_requeridos = ComponenteProducto.objects.filter(
            producto_terminado=op.producto_a_producir
        ).select_related('insumo')

        if not componentes_requeridos.exists():
            messages.error(request, f"No se puede procesar: No hay BOM definido para el producto '{op.producto_a_producir.descripcion}'.")
            logger.error(f"BOM no definido para producto {op.producto_a_producir.id} en OP {op.numero_op}")
            return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

        for comp in componentes_requeridos:
            cantidad_a_descontar = comp.cantidad_necesaria * op.cantidad_a_producir
            try:
                # Bloquear la fila del insumo para evitar condiciones de carrera (si tu DB lo soporta bien)
                # insumo_a_actualizar = Insumo.objects.select_for_update().get(id=comp.insumo.id)
                insumo_a_actualizar = Insumo.objects.get(id=comp.insumo.id) # Versión más simple

                if insumo_a_actualizar.stock >= cantidad_a_descontar:
                    # Usar F() expression para una actualización atómica es preferible
                    Insumo.objects.filter(id=insumo_a_actualizar.id).update(stock=F('stock') - cantidad_a_descontar)
                    logger.info(f"Stock de '{insumo_a_actualizar.descripcion}' (ID: {insumo_a_actualizar.id}) descontado en {cantidad_a_descontar}.")
                else:
                    errores_stock.append(f"Stock insuficiente para '{insumo_a_actualizar.descripcion}'. Requeridos: {cantidad_a_descontar}, Disponible: {insumo_a_actualizar.stock}")
                    insumos_descontados_correctamente = False
                    # Aquí podrías decidir si continuar verificando otros insumos o hacer break.
                    # Si haces break, solo se reportará el primer error de stock.
            except Insumo.DoesNotExist:
                errores_stock.append(f"Insumo '{comp.insumo.descripcion}' (ID: {comp.insumo.id}) no encontrado durante el descuento. Error de datos.")
                insumos_descontados_correctamente = False
                break # Error crítico, no continuar si un insumo del BOM no existe
        
        if errores_stock: # Si hubo algún error de stock
            for error_msg in errores_stock:
                messages.error(request, error_msg)
            # No es necesario reasignar insumos_descontados_correctamente = False aquí, ya se hizo.
        
        if insumos_descontados_correctamente:
            try:
                # Estado al que pasa la OP DESPUÉS de que Depósito envía los insumos
                nombre_estado_op_post_deposito = "Insumos Recibidos" # ESTE ES EL NUEVO ESTADO OBJETIVO
                
                estado_siguiente_op_obj = EstadoOrden.objects.get(nombre__iexact=nombre_estado_op_post_deposito)
                
                op.estado_op = estado_siguiente_op_obj
                # Considera si fecha_inicio_real se debe setear aquí o cuando producción realmente empieza.
                # Si es cuando depósito entrega, está bien.
                if not op.fecha_inicio_real: # O un nuevo campo como 'fecha_insumos_entregados'
                    op.fecha_inicio_real = timezone.now() 
                op.save(update_fields=['estado_op', 'fecha_inicio_real'])
                
                messages.success(request, f"Insumos para OP {op.numero_op} marcados como enviados/recibidos. OP ahora en estado '{estado_siguiente_op_obj.nombre}'.")
                logger.info(f"OP {op.numero_op} actualizada a estado '{estado_siguiente_op_obj.nombre}' por Depósito.")

                # La OV podría seguir en "INSUMOS_SOLICITADOS" o pasar a un estado intermedio si lo tienes.
                # La transición a "PRODUCCION_INICIADA" para la OV debería ocurrir cuando Producción
                # explícitamente inicia la OP (cambiándola de "Insumos Recibidos" a "Producción Iniciada").
                # No hay cambio directo de estado de OV aquí, se deja a la lógica de produccion_detalle_op_view.

            except EstadoOrden.DoesNotExist:
                 messages.error(request, f"Error de Configuración: El estado de OP '{nombre_estado_op_post_deposito}' no fue encontrado. Insumos descontados, pero el estado de la OP no se actualizó correctamente. Por favor, cree este estado en el panel de administración.")
                 logger.error(f"CRÍTICO: Estado OP '{nombre_estado_op_post_deposito}' no encontrado. OP {op.numero_op} podría quedar en estado incorrecto.")
            return redirect('App_LUMINOVA:deposito_solicitudes_insumos') # Vuelve a la lista de solicitudes pendientes
        else: # Hubo errores de stock
            logger.warning(f"Errores de stock al procesar OP {op.numero_op}. Redirigiendo a detalle de solicitud.")
            return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

    # Si es GET
    messages.info(request, "Esta acción de enviar insumos debe realizarse mediante POST desde la página de detalle de la solicitud.")
    return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

@login_required
def deposito_solicitudes_insumos_view(request):
    ops_pendientes_preparacion = OrdenProduccion.objects.none() 
    ops_con_insumos_enviados = OrdenProduccion.objects.none()   
    
    titulo_seccion = 'Gestión de Insumos para Producción' # Correcto
    logger.info("--- Entrando a deposito_solicitudes_insumos_view ---") # Log de entrada

    try:
        # 1. OBTENER OPs QUE ESTÁN SOLICITANDO INSUMOS
        estado_insumos_solicitados_obj = EstadoOrden.objects.filter(nombre__iexact='Insumos Solicitados').first() # Renombrado para claridad
        
        if estado_insumos_solicitados_obj:
            logger.info(f"Estado 'Insumos Solicitados' encontrado (ID: {estado_insumos_solicitados_obj.id}, Nombre: '{estado_insumos_solicitados_obj.nombre}').")
            ops_pendientes_preparacion = OrdenProduccion.objects.filter(
                estado_op=estado_insumos_solicitados_obj # Usar el objeto encontrado
            ).select_related(
                'producto_a_producir', 'estado_op', 'orden_venta_origen__cliente'
            ).order_by('fecha_solicitud')
            logger.info(f"Encontradas {ops_pendientes_preparacion.count()} OPs pendientes de preparación.")
        else:
            messages.error(request, "Configuración crítica: El estado 'Insumos Solicitados' no existe en la base de datos. No se pueden mostrar las solicitudes pendientes.")
            logger.error("CRÍTICO: Estado 'Insumos Solicitados' no encontrado en deposito_solicitudes_insumos_view.")

        # 2. OBTENER OPs A LAS QUE YA SE LES ENVIARON INSUMOS (AHORA EN ESTADO "En Proceso")
        estado_en_proceso_nombre_buscado = "En Proceso" 
        estado_en_proceso_obj = EstadoOrden.objects.filter(nombre__iexact=estado_en_proceso_nombre_buscado).first() # Renombrado

        if estado_en_proceso_obj:
            logger.info(f"Estado '{estado_en_proceso_nombre_buscado}' encontrado (ID: {estado_en_proceso_obj.id}, Nombre: '{estado_en_proceso_obj.nombre}').")
            ops_con_insumos_enviados = OrdenProduccion.objects.filter(
                estado_op=estado_en_proceso_obj # Usar el objeto encontrado
            ).select_related(
                'producto_a_producir', 'estado_op', 'orden_venta_origen__cliente'
            ).order_by('-fecha_inicio_real', '-fecha_solicitud') 
            logger.info(f"Encontradas {ops_con_insumos_enviados.count()} OPs con insumos ya enviados/en proceso.")
        else:
            messages.warning(request, f"Advertencia de configuración: El estado '{estado_en_proceso_nombre_buscado}' no existe. No se mostrará la lista de OPs con insumos enviados.")
            logger.warning(f"Configuración: Estado '{estado_en_proceso_nombre_buscado}' no encontrado en deposito_solicitudes_insumos_view.")
            
    except Exception as e: # Captura más genérica para cualquier otro error inesperado
        messages.error(request, f"Ocurrió un error inesperado al cargar las solicitudes de insumos: {e}")
        logger.exception("Excepción inesperada en deposito_solicitudes_insumos_view:")
        # ops_pendientes_preparacion y ops_con_insumos_enviados ya están como QuerySet vacíos.

    context = {
        'ops_pendientes_list': ops_pendientes_preparacion,
        'ops_enviadas_list': ops_con_insumos_enviados,
        'titulo_seccion': titulo_seccion,
    }
    logger.info(f"Contexto para deposito_solicitudes_insumos.html: ops_pendientes_list count = {ops_pendientes_preparacion.count()}, ops_enviadas_list count = {ops_con_insumos_enviados.count()}")
    return render(request, 'deposito/deposito_solicitudes_insumos.html', context)

@login_required
def deposito_view(request):
    logger.info("--- deposito_view: INICIO ---")
    
    categorias_I = CategoriaInsumo.objects.all()
    categorias_PT = CategoriaProductoTerminado.objects.all()
    
    ops_pendientes_deposito_list = OrdenProduccion.objects.none()
    ops_pendientes_deposito_count = 0
    try:
        estado_sol = EstadoOrden.objects.filter(nombre__iexact='Insumos Solicitados').first()
        if estado_sol:
            ops_pendientes_deposito_list = OrdenProduccion.objects.filter(
                estado_op=estado_sol
            ).select_related('producto_a_producir').order_by('fecha_solicitud')
            ops_pendientes_deposito_count = ops_pendientes_deposito_list.count()
            logger.info(f"Deposito_view (OPs): Encontradas {ops_pendientes_deposito_count} OPs pendientes (estado: '{estado_sol.nombre}').")
        else:
            # Este mensaje solo se muestra si el estado "Insumos Solicitados" NO EXISTE.
            # Si existe pero no hay OPs en ese estado, ops_pendientes_deposito_count será 0, lo cual es correcto.
            messages.warning(request, "Configuración: El estado 'Insumos Solicitados' para OP no se encontró en la base de datos. La lista de OPs pendientes no se poblará.")
            logger.warning("Deposito_view (OPs): Estado 'Insumos Solicitados' NO encontrado.")
    except Exception as e_op: # Captura de excepción más genérica
        messages.error(request, f"Error al cargar OPs pendientes para depósito: {e_op}")
        logger.error(f"Deposito_view (OPs): Excepción al cargar OPs: {e_op}")

    productos_terminados_con_stock = ProductoTerminado.objects.filter(stock__gt=0).order_by('-stock', 'descripcion')
    logger.info(f"Deposito_view (PTs): Productos terminados con stock > 0 encontrados: {productos_terminados_con_stock.count()}")

    # --- LÓGICA PARA INSUMOS CON STOCK BAJO ---
    UMBRAL_STOCK_BAJO_INSUMOS = 15000 
    insumos_con_stock_bajo = Insumo.objects.filter(stock__lt=UMBRAL_STOCK_BAJO_INSUMOS).order_by('stock', 'descripcion')
    
    logger.info(f"Deposito_view: Insumos con stock bajo (<{UMBRAL_STOCK_BAJO_INSUMOS}) encontrados: {insumos_con_stock_bajo.count()}")
    if insumos_con_stock_bajo.exists():
        for ins_debug in insumos_con_stock_bajo:
            logger.info(f"  -> Insumo bajo stock: {ins_debug.descripcion}, Stock: {ins_debug.stock}, ID: {ins_debug.id}")
    else:
        logger.info("  -> No se encontraron insumos con stock por debajo del umbral.")
    # --- FIN LÓGICA STOCK BAJO ---

    context = {
        'categorias_I': categorias_I,
        'categorias_PT': categorias_PT,
        'ops_pendientes_deposito_list': ops_pendientes_deposito_list,
        'ops_pendientes_deposito_count': ops_pendientes_deposito_count,
        'productos_terminados_en_stock_list': productos_terminados_con_stock,
        'insumos_con_stock_bajo_list': insumos_con_stock_bajo, # Esta es la lista clave
        'umbral_stock_bajo': UMBRAL_STOCK_BAJO_INSUMOS, 
    }
    
    logger.info(f"Deposito_view: Contexto final - pt_stock_count={productos_terminados_con_stock.count()}, insumos_bajos_count={insumos_con_stock_bajo.count()}")
    return render(request, 'deposito/deposito.html', context)


@login_required
def deposito_solicitudes_insumos_view(request):
    # if not es_admin_o_rol(request.user, ['deposito', 'administrador']): # Control de permisos
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    ops_necesitan_insumos = OrdenProduccion.objects.none() # Inicializar con un queryset vacío

    try:
        estado_objetivo = EstadoOrden.objects.get(nombre__iexact='Insumos Solicitados')
        ops_necesitan_insumos = OrdenProduccion.objects.filter( # ASIGNACIÓN AQUÍ (Camino A)
            estado_op=estado_objetivo
        ).select_related('producto_a_producir', 'estado_op', 'orden_venta_origen__cliente').order_by('fecha_solicitud')

    except EstadoOrden.DoesNotExist:
        messages.error(request, "Error: El estado 'Insumos Solicitados' no está configurado para las Órdenes de Producción. No se pueden listar las solicitudes.")
        # ops_necesitan_insumos ya es un queryset vacío, así que está bien.
        # O podrías decidir mostrar un error más prominente o redirigir.
        # Para mantener la funcionalidad de la plantilla, dejaremos ops_necesitan_insumos como un queryset vacío.

    context = {
        'ops_necesitan_insumos_list': ops_necesitan_insumos,
        'titulo_seccion': 'Solicitudes de Insumos desde Producción'
    }
    return render(request, 'deposito/deposito_solicitudes_insumos.html', context)


@login_required
def deposito_detalle_solicitud_op_view(request, op_id):
    """
    Muestra el detalle de una OP desde la perspectiva del depósito,
    listando los insumos necesarios, su stock y si son suficientes.
    Permite confirmar el envío/descuento de insumos.
    """
    # if not es_admin_o_rol(request.user, ['deposito', 'administrador']): # Control de permisos
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    op = get_object_or_404(OrdenProduccion.objects.select_related('producto_a_producir', 'estado_op'), id=op_id)
    insumos_necesarios_data = []
    todos_los_insumos_disponibles = True # Asumir que sí hasta que se demuestre lo contrario

    if op.producto_a_producir:
        componentes_requeridos = ComponenteProducto.objects.filter(
            producto_terminado=op.producto_a_producir
        ).select_related('insumo')

        if not componentes_requeridos.exists():
            messages.warning(request, f"No se ha definido el BOM (lista de componentes) para el producto '{op.producto_a_producir.descripcion}'. No se pueden determinar los insumos.")
            todos_los_insumos_disponibles = False # No se puede proceder

        for comp in componentes_requeridos:
            cantidad_total_req = comp.cantidad_necesaria * op.cantidad_a_producir
            suficiente = comp.insumo.stock >= cantidad_total_req
            if not suficiente:
                todos_los_insumos_disponibles = False
            insumos_necesarios_data.append({
                'insumo_id': comp.insumo.id,
                'insumo_descripcion': comp.insumo.descripcion,
                'cantidad_total_requerida_op': cantidad_total_req,
                'stock_actual_insumo': comp.insumo.stock,
                'suficiente_stock': suficiente
            })

    context = {
        'op': op,
        'insumos_necesarios_list': insumos_necesarios_data,
        'todos_los_insumos_disponibles': todos_los_insumos_disponibles, # Para habilitar/deshabilitar botón
        'titulo_seccion': f'Detalle Solicitud Insumos para OP: {op.numero_op}'
    }
    return render(request, 'deposito/deposito_detalle_solicitud_op.html', context)

# --- CLASS-BASED VIEWS (CRUDs) ---
class Categoria_IListView(ListView):
    model = CategoriaInsumo
    template_name = 'deposito/deposito_view.html'
    context_object_name = 'categorias_I' # Para diferenciar en el template deposito.html

class Categoria_IDetailView(DetailView):
    model = CategoriaInsumo
    template_name = 'deposito/categoria_insumo_detail.html'
    context_object_name = 'categoria_I'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['insumos_de_categoria'] = Insumo.objects.filter(categoria=self.object)
        return context

class Categoria_ICreateView(CreateView):
    model = CategoriaInsumo
    template_name = 'deposito/categoria_insumo_crear.html'
    fields = ('nombre', 'imagen')
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')


class Categoria_IUpdateView(UpdateView):
    model = CategoriaInsumo
    template_name = 'deposito/categoria_insumo_editar.html'
    fields = ('nombre', 'imagen')
    context_object_name = 'categoria'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class Categoria_IDeleteView(DeleteView):
    model = CategoriaInsumo
    template_name = 'deposito/categoria_insumo_confirm_delete.html'
    context_object_name = 'categoria'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')


# --- CRUD Categorias Producto Terminado ---
class Categoria_PTListView(ListView):
    model = CategoriaProductoTerminado
    template_name = 'deposito/deposito.html'
    context_object_name = 'categorias_PT'

class Categoria_PTDetailView(DetailView):
    model = CategoriaProductoTerminado
    template_name = 'deposito/categoria_producto_terminado_detail.html'
    context_object_name = 'categoria_PT'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['productos_de_categoria'] = ProductoTerminado.objects.filter(categoria=self.object)
        return context

class Categoria_PTCreateView(CreateView):
    model = CategoriaProductoTerminado
    template_name = 'deposito/categoria_producto_terminado_crear.html'
    fields = ('nombre', 'imagen')
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class Categoria_PTUpdateView(UpdateView):
    model = CategoriaProductoTerminado
    template_name = 'deposito/categoria_producto_terminado_editar.html'
    fields = ('nombre', 'imagen')
    context_object_name = 'categoria'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class Categoria_PTDeleteView(DeleteView):
    model = CategoriaProductoTerminado
    template_name = 'deposito/categoria_producto_terminado_confirm_delete.html'
    context_object_name = 'categoria'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')


# Funciones para el CRUD de Insumos
class InsumosListView(ListView):
    model = Insumo
    template_name = 'deposito/insumos_list.html' # Para una vista de todos los insumos si es necesaria
    context_object_name = 'insumos'

class InsumoDetailView(DetailView):
    model = Insumo
    template_name = 'deposito/insumo_detail.html'
    context_object_name = 'insumo'

class InsumoCreateView(CreateView):
    model = Insumo
    template_name = 'deposito/insumo_crear.html'
    fields = '__all__'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')


class InsumoUpdateView(UpdateView):
    model = Insumo
    template_name = 'deposito/insumo_editar.html' # Asegúrate que sea el nombre correcto de tu plantilla
    fields = ['descripcion', 'categoria', 'fabricante', 'stock', 'imagen'] # Lista los campos que quieres que sean editables
    # O usa un formulario personalizado:
    # form_class = InsumoForm 
    context_object_name = 'insumo' # Nombre del objeto en la plantilla (puedes usar 'object' también)

    def get_success_url(self):
        # Redirigir al detalle de la categoría del insumo editado, o a donde prefieras
        messages.success(self.request, f"Insumo '{self.object.descripcion}' actualizado exitosamente.")
        if hasattr(self.object, 'categoria') and self.object.categoria:
            return reverse_lazy('App_LUMINOVA:categoria_i_detail', kwargs={'pk': self.object.categoria.pk})
        return reverse_lazy('App_LUMINOVA:deposito_view') # Fallback

    def form_valid(self, form):
        logger.info(f"InsumoUpdateView: Formulario válido para insumo ID {self.object.id}. Guardando cambios.")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.warning(f"InsumoUpdateView: Formulario inválido para insumo ID {self.object.id if self.object else 'Nuevo'}. Errores: {form.errors.as_json()}")
        messages.error(self.request, "Hubo errores al intentar guardar el insumo. Por favor, revise los campos.")
        return super().form_invalid(form)

class InsumoDeleteView(DeleteView):
    model = Insumo
    template_name = 'deposito/insumo_confirm_delete.html'
    context_object_name = 'insumo'
    # success_url = reverse_lazy('App_LUMINOVA:deposito_view') # success_url se maneja en get_success_url

    def get_success_url(self):
        # Redirigir al detalle de la categoría del insumo eliminado, o a la vista principal de depósito
        if hasattr(self.object, 'categoria') and self.object.categoria: # self.object es el insumo borrado
            return reverse_lazy('App_LUMINOVA:categoria_i_detail', kwargs={'pk': self.object.categoria.pk})
        return reverse_lazy('App_LUMINOVA:deposito_view')

    def form_valid(self, form):
        # Este método se llama DESPUÉS de que la eliminación fue exitosa (si no hay ProtectedError)
        # Aquí se guarda el nombre para usarlo en el mensaje ANTES de que self.object se elimine completamente.
        insumo_descripcion = self.object.descripcion
        response = super().form_valid(form)
        messages.success(self.request, f"El insumo '{insumo_descripcion}' ha sido eliminado exitosamente.")
        return response

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() # Cargar el objeto para tener acceso a él en caso de error
        try:
            # Intenta llamar al método delete de la clase base, que es lo que realmente borra
            # y donde se podría lanzar ProtectedError.
            # Si la eliminación es exitosa, se llamará a form_valid y luego a get_success_url.
            return super().delete(request, *args, **kwargs)
        except ProtectedError as e:
            # Construir un mensaje más detallado sobre qué está protegiendo la eliminación
            protecting_objects = []
            if hasattr(e, 'protected_objects'): # e.protected_objects contiene los objetos que causan la protección
                for obj in e.protected_objects:
                    if isinstance(obj, ComponenteProducto):
                        protecting_objects.append(f"el producto terminado '{obj.producto_terminado.descripcion}' (usa {obj.cantidad_necesaria} unidades)")
                    else:
                        protecting_objects.append(str(obj)) # Representación genérica

            error_message = (
                f"No se puede eliminar el insumo '{self.object.descripcion}' porque está referenciado y protegido."
            )
            if protecting_objects:
                error_message += " Específicamente, es usado por: " + ", ".join(protecting_objects) + "."
            error_message += " Por favor, primero elimine o modifique estas referencias."

            messages.error(request, error_message)
            # Redirigir de vuelta a la página de confirmación de borrado o a una página relevante
            # Podrías redirigir al detalle del insumo o a la lista donde el usuario pueda ver el error
            # o incluso a la página desde donde vino.
            # Para simplificar, redirigimos a donde iría si la eliminación fuera exitosa (ej. la categoría o depósito)
            # para que vea el mensaje de error allí.
            if hasattr(self.object, 'categoria') and self.object.categoria:
                 return redirect(reverse_lazy('App_LUMINOVA:categoria_i_detail', kwargs={'pk': self.object.categoria.pk}))
            return redirect(reverse_lazy('App_LUMINOVA:deposito_view'))


# Funciones para el CRUD de Productos Terminados
class ProductoTerminadosListView(ListView):
    model = ProductoTerminado
    template_name = 'deposito/productoterminados_list.html' # Para una vista de todos los PT si es necesaria
    context_object_name = 'productos_terminados'

class ProductoTerminadoDetailView(DetailView):
    model = ProductoTerminado
    template_name = 'deposito/productoterminado_detail.html'
    context_object_name = 'producto_terminado'

class ProductoTerminadoCreateView(CreateView):
    model = ProductoTerminado
    template_name = 'deposito/productoterminado_crear.html'
    fields = '__all__'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class ProductoTerminadoUpdateView(UpdateView):
    model = ProductoTerminado
    template_name = 'deposito/productoterminado_editar.html'
    fields = '__all__'
    context_object_name = 'producto_terminado'

    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class ProductoTerminadoDeleteView(DeleteView):
    model = ProductoTerminado
    template_name = 'deposito/productoterminado_confirm_delete.html'
    context_object_name = 'producto_terminado'
    # success_url = reverse_lazy('App_LUMINOVA:deposito_view') # Se manejará con get_success_url

    def get_success_url(self):
        # Redirigir al detalle de la categoría del producto, o a la vista principal de depósito
        if hasattr(self.object, 'categoria') and self.object.categoria:
            return reverse_lazy('App_LUMINOVA:categoria_pt_detail', kwargs={'pk': self.object.categoria.pk})
        return reverse_lazy('App_LUMINOVA:deposito_view')

    def form_valid(self, form):
        # Guardar descripción para el mensaje antes de borrar
        producto_descripcion = self.object.descripcion
        response = super().form_valid(form)
        messages.success(self.request, f"El producto terminado '{producto_descripcion}' ha sido eliminado exitosamente.")
        return response

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() # Cargar el objeto para tener acceso a él en caso de error
        try:
            return super().delete(request, *args, **kwargs)
        except ProtectedError as e:
            protecting_objects_details = []
            if hasattr(e, 'protected_objects'):
                for obj in e.protected_objects:
                    if isinstance(obj, ItemOrdenVenta):
                        protecting_objects_details.append(f"la Orden de Venta N° {obj.orden_venta.numero_ov}")
                    elif isinstance(obj, OrdenProduccion):
                        protecting_objects_details.append(f"la Orden de Producción N° {obj.numero_op}")
                    # Añade más 'elif isinstance' si ProductoTerminado es FK en otros modelos con PROTECT
                    else:
                        protecting_objects_details.append(f"un registro del tipo '{obj.__class__.__name__}'")

            error_message = (
                f"No se puede eliminar el producto terminado '{self.object.descripcion}' porque está referenciado y protegido."
            )
            if protecting_objects_details:
                error_message += " Específicamente, es usado por: " + ", ".join(protecting_objects_details) + "."
            error_message += " Por favor, primero elimine o modifique estas referencias."

            messages.error(request, error_message)
            # Redirigir de vuelta a una página relevante donde se muestre el mensaje
            if hasattr(self.object, 'categoria') and self.object.categoria:
                 return redirect(reverse_lazy('App_LUMINOVA:categoria_pt_detail', kwargs={'pk': self.object.categoria.pk}))
            return redirect(reverse_lazy('App_LUMINOVA:deposito_view'))


class ProveedorListView(ListView):
    model = Proveedor
    template_name = 'ventas/proveedores/proveedor_list.html'
    context_object_name = 'proveedores'

class ProveedorDetailView(DetailView):
    model = Proveedor
    template_name = 'ventas/proveedores/proveedor_detail.html'
    context_object_name = 'proveedor'

class ProveedorUpdateView(UpdateView):
    model = Proveedor
    template_name = 'ventas/proveedores/proveedor_editar.html'
    fields = '__all__'
    context_object_name = 'proveedor'
    success_url = reverse_lazy('App_LUMINOVA:proveedor_list')

class ProveedorDeleteView(DeleteView):
    model = Proveedor
    template_name = 'ventas/proveedores/proveedor_confirm_delete.html'
    context_object_name = 'proveedor'
    success_url = reverse_lazy('App_LUMINOVA:proveedor_list')


class FabricanteListView(ListView):
    model = Fabricante
    template_name = 'ventas/fabricantes/fabricante_list.html'
    context_object_name = 'fabricantes'

class FabricanteDetailView(DetailView):
    model = Fabricante
    template_name = 'ventas/fabricantes/fabricante_detail.html'
    context_object_name = 'fabricante'

class FabricanteCreateView(CreateView):
    model = Fabricante
    template_name = 'ventas/fabricantes/fabricante_crear.html'
    fields = '__all__'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class FabricanteUpdateView(UpdateView):
    model = Fabricante
    template_name = 'ventas/fabricantes/fabricante_editar.html'
    fields = '__all__'
    context_object_name = 'fabricante'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class FabricanteDeleteView(DeleteView):
    model = Fabricante
    template_name = 'ventas/fabricantes/fabricante_confirm_delete.html'
    context_object_name = 'fabricante'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')
    
# --- PDF VIEW ---
@login_required
def ventas_ver_factura_pdf_view(request, factura_id):
    # Obtener la factura y pre-cargar los datos necesarios de forma eficiente
    try:
        factura = Factura.objects.select_related(
            'orden_venta__cliente' # Para el cliente de la orden de venta
        ).prefetch_related(
            # Prefetch para los ítems de la orden de venta y sus productos terminados
            Prefetch('orden_venta__items_ov', queryset=ItemOrdenVenta.objects.select_related('producto_terminado'))
        ).get(id=factura_id)
    except Factura.DoesNotExist:
        messages.error(request, "La factura solicitada no existe.")
        return redirect('App_LUMINOVA:ventas_lista_ov') # O a donde sea apropiado

    orden_venta = factura.orden_venta # Acceder a la orden de venta asociada

    # Crear la respuesta HTTP con el tipo de contenido PDF.
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="factura_{factura.numero_factura}.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    # ... (resto de tu código de generación de PDF como lo tenías) ...

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
    p.drawString(width - 3 * inch, height - 1.5 * inch, f"Fecha Emisión: {factura.fecha_emision.strftime('%d/%m/%Y')}")
    p.drawString(width - 3 * inch, height - 1.65 * inch, f"OV N°: {orden_venta.numero_ov}")

    # ... (Datos del Cliente, usando factura.orden_venta.cliente) ...
    p.setFont("Helvetica-Bold", 12)
    p.drawString(1 * inch, height - 2.5 * inch, "Cliente:")
    p.setFont("Helvetica", 10)
    p.drawString(1 * inch, height - 2.7 * inch, orden_venta.cliente.nombre)
    # ... (más datos del cliente) ...

    p.line(1 * inch, height - 3.5 * inch, width - 1 * inch, height - 3.5 * inch)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(1 * inch, height - 3.8 * inch, "Detalle de Productos/Servicios:")

    data = [['Cant.', 'Descripción', 'P. Unit.', 'Subtotal']] # Encabezados de la tabla
    
    # Lógica para determinar qué ítems de la OV se incluyen en la factura
    # (basado en si sus OPs asociadas fueron completadas, o si eran de stock)
    ops_asociadas_a_ov = orden_venta.ops_generadas.all() # Obtener todas las OPs de la OV
    productos_completados_en_ops_ids = {
        op.producto_a_producir_id 
        for op in ops_asociadas_a_ov 
        if op.estado_op and op.estado_op.nombre.lower() == "completada"
    }

    total_factura_recalculado_para_pdf = 0 # Para verificar o usar si es necesario

    for item in orden_venta.items_ov.all(): # Iterar sobre los items pre-cargados
        facturar_este_item = False
        if not ops_asociadas_a_ov.exists(): # Si la OV no generó OPs (todo era de stock)
            facturar_este_item = True
        elif item.producto_terminado_id in productos_completados_en_ops_ids: # Si la OP del producto se completó
            facturar_este_item = True
        
        # Podrías añadir una condición adicional: si la OV está en 'LISTA_ENTREGA' o 'COMPLETADA'
        # y un item no tuvo OP (asumiendo que era de stock), también facturarlo.
        elif not ops_asociadas_a_ov.filter(producto_a_producir=item.producto_terminado).exists() and \
             orden_venta.estado in ['LISTA_ENTREGA', 'COMPLETADA']:
            facturar_este_item = True


        if facturar_este_item:
            data.append([
                str(item.cantidad),
                Paragraph(item.producto_terminado.descripcion, style_normal),
                f"${item.precio_unitario_venta:.2f}",
                f"${item.subtotal:.2f}"
            ])
            total_factura_recalculado_para_pdf += item.subtotal
    
    # Es mejor usar el factura.total_facturado que ya fue calculado y guardado
    # a menos que quieras que el PDF siempre recalcule.
    # total_a_mostrar = factura.total_facturado 
    total_a_mostrar = total_factura_recalculado_para_pdf # O usa este si quieres que el PDF siempre refleje los items listados

    y_position = height - 4.2 * inch
    if len(data) > 1: # Si hay ítems
        table = Table(data, colWidths=[0.5*inch, 4.5*inch, 1*inch, 1*inch]) # Ajusta anchos
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue), # Color de encabezado
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'), 
            ('ALIGN', (0, 1), (0, -1), 'RIGHT'), # Cantidad a la derecha
            ('ALIGN', (2, 1), (3, -1), 'RIGHT'), 
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        table.wrapOn(p, width - 2*inch, y_position)
        table_height = table._height
        table.drawOn(p, 1 * inch, y_position - table_height)
        y_position -= (table_height + 0.3 * inch)
    else:
        p.drawString(1 * inch, y_position, "No hay ítems facturados para esta orden.")
        y_position -= (0.3 * inch)

    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(width - 1 * inch, y_position, f"TOTAL: ${total_a_mostrar:.2f}") # Usar total_a_mostrar

    # ... (Notas Adicionales si las tienes en el modelo Factura)

    p.showPage()
    p.save()
    return response

# --- CONTROL DE CALIDAD (Placeholder) ---
@login_required
def control_calidad_view(request): 
    return render(request, "control_calidad/control_calidad.html")

################################################################################
# --- VISTAS ANTIGUAS/PLACEHOLDER (Revisar y decidir si se eliminan) ---

def produccion(req):
    return render(req, "produccion/produccion.html")

def ventas(req):
    return render(req, "ventas/ventas.html")

def control_calidad(req):
    return render(req, "control_calidad/control_calidad.html")

#  Funciones para los botones del sidebar de Compras
def desglose(req):
    return render(req, "compras/desglose.html")

def seguimiento(req):
    return render(req, "compras/seguimiento.html")

def tracking(req):
    return render(req, "compras/tracking.html")

def desglose2(req):
    return render(req, "compras/desglose2.html")

def desglose3(req, producto_id):
    context = {
        'producto_id': producto_id,
    }
    return render(req, "desglose3.html", context)

def ordenes(request):
    return render(request, 'produccion/ordenes.html')

def planificacion(request):
    return render(request, 'produccion/planificacion.html')

def depo_seleccion(request):
    return render(request, 'deposito/depo_seleccion.html')

def depo_enviar(request):
    return render(request, 'deposito/depo_enviar.html')
