# TP_LUMINOVA-main/App_LUMINOVA/views.py

from django.http import JsonResponse # Necesario para vistas AJAX
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group, Permission
# from django.contrib.auth.forms import UserCreationForm, UserChangeForm # No se usan directamente aquí
from django.contrib.auth.decorators import user_passes_test, login_required
# from .models import AuditoriaAcceso # Se importará más abajo con otros modelos
from django.contrib.auth import authenticate, login, logout as auth_logout # Renombrado
# from django.contrib.auth.decorators import login_required # Ya importado arriba
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt # Usar con precaución
from django.db import transaction, IntegrityError as DjangoIntegrityError  # Para transacciones y error de Django
from django.utils import timezone # Para fechas y horas
from django.db.models import ProtectedError

# Importa los modelos que realmente existen y necesitas:
from .models import (
    AuditoriaAcceso,
    CategoriaProductoTerminado, ProductoTerminado, CategoriaInsumo, Insumo,
    ComponenteProducto, Proveedor, Cliente,
    Orden, # <--- Agregado para Órdenes de Compra
    OrdenVenta, ItemOrdenVenta, # <--- MODELO PARA ÓRDENES DE VENTA
    EstadoOrden, SectorAsignado, OrdenProduccion, # Modelos para Órdenes de Producción
    Reportes, Factura, RolDescripcion, Fabricante,
)

# Importa los formularios que realmente existen y necesitas:
from .forms import (
    FacturaForm, RolForm, PermisosRolForm, ClienteForm, ProveedorForm, # Asegúrate que ProveedorForm exista si lo usas
    OrdenVentaForm, ItemOrdenVentaFormSet, OrdenProduccionUpdateForm,
)
# Create your views here.

#  Funciones para las vistas del navbar
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
    # Esta vista mostraría las OCs que están pendientes de generar pedidos a proveedores
    # Basado en el estado 'PENDIENTE_COMPRAR' o similar que definimos para Orden.
    # estado_pendiente = EstadoOrden.objects.filter(nombre__iexact='Pendiente a Comprar').first() # Necesitarías EstadoOrden para OC
    # ordenes_pendientes_compra = []
    # if estado_pendiente:
    #     ordenes_pendientes_compra = Orden.objects.filter(tipo='compra', estado=estado_pendiente).order_by('-fecha_creacion')

    context = {
        # 'ordenes_pendientes_list': ordenes_pendientes_compra,
        'ordenes_pendientes_list': [], # Placeholder por ahora
        'titulo_seccion': 'Desglose de Componentes para Compra',
    }
    return render(request, 'compras/compras_desglose.html', context)

@login_required
def compras_seguimiento_view(request):
    # Esta vista mostraría las OCs que ya fueron enviadas a proveedores y están en seguimiento
    # estado_solicitada = EstadoOrden.objects.filter(nombre__iexact='Solicitada').first() # Necesitarías EstadoOrden para OC
    # ordenes_en_seguimiento = []
    # if estado_solicitada:
    #     ordenes_en_seguimiento = Orden.objects.filter(tipo='compra', estado=estado_solicitada).order_by('-fecha_creacion')

    context = {
        # 'ordenes_solicitadas_list': ordenes_en_seguimiento,
        'ordenes_solicitadas_list': [], # Placeholder por ahora
        'titulo_seccion': 'Seguimiento de Órdenes de Compra',
    }
    return render(request, 'compras/compras_seguimiento.html', context)

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

def produccion(req):
    return render(req, "produccion/produccion.html")

def ventas(req):
    return render(req, "ventas/ventas.html")

def deposito(req):
    categorias_I = CategoriaInsumo.objects.all()
    categorias_PT = CategoriaProductoTerminado.objects.all()
    insumos = Insumo.objects.all() # Estos no se usan directamente en deposito.html, sino en sus detalles
    productos_terminados = ProductoTerminado.objects.all() # Ídem
    return render(req, 'deposito/deposito.html', {
        'categorias_I': categorias_I,
        'categorias_PT': categorias_PT,
        # 'insumos': insumos, # No es necesario pasar todos los insumos aquí
        # 'productos_terminados': productos_terminados # No es necesario pasar todos los PT aquí
    })

def control_calidad(req):
    return render(req, "control_calidad/control_calidad.html")

