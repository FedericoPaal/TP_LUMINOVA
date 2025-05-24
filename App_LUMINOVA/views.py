from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.decorators import user_passes_test, login_required
from .models import AuditoriaAcceso
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import *
from django.contrib import messages
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from .forms import (
    RolForm, PermisosRolForm
)
from django.db import transaction
# Create your views here.

#  Funciones para las vistas del navbar
def compras(req):
    return render(req, "compras/compras.html")

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

def reportes(request):
    return render(request, 'produccion/reportes.html')

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
    template_name = 'deposito/deposito.html' 
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
    success_url = reverse_lazy('App_LUMINOVA:deposito')

class Categoria_IUpdateView(UpdateView):
    model = CategoriaInsumo
    template_name = 'deposito/categoria_insumo_editar.html'
    fields = ('nombre', 'imagen')
    context_object_name = 'categoria'
    success_url = reverse_lazy('App_LUMINOVA:deposito')

class Categoria_IDeleteView(DeleteView):
    model = CategoriaInsumo
    template_name = 'deposito/categoria_insumo_confirm_delete.html'
    context_object_name = 'categoria'
    success_url = reverse_lazy('App_LUMINOVA:deposito')


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
    success_url = reverse_lazy('App_LUMINOVA:deposito')

class Categoria_PTUpdateView(UpdateView):
    model = CategoriaProductoTerminado
    template_name = 'deposito/categoria_producto_terminado_editar.html'
    fields = ('nombre', 'imagen')
    context_object_name = 'categoria'
    success_url = reverse_lazy('App_LUMINOVA:deposito')

class Categoria_PTDeleteView(DeleteView):
    model = CategoriaProductoTerminado
    template_name = 'deposito/categoria_producto_terminado_confirm_delete.html'
    context_object_name = 'categoria'
    success_url = reverse_lazy('App_LUMINOVA:deposito')


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
    success_url = reverse_lazy('App_LUMINOVA:deposito') 

class InsumoUpdateView(UpdateView):
    model = Insumo
    template_name = 'deposito/insumo_editar.html'
    fields = '__all__'
    context_object_name = 'insumo'
    success_url = reverse_lazy('App_LUMINOVA:deposito')

class InsumoDeleteView(DeleteView):
    model = Insumo
    template_name = 'deposito/insumo_confirm_delete.html'
    context_object_name = 'insumo'
    success_url = reverse_lazy('App_LUMINOVA:deposito')


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
    success_url = reverse_lazy('App_LUMINOVA:deposito')

class ProductoTerminadoUpdateView(UpdateView):
    model = ProductoTerminado
    template_name = 'deposito/productoterminado_editar.html'
    fields = '__all__'
    context_object_name = 'producto_terminado' 
    success_url = reverse_lazy('App_LUMINOVA:deposito')

class ProductoTerminadoDeleteView(DeleteView):
    model = ProductoTerminado
    template_name = 'deposito/productoterminado_confirm_delete.html'
    context_object_name = 'producto_terminado'
    success_url = reverse_lazy('App_LUMINOVA:deposito')