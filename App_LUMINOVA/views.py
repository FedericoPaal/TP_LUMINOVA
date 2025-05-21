from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.decorators import user_passes_test, login_required
from .models import AuditoriaAcceso
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import *
from django.contrib import messages

# Create your views here.

#  Funciones para las vistas del navbar
def compras(req):
    return render(req, "compras.html")

def produccion(req):
    return render(req, "produccion.html")

def ventas(req):
    return render(req, "ventas.html")

def deposito(req):
    return render(req, "deposito.html")

def control_calidad(req):
    return render(req, "control_calidad.html")

def inicio(request):
    if request.user.is_authenticated:
        return redirect('App_LUMINOVA:dashboard')  # Redirige al dashboard si está autenticado
    return redirect('App_LUMINOVA:login')  # Redirige al login si no está autenticado

#  Funciones para el login y logout
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard.html')

    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password'),
        )
        if user:
            login(request, user)
            return redirect('App_LUMINOVA:dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'login.html')

@login_required
def dashboard_view(request):
    return render(request, 'dashboard.html')

def logout_view(request):
    logout(request)
    return redirect('login.html')

#  Funciones para los botones del sidebar del Admin
def roles_permisos_view(request):
    roles = Group.objects.all().select_related('descripcion_extendida').prefetch_related('permissions')
    return render(request, 'roles_permisos.html', {'roles': roles})

def auditoria_view(request):
    auditorias = AuditoriaAcceso.objects.select_related('usuario').order_by('-fecha_hora')
    return render(request, 'auditoria.html', {'auditorias': auditorias})

# Funciones CRUD para los Usuarios
# Función para verificar si el usuario es administrador
def es_admin(user):
    return user.groups.filter(name='administrador').exists() or user.is_superuser

# Lista de usuarios
@login_required
@user_passes_test(es_admin)
def lista_usuarios(request):
    # Mostrar solo usuarios que NO son superusuarios
    usuarios = User.objects.filter(is_superuser=False).order_by('id')
    form = UserCreationForm()
    return render(request, 'usuarios.html', {'usuarios': usuarios, 'form': form})

# Creación de usuario
@login_required
@user_passes_test(es_admin)
def crear_usuario(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        rol_nombre = request.POST.get('rol')
        estado = request.POST.get('estado')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya existe.')
            return redirect('App_LUMINOVA:lista_usuarios')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'El correo electrónico ya existe.')
            return redirect('App_LUMINOVA:lista_usuarios')

        user = User.objects.create_user(username=username, email=email, is_active=(estado == 'Activo'))
        user.set_password('temporal')  # Establecer una contraseña temporal
        user.save()

        # Asignar rol
        try:
            rol = Group.objects.get(name=rol_nombre)
            user.groups.add(rol)
        except Group.DoesNotExist:
            messages.error(request, f'No existe el rol "{rol_nombre}".')
            user.delete()
            return redirect('App_LUMINOVA:lista_usuarios')

        messages.success(request, 'Usuario creado exitosamente. La contraseña es "temporal".')
        return redirect('App_LUMINOVA:lista_usuarios')
    else:
        form = UserCreationForm()
        return render(request, 'usuarios.html', {'form': form})

# Edición de usuario
@login_required
@user_passes_test(es_admin)
def editar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if request.method == 'POST':
        usuario.username = request.POST.get('username')
        usuario.email = request.POST.get('email')
        rol_nombre = request.POST.get('rol')
        usuario.is_active = request.POST.get('estado') == 'Activo'
        usuario.save()

         # Actualizar rol
        try:
            rol = Group.objects.get(name=rol_nombre)
            usuario.groups.clear()  # Elimina los roles anteriores
            usuario.groups.add(rol) # Agrega el nuevo rol
        except Group.DoesNotExist:
             messages.error(request, f'No existe el rol "{rol_nombre}".')
             return redirect('App_LUMINOVA:lista_usuarios')

        messages.success(request, 'Usuario editado exitosamente.')
        return redirect('App_LUMINOVA:lista_usuarios')
    else:
        form = UserChangeForm(instance=usuario)
        return render(request, 'usuarios.html', {'form': form, 'usuario': usuario})

# Eliminación de usuario
@login_required
@user_passes_test(es_admin)
def eliminar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuario eliminado exitosamente.')
        return redirect('App_LUMINOVA:lista_usuarios')
    return render(request, 'eliminar_usuario.html', {'usuario': usuario})

#  Funciones para los botones del sidebar de Compras
def desglose(req):
    return render(req, "desglose.html")

def seguimiento(req):
    return render(req, "seguimiento.html")

def tracking(req):
    return render(req, "tracking.html")

def desglose2(req):
    return render(req, "desglose2.html")

#  Funciones para los botones del sidebar de Produccion
def ordenes(request):
    return render(request, 'ordenes.html')

def planificacion(request):
    return render(request, 'planificacion.html')

def reportes(request):
    return render(request, 'reportes.html')

#  Funciones para el boton Seleccionar de la tabla de OP// los botones del sidebar de Deposito
def depo_seleccion(request):
    return render(request, 'depo_seleccion.html')

def depo_enviar(request):
    return render(request, 'depo_enviar.html')