def inicio(request): # Esta vista es la que se muestra si el usuario no está autenticado
    if request.user.is_authenticated:
        return redirect('App_LUMINOVA:dashboard')
    return redirect('App_LUMINOVA:login') # Redirige a login si no está autenticado


#  Funciones para el login y logout
# La vista login_view personalizada no es estrictamente necesaria si usas auth_views.LoginView
# pero la dejamos por si decides personalizarla más adelante.
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

# logout_view es manejada por Django en urls.py

#  Funciones para los botones del sidebar del Admin
@login_required
def roles_permisos_view(request):
    roles = Group.objects.all().select_related('descripcion_extendida').prefetch_related('permissions')
    return render(request, 'admin/roles_permisos.html', {'roles': roles})

@login_required
def auditoria_view(request):
    auditorias = AuditoriaAcceso.objects.select_related('usuario').order_by('-fecha_hora')
    return render(request, 'admin/auditoria.html', {'auditorias': auditorias})

# Funciones CRUD para los Usuarios
def es_admin(user):
    return user.groups.filter(name='administrador').exists() or user.is_superuser

@login_required
@user_passes_test(es_admin)
def lista_usuarios(request):
    usuarios = User.objects.filter(is_superuser=False).order_by('id')
    return render(request, 'admin/usuarios.html', {'usuarios': usuarios})

# --- CRUD de usuario (mantener como estaba si funcionaba) ---
@login_required
def lista_usuarios(request):
    usuarios = User.objects.all().prefetch_related('groups') # prefetch groups para eficiencia
    return render(request, 'admin/usuarios.html', {'usuarios': usuarios})

