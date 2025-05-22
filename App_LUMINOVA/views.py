from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
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
        return redirect('App_LUMINOVA:dashboard')

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

        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'El correo electrónico ya existe.')
            return redirect('App_LUMINOVA:lista_usuarios')

        user = User.objects.create_user(username=username, email=email, is_active=(estado == 'Activo'))
        user.set_password('Luminova2025!') # Contraseña temporal más segura
        user.save()

        if rol_nombre:
            try:
                rol = Group.objects.get(name=rol_nombre)
                user.groups.add(rol)
            except Group.DoesNotExist:
                messages.warning(request, f'Rol "{rol_nombre}" no encontrado. Usuario creado sin rol.')
        
        messages.success(request, f'Usuario {username} creado. Contraseña temporal: Luminova2025!')
        return redirect('App_LUMINOVA:lista_usuarios')
    return redirect('App_LUMINOVA:lista_usuarios') # Si no es POST, redirigir

@login_required
@user_passes_test(es_admin)
def editar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if request.method == 'POST':
        usuario.username = request.POST.get('username')
        usuario.email = request.POST.get('email')
        rol_nombre = request.POST.get('rol')
        usuario.is_active = request.POST.get('estado') == 'Activo'
        
        # Validar unicidad de username y email (excluyendo el usuario actual)
        if User.objects.filter(username=usuario.username).exclude(pk=id).exists():
            messages.error(request, 'Ese nombre de usuario ya está en uso.')
            return redirect('App_LUMINOVA:lista_usuarios')
        if usuario.email and User.objects.filter(email=usuario.email).exclude(pk=id).exists():
            messages.error(request, 'Ese correo electrónico ya está en uso.')
            return redirect('App_LUMINOVA:lista_usuarios')
            
        usuario.save()

        usuario.groups.clear() # Limpiar roles existentes
        if rol_nombre:
            try:
                rol = Group.objects.get(name=rol_nombre)
                usuario.groups.add(rol)
            except Group.DoesNotExist:
                 messages.warning(request, f'Rol "{rol_nombre}" no encontrado. Usuario editado sin rol.')

        messages.success(request, 'Usuario editado exitosamente.')
        return redirect('App_LUMINOVA:lista_usuarios')
    return redirect('App_LUMINOVA:lista_usuarios')

@login_required
@user_passes_test(es_admin)
def eliminar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if request.method == 'POST':
        if usuario == request.user:
            messages.error(request, "No puedes eliminar tu propio usuario.")
        else:
            usuario.delete()
            messages.success(request, 'Usuario eliminado exitosamente.')
        return redirect('App_LUMINOVA:lista_usuarios')
    return redirect('App_LUMINOVA:lista_usuarios')

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