@login_required
# @require_POST # Descomentar si es solo AJAX POST
def crear_usuario(request):
    if request.method == 'POST':
        # ESTE FORMULARIO ES MUY BÁSICO. Deberías crear un CustomUserCreationForm
        # que incluya campos para email, rol, y estado.
        # Por ahora, tomaremos los datos directamente del POST y validaremos manualmente.

        username = request.POST.get('username')
        email = request.POST.get('email')
        rol_name = request.POST.get('rol')
        estado_str = request.POST.get('estado')
        password = request.POST.get('password', 'temporal') # Deberías tener un campo de contraseña en el modal

        errors = {}
        if not username: errors['username'] = 'Este campo es requerido.'
        if User.objects.filter(username=username).exists(): errors['username'] = 'Este nombre de usuario ya existe.'
        if not email: errors['email'] = 'Este campo es requerido.'
        # Añadir más validaciones (ej. formato de email)

        if errors:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest': # Si es AJAX
                return JsonResponse({'success': False, 'errors': errors})
            else: # Si es un POST normal
                for field, error_list in errors.items():
                    for err in error_list if isinstance(error_list, list) else [error_list]:
                         messages.error(request, f"Error en {field}: {err}")
                return redirect('App_LUMINOVA:lista_usuarios')


        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password # ¡DEBE SER HASHEADA! Usa make_password si no usas un form de Django que lo haga.
            )
            user.is_active = (estado_str == 'Activo')

            if rol_name:
                try:
                    group = Group.objects.get(name=rol_name)
                    user.groups.add(group)
                except Group.DoesNotExist:
                    # Manejar el caso de que el grupo no exista, quizás con un error.
                    user.delete() # Rollback de la creación del usuario
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'errors': {'rol': [f"El rol '{rol_name}' no existe."]}})
                    else:
                        messages.error(request, f"El rol '{rol_name}' no existe.")
                        return redirect('App_LUMINOVA:lista_usuarios')

            user.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'user': { # Devuelve los datos del usuario para añadirlo a la tabla dinámicamente
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

    # Si es GET, podrías renderizar un formulario o simplemente no hacer nada si el modal se maneja en la misma página.
    # Por ahora, si no es POST, no hacemos nada especial, asumiendo que el modal está en lista_usuarios.html
    return redirect('App_LUMINOVA:lista_usuarios') # O renderizar la página con el modal

@login_required
@require_POST # Es buena práctica
def editar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if request.method == 'POST':
        # De nuevo, UserChangeForm es limitado. Un form personalizado es mejor.
        # form = UserChangeForm(request.POST, instance=usuario)
        # if form.is_valid():
        #     form.save()
        #     messages.success(request, f"Usuario '{usuario.username}' actualizado.")
        #     return redirect('App_LUMINOVA:lista_usuarios')
        # else:
        #     for field, errors in form.errors.items():
        #         for error in errors:
        #             messages.error(request, f"Error al editar {field}: {error}")
        #     return redirect('App_LUMINOVA:lista_usuarios') # O renderizar form_editar_usuario.html

        # Lógica manual para actualizar campos básicos, rol y estado
        usuario.username = request.POST.get('username', usuario.username)
        usuario.email = request.POST.get('email', usuario.email)

        # Actualizar rol
        rol_name = request.POST.get('rol')
        usuario.groups.clear() # Limpiar roles existentes
        if rol_name:
            try:
                group = Group.objects.get(name=rol_name)
                usuario.groups.add(group)
            except Group.DoesNotExist:
                messages.error(request, f"El rol '{rol_name}' no existe.")

        # Actualizar estado
        estado_str = request.POST.get('estado')
        if estado_str: # Asegurarse que 'estado' está en POST
            usuario.is_active = (estado_str == 'Activo')

        usuario.save()
        messages.success(request, f"Usuario '{usuario.username}' actualizado exitosamente.")
        return redirect('App_LUMINOVA:lista_usuarios')
    return redirect('App_LUMINOVA:lista_usuarios') # Si no es POST


@login_required
@require_POST # Es buena práctica
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



#  Funciones para los botones del sidebar de Compras
def desglose(req):
    return render(req, "compras/desglose.html")

def seguimiento(req):
    return render(req, "compras/seguimiento.html")

def tracking(req):
    return render(req, "compras/tracking.html")

def desglose2(req):
    return render(req, "compras/desglose2.html")

#  Funciones para los botones del sidebar de Produccion
def ordenes(request):
    return render(request, 'produccion/ordenes.html')

def planificacion(request):
    return render(request, 'produccion/planificacion.html')



#  Funciones para el boton Seleccionar de la tabla de OP// los botones del sidebar de Deposito
def depo_seleccion(request):
    return render(request, 'deposito/depo_seleccion.html')

def depo_enviar(request):
    return render(request, 'deposito/depo_enviar.html')

# La vista genérica categoria_detail ya no es necesaria con las DetailView específicas.
# def categoria_detail(req):
#     ...

# --- CRUD Categorias Insumo ---
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
    template_name = 'deposito/insumo_editar.html'
    fields = '__all__'
    context_object_name = 'insumo'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

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

class ProveedorCreateView(CreateView):
    model = Proveedor
    template_name = 'ventas/proveedores/proveedor_crear.html'
    fields = '__all__'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class ProveedorUpdateView(UpdateView):
    model = Proveedor
    template_name = 'ventas/proveedores/proveedor_editar.html'
    fields = '__all__'
    context_object_name = 'proveedor'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')

class ProveedorDeleteView(DeleteView):
    model = Proveedor
    template_name = 'ventas/proveedores/proveedor_confirm_delete.html'
    context_object_name = 'proveedor'
    success_url = reverse_lazy('App_LUMINOVA:deposito_view')


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


# TP_LUMINOVA-main/App_LUMINOVA/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.utils import IntegrityError as DjangoIntegrityError
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView # Si las usas para otros CRUDs

from .models import (
    Cliente, OrdenVenta, ItemOrdenVenta, ProductoTerminado, OrdenProduccion,
    EstadoOrden, SectorAsignado, Proveedor, Insumo, CategoriaInsumo,
    CategoriaProductoTerminado, RolDescripcion, AuditoriaAcceso, ComponenteProducto
)
from .forms import (
    ClienteForm, OrdenVentaForm, ItemOrdenVentaFormSet, OrdenProduccionUpdateForm,
    # Si tienes InsumoForm, ProductoTerminadoForm, etc., impórtalos aquí
)

# --- HELPER ---
def es_admin_o_rol(user, roles_permitidos=None):
    if user.is_superuser:
        return True
    if roles_permitidos is None:
        roles_permitidos = []
    return user.groups.filter(name__in=[rol.lower() for rol in roles_permitidos]).exists()

# --- VISTAS DE CLIENTES ---
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

# --- VISTAS PARA ÓRDENES DE VENTA ---
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

# ... (resto de tus vistas para Producción, Depósito, Admin, etc., ajustando nombres de modelos y campos si es necesario)


# --- VISTAS PARA PRODUCCIÓN ---
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
@transaction.atomic # Asegurar que ambas actualizaciones ocurran o ninguna
def produccion_detalle_op_view(request, op_id):
    op = get_object_or_404(
        OrdenProduccion.objects.select_related(
            'producto_a_producir', 
            'orden_venta_origen__cliente', # Necesario para el cliente
            'estado_op', 
            'sector_asignado_op'
        ), 
        id=op_id
    )
    
    # ... (lógica para insumos_necesarios_data) ...
    insumos_necesarios_data = []
    todos_los_insumos_disponibles = True 
    if op.producto_a_producir:
        componentes_requeridos = ComponenteProducto.objects.filter(
            producto_terminado=op.producto_a_producir
        ).select_related('insumo')
        if not componentes_requeridos.exists():
            messages.warning(request, f"No se han definido componentes (BOM) para el producto '{op.producto_a_producir.descripcion}'.")
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
        messages.error(request, "La Orden de Producción no tiene un producto asociado.")
        todos_los_insumos_disponibles = False

    if request.method == 'POST':
        form_update = OrdenProduccionUpdateForm(request.POST, instance=op)
        if form_update.is_valid():
            op_actualizada = form_update.save() # Guardar la OP
            messages.success(request, f"Orden de Producción {op_actualizada.numero_op} actualizada a '{op_actualizada.estado_op.nombre}'.")

            # --- LÓGICA PARA ACTUALIZAR ESTADO DE OV ---
            if op_actualizada.orden_venta_origen and op_actualizada.estado_op:
                orden_venta_asociada = op_actualizada.orden_venta_origen
                
                # Definir qué estado de OP significa "producción completada para este item/OP"
                # Asegúrate de que 'Terminado' sea el nombre exacto de tu EstadoOrden
                if op_actualizada.estado_op.nombre.lower() == 'completada':
                    # Verificar si TODAS las OPs asociadas a esta OV están terminadas
                    todas_ops_terminadas = True
                    # .ops_generadas es el related_name de OrdenVenta a OrdenProduccion
                    for otra_op in orden_venta_asociada.ops_generadas.all(): 
                        if not otra_op.estado_op or otra_op.estado_op.nombre.lower() != 'completada':
                            todas_ops_terminadas = False
                            break
                    
                    if todas_ops_terminadas:
                        orden_venta_asociada.estado = 'LISTA_ENTREGA' # O el estado que uses para facturable
                        orden_venta_asociada.save(update_fields=['estado'])
                        messages.info(request, f"Todos los productos para la OV {orden_venta_asociada.numero_ov} están listos. Estado de OV actualizado a 'Lista para Entrega'.")
            # --- FIN LÓGICA ACTUALIZAR ESTADO DE OV ---
            
            return redirect('App_LUMINOVA:produccion_detalle_op', op_id=op_actualizada.id)
        else:
            messages.error(request, "Error al actualizar la OP. Revise los datos del formulario.")
            # Re-renderizar con el form con errores (ya se hace abajo)
    else: # GET
        form_update = OrdenProduccionUpdateForm(instance=op)

    context = {
        'op': op,
        'insumos_necesarios_list': insumos_necesarios_data,
        'form_update_op': form_update,
        'todos_los_insumos_disponibles_variable_de_contexto': todos_los_insumos_disponibles,
        'titulo_seccion': f'Detalle OP: {op.numero_op}',
    }
    return render(request, 'produccion/produccion_detalle_op.html', context)

@login_required
@transaction.atomic # Buena idea para operaciones que modifican stock
def deposito_enviar_insumos_op_view(request, op_id):
    op = get_object_or_404(OrdenProduccion, id=op_id)

    if request.method == 'POST':
        # Lógica para descontar insumos del stock
        # Esto se implementaría completamente después, pero la vista debe existir
        insumos_descontados_correctamente = True
        componentes_requeridos = ComponenteProducto.objects.filter(producto_terminado=op.producto_a_producir)

        for comp in componentes_requeridos:
            cantidad_a_descontar = comp.cantidad_necesaria * op.cantidad_a_producir
            if comp.insumo.stock >= cantidad_a_descontar:
                # Insumo.objects.filter(id=comp.insumo.id).update(stock=F('stock') - cantidad_a_descontar) # Mejor para concurrencia
                comp.insumo.stock -= cantidad_a_descontar
                comp.insumo.save()
            else:
                messages.error(request, f"Stock insuficiente para '{comp.insumo.descripcion}'. Requeridos: {cantidad_a_descontar}, Disponible: {comp.insumo.stock}")
                insumos_descontados_correctamente = False
                break

        if insumos_descontados_correctamente:
            # Cambiar estado de la OP, por ejemplo a "En Proceso" o un estado "Insumos Entregados"
            try:
                # Asume que tienes un estado como "En Proceso" o "Insumos Listos"
                estado_siguiente = EstadoOrden.objects.get(nombre__iexact='En Proceso')
                op.estado_op = estado_siguiente
                op.save()
                messages.success(request, f"Insumos para OP {op.numero_op} descontados del stock. OP ahora 'En Proceso'.")
            except EstadoOrden.DoesNotExist:
                 messages.warning(request, "Estado 'En Proceso' no encontrado para OP. Insumos descontados, pero el estado de la OP no se actualizó.")
            # Redirigir a la lista de solicitudes de depósito o al detalle de la OP de producción
            return redirect('App_LUMINOVA:deposito_solicitudes_insumos')
        else:
            # Si no se descontaron, redirige de nuevo al detalle de la solicitud en depósito para ver el error
            return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

    # Si es GET, podría redirigir o mostrar alguna confirmación, pero usualmente esta acción es POST.
    # Por ahora, redirigimos a la página de detalle de la solicitud en depósito.
    messages.info(request, "Para enviar insumos, confirme la acción desde la página de detalle de la solicitud.")
    return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)


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

""" class Reportes(models.Model):
    orden_produccion_asociada = models.ForeignKey(OrdenProduccion, on_delete=models.SET_NULL, null=True, blank=True, related_name="reportes_incidencia")
    n_reporte = models.CharField(max_length=20, unique=True) # RP-XXXX
    fecha = models.DateTimeField(default=timezone.now)
    tipo_problema = models.CharField(max_length=100)
    descripcion_problema = models.TextField(blank=True, null=True) # Cambiado de informe_reporte
    reportado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # Quién lo reportó
    sector_reporta = models.ForeignKey(SectorAsignado, on_delete=models.SET_NULL, null=True, blank=True) # Desde qué sector

    def __str__(self):
        return f"Reporte {self.n_reporte} (OP: {self.orden_produccion_asociada.numero_op if self.orden_produccion_asociada else 'N/A'})"
 """
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

# --- VISTAS PARA DEPÓSITO (Manejo de Insumos para OPs) ---

@login_required
def deposito_view(request): # Tu vista principal de depósito (ya la tienes, solo para contexto)
    categorias_I = CategoriaInsumo.objects.all()
    categorias_PT = CategoriaProductoTerminado.objects.all()

    # Podrías añadir un resumen de OPs esperando insumos aquí también
    estado_requiere_insumos = EstadoOrden.objects.filter(nombre__iexact='En Proceso').first() # O un estado "Insumos Solicitados"
    ops_pendientes_deposito_count = 0
    if estado_requiere_insumos:
        ops_pendientes_deposito_count = OrdenProduccion.objects.filter(estado_op=estado_requiere_insumos).count()

    context = {
        'categorias_I': categorias_I,
        'categorias_PT': categorias_PT,
        'ops_pendientes_deposito_count': ops_pendientes_deposito_count,
        # ... (otro contexto que ya tenías)
    }
    return render(request, 'deposito/deposito.html', context)


@login_required
def deposito_solicitudes_insumos_view(request):
    """
    Muestra una lista de Órdenes de Producción que están en un estado
    que requiere que el depósito prepare/envíe insumos.
    Ej: Estado "En Proceso" o un estado específico como "Esperando Insumos".
    """
    # if not es_admin_o_rol(request.user, ['deposito', 'administrador']): # Control de permisos
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    # Decide qué estado de OP significa "necesita insumos de depósito"
    # Podría ser 'En Proceso', o podrías crear un estado específico como 'Insumos Solicitados'
    # Aquí asumimos 'En Proceso' o un estado más específico que debes crear en el admin: 'Esperando Preparación Insumos'
    try:
        # Intenta con un estado específico si lo tienes
        estado_objetivo = EstadoOrden.objects.get(nombre__iexact='Insumos Solicitados')
    except EstadoOrden.DoesNotExist:
        # Si no, usa 'En Proceso' como fallback o muestra un error
        estado_objetivo = EstadoOrden.objects.filter(nombre__iexact='En Proceso').first()
        if not estado_objetivo:
            messages.warning(request, "No se ha configurado un estado de OP para la solicitud de insumos (ej. 'Insumos Solicitados' o 'En Proceso'). Mostrando todas las OPs pendientes.")
            # Como fallback, podrías mostrar todas las OPs que no estén 'Terminado' o 'Cancelado'
            ops_necesitan_insumos = OrdenProduccion.objects.exclude(
                estado_op__nombre__iexact='Terminado'
            ).exclude(
                estado_op__nombre__iexact='Cancelado'
            ).select_related('producto_a_producir', 'estado_op').order_by('fecha_solicitud')
        else:
            ops_necesitan_insumos = OrdenProduccion.objects.filter(
                estado_op=estado_objetivo
            ).select_related('producto_a_producir', 'estado_op').order_by('fecha_solicitud')


    context = {
        'ops_necesitan_insumos_list': ops_necesitan_insumos,
        'titulo_seccion': 'Órdenes de Producción Pendientes de Insumos'
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


@login_required
@transaction.atomic
def deposito_enviar_insumos_op_view(request, op_id):
    """
    Procesa el envío/descuento de insumos para una OP.
    Esta vista es llamada por un POST, usualmente desde deposito_detalle_solicitud_op.html.
    """
    # if not es_admin_o_rol(request.user, ['deposito', 'administrador']): # Control de permisos
    #     messages.error(request, "Acción no permitida.")
    #     return redirect('App_LUMINOVA:deposito_solicitudes_insumos')

    op = get_object_or_404(OrdenProduccion, id=op_id)

    if request.method == 'POST':
        insumos_descontados_correctamente = True
        componentes_requeridos = ComponenteProducto.objects.filter(producto_terminado=op.producto_a_producir)

        if not componentes_requeridos.exists():
            messages.error(request, f"No se puede procesar: No hay BOM definido para '{op.producto_a_producir.descripcion}'.")
            return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

        for comp in componentes_requeridos:
            cantidad_a_descontar = comp.cantidad_necesaria * op.cantidad_a_producir

            # Re-chequear stock antes de descontar (importante por concurrencia, aunque F() es mejor)
            insumo_a_actualizar = Insumo.objects.get(id=comp.insumo.id) # Obtener la instancia más reciente
            if insumo_a_actualizar.stock >= cantidad_a_descontar:
                insumo_a_actualizar.stock -= cantidad_a_descontar
                insumo_a_actualizar.save(update_fields=['stock'])
                # Mejor para concurrencia (pero requiere que 'cantidad_a_descontar' sea positivo):
                # Insumo.objects.filter(id=comp.insumo.id, stock__gte=cantidad_a_descontar).update(stock=F('stock') - cantidad_a_descontar)
                # updated_rows = Insumo.objects.filter(id=comp.insumo.id, stock__gte=cantidad_a_descontar).update(stock=F('stock') - cantidad_a_descontar)
                # if updated_rows == 0: # No se pudo actualizar, probablemente stock insuficiente
                #    insumos_descontados_correctamente = False
                #    messages.error(request, f"Stock insuficiente o error al actualizar '{comp.insumo.descripcion}'.")
                #    break
            else:
                messages.error(request, f"Stock insuficiente para '{comp.insumo.descripcion}'. Requeridos: {cantidad_a_descontar}, Disponible: {insumo_a_actualizar.stock}")
                insumos_descontados_correctamente = False
                break

        if insumos_descontados_correctamente:
            try:
                # Actualizar estado de la OP, ej. a "En Proceso" (si antes era "Insumos Solicitados")
                # o a "Insumos Entregados a Producción" si tienes ese estado.
                # Aquí es crucial que tengas un estado "En Proceso" o el siguiente lógico.
                estado_siguiente = EstadoOrden.objects.get(nombre__iexact='En Proceso')
                op.estado_op = estado_siguiente
                op.fecha_inicio_real = timezone.now() # Opcional: marcar cuándo se entregaron los insumos como inicio real
                op.save(update_fields=['estado_op', 'fecha_inicio_real'])
                messages.success(request, f"Insumos para OP {op.numero_op} descontados. OP ahora '{estado_siguiente.nombre}'.")
            except EstadoOrden.DoesNotExist:
                 messages.warning(request, "Estado de OP para 'En Proceso' no encontrado. Insumos descontados, pero el estado de la OP no se actualizó.")
            return redirect('App_LUMINOVA:deposito_solicitudes_insumos')
        else:
            # Si no se descontaron todos, se queda en la página de detalle para ver el error.
            return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

    # Si es GET, no debería hacer nada más que redirigir.
    messages.info(request, "Para enviar insumos, confirme la acción desde la página de detalle de la solicitud de OP.")
    return redirect('App_LUMINOVA:deposito_detalle_solicitud_op', op_id=op.id)

# --- VISTAS PARA ÓRDENES DE VENTA ---
@login_required
def ventas_detalle_ov_view(request, ov_id):
    # if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    orden_venta = get_object_or_404(
        OrdenVenta.objects.select_related('cliente').prefetch_related(
            'items_ov__producto_terminado', 
            'ops_generadas', # Si quieres mostrar OPs asociadas
            'factura_asociada' # Para acceder a la factura si existe
        ), 
        id=ov_id
    )
    
    # Formulario para generar factura (si no existe una)
    factura_form = None
    if not hasattr(orden_venta, 'factura_asociada') or not orden_venta.factura_asociada:
        # Solo mostrar el form si la OV está en un estado facturable
        if orden_venta.estado in ['LISTA_ENTREGA', 'COMPLETADA']: # Ajusta estos estados según tu lógica
            factura_form = FacturaForm()


    context = {
        'ov': orden_venta,
        'items_ov': orden_venta.items_ov.all(), # Pasar los items explícitamente
        'factura_form': factura_form,
        'titulo_seccion': f"Detalle Orden de Venta: {orden_venta.numero_ov}",
    }
    return render(request, 'ventas/ventas_detalle_ov.html', context)


@login_required
@transaction.atomic
def ventas_generar_factura_view(request, ov_id):
    # if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
    #     messages.error(request, "Acción no permitida.")
    #     return redirect('App_LUMINOVA:ventas_lista_ov')

    orden_venta = get_object_or_404(OrdenVenta, id=ov_id)

    # Verificar si ya existe una factura para esta OV
    if hasattr(orden_venta, 'factura_asociada') and orden_venta.factura_asociada:
        messages.warning(request, f"La Orden de Venta {orden_venta.numero_ov} ya tiene una factura asociada (N° {orden_venta.factura_asociada.numero_factura}).")
        return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)

    # Verificar si la OV está en un estado facturable
    if orden_venta.estado not in ['LISTA_ENTREGA']: # Ajusta según tu flujo
        messages.error(request, f"La Orden de Venta {orden_venta.numero_ov} no está en un estado facturable (Estado actual: {orden_venta.get_estado_display()}).")
        return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)

    if request.method == 'POST':
        form = FacturaForm(request.POST)
        if form.is_valid():
            try:
                factura = form.save(commit=False)
                factura.orden_venta = orden_venta
                factura.total_facturado = orden_venta.total_ov # El total de la factura es el total de la OV
                factura.cliente = orden_venta.cliente # Redundante si se accede vía orden_venta, pero puede ser útil
                factura.fecha_emision = timezone.now() # O permitir seleccionarla
                factura.save()
                messages.success(request, f"Factura N° {factura.numero_factura} generada para la OV {orden_venta.numero_ov}.")
                return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)
            except DjangoIntegrityError:
                 messages.error(request, f"Error: El número de factura '{form.cleaned_data.get('numero_factura')}' ya existe.")
            except Exception as e:
                messages.error(request, f"Error al generar la factura: {e}")
        else:
            # Si el formulario no es válido, mostrar errores y redirigir al detalle de OV
            for field, errors in form.errors.items():
                 for error in errors:
                    messages.error(request, f"{form.fields[field].label or field}: {error}")
    
    # Si es GET o el form no es válido, redirige de vuelta al detalle de la OV
    # (el modal de facturación debería estar en la página de detalle de OV)
    return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=orden_venta.id)