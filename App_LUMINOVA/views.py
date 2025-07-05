import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth import logout as auth_logout_function
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm

# Django Contrib Imports
from django.contrib.auth.models import Group, Permission, User
from django.db import IntegrityError as DjangoIntegrityError
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Prefetch, ProtectedError, Q, Sum

# Django Core Imports
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt  # Usar con precaución
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# ReportLab (Third-party for PDF generation)
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from Proyecto_LUMINOVA import settings

# Local Application Imports (Forms)
from .forms import (
    ClienteForm,
    FacturaForm,
    ItemOrdenVentaFormSet,
    ItemOrdenVentaFormSetCreacion,
    OrdenCompraForm,
    OrdenProduccionUpdateForm,
    OrdenVentaForm,
    PermisosRolForm,
    ProveedorForm,
    ReporteProduccionForm,
    RolForm,
)

# Local Application Imports (Models)
from .models import (
    AuditoriaAcceso,
    CategoriaInsumo,
    CategoriaProductoTerminado,
    Cliente,
    ComponenteProducto,
    EstadoOrden,
    Fabricante,
    Factura,
    HistorialOV,
    Insumo,
    ItemOrdenVenta,
    LoteProductoTerminado,
    OfertaProveedor,
    Orden,
    OrdenProduccion,
    OrdenVenta,
    PasswordChangeRequired,
    ProductoTerminado,
    Proveedor,
    Reportes,
    RolDescripcion,
    SectorAsignado,
)
from .signals import get_client_ip

from .services.document_services import generar_siguiente_numero_documento
from .services.pdf_services import generar_pdf_factura
from .utils import es_admin, es_admin_o_rol

logger = logging.getLogger(__name__)


# --- GENERAL VIEWS & AUTHENTICATION ---
def inicio(
    request,
):  # Esta vista es la que se muestra si el usuario no está autenticado
    if request.user.is_authenticated:
        return redirect("App_LUMINOVA:dashboard")
    return redirect("App_LUMINOVA:login")  # Redirige a login si no está autenticado


def login_view(request):
    if request.user.is_authenticated:
        return redirect("App_LUMINOVA:dashboard")  # Redirige si ya está logueado

    if request.method == "POST":
        # Obtener los datos del formulario de login
        username_from_form = request.POST.get("username")
        password_from_form = request.POST.get("password")

        # Autenticar al usuario
        user = authenticate(
            request,
            username=username_from_form,
            password=password_from_form,
        )

        if user is not None:
            # Si la autenticación es exitosa, iniciar la sesión
            login(request, user)

            # --- LÓGICA CLAVE DE AUDITORÍA ---
            # Ahora que el usuario está logueado y tenemos el 'request' completo,
            # registramos el evento.
            AuditoriaAcceso.objects.create(
                usuario=user,
                accion="Inicio de sesión",
                ip_address=get_client_ip(request),  # Obtendrá la IP
                user_agent=request.META.get(
                    "HTTP_USER_AGENT", ""
                ),  # Obtendrá el navegador
            )

            # Redirigir al dashboard (o a la página de cambio de contraseña si es necesario, el middleware se encargará)
            return redirect("App_LUMINOVA:dashboard")
        else:
            # Si las credenciales son inválidas, mostrar un error
            messages.error(request, "Usuario o contraseña incorrectos.")

    # Si es una petición GET, simplemente mostrar la página de login
    return render(request, "login.html")


def custom_logout_view(request):
    """
    Gestiona el cierre de sesión y registra el evento en la auditoría ANTES de desloguear.
    """
    user = request.user

    # Registrar el evento de cierre de sesión con toda la información disponible
    AuditoriaAcceso.objects.create(
        usuario=user,
        accion="Cierre de sesión",
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    # Llamar a la función de logout de Django para limpiar la sesión
    auth_logout_function(request)

    # Opcional: mostrar un mensaje de que cerró sesión correctamente
    messages.info(request, "Has cerrado sesión exitosamente.")

    # Redirigir a la página de login
    return redirect("App_LUMINOVA:login")


@login_required
def dashboard_view(request):
    # --- 1. Tarjeta: Acciones Urgentes ---
    # Contamos OPs cuyo estado refleje un problema o pausa por incidencia
    # estados_problematicos_op = ['Producción con Problemas', 'Pausada']
    ops_con_problemas_reportados_count = (
        Reportes.objects.filter(resuelto=False, orden_produccion_asociada__isnull=False)
        .values("orden_produccion_asociada_id")
        .distinct()
        .count()
    )

    solicitudes_insumos_pendientes = OrdenProduccion.objects.filter(
        estado_op__nombre__iexact="Insumos Solicitados"
    ).count()
    ocs_para_aprobar = Orden.objects.filter(tipo="compra", estado="BORRADOR").count()

    # --- 2. Tarjeta: Stock Crítico ---
    UMBRAL_STOCK_BAJO = 15000
    insumos_criticos_query = Insumo.objects.filter(
        stock__lt=UMBRAL_STOCK_BAJO
    ).order_by("stock")[:5]
    insumos_criticos_con_porcentaje = []
    for insumo in insumos_criticos_query:
        porcentaje_stock = (
            int((insumo.stock / UMBRAL_STOCK_BAJO) * 100)
            if UMBRAL_STOCK_BAJO > 0
            else 0
        )
        insumos_criticos_con_porcentaje.append(
            {"insumo": insumo, "porcentaje_stock": min(100, porcentaje_stock)}
        )

    # --- 3. Tarjeta: Rendimiento de Producción ---
    hace_30_dias = timezone.now() - timedelta(days=30)
    ops_completadas_recientemente = OrdenProduccion.objects.filter(
        estado_op__nombre__iexact="Completada", fecha_fin_real__gte=hace_30_dias
    )
    total_luminarias_ensambladas = (
        ops_completadas_recientemente.aggregate(total=Sum("cantidad_a_producir"))[
            "total"
        ]
        or 0
    )
    total_ops_completadas = ops_completadas_recientemente.count()
    ops_a_tiempo = ops_completadas_recientemente.filter(
        fecha_fin_real__date__lte=F("fecha_fin_planificada")
    ).count()
    ops_con_retraso = total_ops_completadas - ops_a_tiempo
    tasa_cumplimiento = (
        (ops_a_tiempo / total_ops_completadas * 100) if total_ops_completadas > 0 else 0
    )

    # --- 4. Tarjeta: Actividad Reciente ---
    try:
        ultima_ov = OrdenVenta.objects.latest("fecha_creacion")
    except OrdenVenta.DoesNotExist:
        ultima_ov = None
    try:
        ultima_op_completada = OrdenProduccion.objects.filter(
            estado_op__nombre__iexact="Completada"
        ).latest("fecha_fin_real")
    except OrdenProduccion.DoesNotExist:
        ultima_op_completada = None
    try:
        ultimo_reporte = Reportes.objects.latest("fecha")
    except Reportes.DoesNotExist:
        ultimo_reporte = None

    context = {
        "ops_con_problemas_count": ops_con_problemas_reportados_count,
        "solicitudes_insumos_pendientes_count": solicitudes_insumos_pendientes,
        "ocs_para_aprobar_count": ocs_para_aprobar,
        "insumos_criticos_list": insumos_criticos_con_porcentaje,
        "umbral_stock_bajo": UMBRAL_STOCK_BAJO,
        "total_luminarias_ensambladas": total_luminarias_ensambladas,
        "ops_a_tiempo": ops_a_tiempo,
        "ops_con_retraso": ops_con_retraso,
        "tasa_cumplimiento": tasa_cumplimiento,
        "ultima_ov": ultima_ov,
        "ultima_op_completada": ultima_op_completada,
        "ultimo_reporte": ultimo_reporte,
    }
    return render(request, "admin/dashboard.html", context)


# --- ADMINISTRATOR VIEWS ---
@login_required
@user_passes_test(es_admin)
def lista_usuarios(request):
    usuarios = (
        User.objects.filter(is_superuser=False)
        .prefetch_related("groups")
        .order_by("id")
    )
    context = {"usuarios": usuarios, "titulo_seccion": "Gestión de Usuarios"}
    return render(request, "admin/usuarios.html", context)


@login_required
@user_passes_test(es_admin)
def crear_usuario(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        rol_name = request.POST.get("rol")
        estado_str = request.POST.get("estado")

        # --- Se utiliza la contraseña por defecto definida en settings.py ---
        password = settings.DEFAULT_PASSWORD_FOR_NEW_USERS

        # --- Validaciones básicas ---
        if User.objects.filter(username=username).exists():
            messages.error(
                request, f"El nombre de usuario '{username}' ya está en uso."
            )
            return redirect("App_LUMINOVA:lista_usuarios")

        if not username or not email or not rol_name or not estado_str:
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect("App_LUMINOVA:lista_usuarios")

        try:
            # La creación del usuario y la asignación de grupo ocurren dentro de una transacción
            # para asegurar que todo se complete correctamente o no se haga nada.

            user = User.objects.create_user(
                username=username, email=email, password=password
            )
            user.is_active = estado_str == "Activo"

            # Asignar el rol (grupo)
            try:
                group = Group.objects.get(name=rol_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                # Si el grupo no existe, la transacción hará rollback y el usuario no se creará.
                messages.error(
                    request,
                    f"El rol '{rol_name}' no existe. No se pudo crear el usuario.",
                )
                raise Exception("Rol no existente")  # Forzar rollback de la transacción

            user.save()

            # --- Marcar al usuario para que cambie su contraseña en el primer login ---
            PasswordChangeRequired.objects.create(user=user)

            messages.success(
                request,
                f"Usuario '{user.username}' creado exitosamente. La contraseña por defecto es: '{password}'",
            )

        except DjangoIntegrityError as e:
            # Captura errores de unicidad (por ejemplo, email duplicado si es unique)
            messages.error(
                request,
                f"Error de integridad al crear el usuario. Es posible que el email ya esté en uso. Detalle: {e}",
            )
        except Exception as e:
            # Captura cualquier otro error, como el de "Rol no existente"
            if "Rol no existente" not in str(e):
                messages.error(request, f"Error inesperado al crear usuario: {e}")

    # Redirige a la lista de usuarios en cualquier caso (éxito, error, o si no es POST)
    return redirect("App_LUMINOVA:lista_usuarios")


@login_required
def change_password_view(request):
    """
    Vista para que el usuario cambie su contraseña.
    Es forzado por el middleware si es su primer login.
    """
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)

            PasswordChangeRequired.objects.filter(user=request.user).delete()

            messages.success(
                request,
                "¡Tu contraseña ha sido actualizada exitosamente! Ya puedes navegar por el sitio.",
            )
            return redirect("App_LUMINOVA:dashboard")
        else:
            # --- CAMBIO AQUÍ: También modificar el form con errores ---
            form.fields["old_password"].widget.attrs[
                "autocomplete"
            ] = "current-password"
            form.fields["new_password1"].widget.attrs["autocomplete"] = "new-password"
            form.fields["new_password2"].widget.attrs["autocomplete"] = "new-password"
            messages.error(request, "Por favor, corrige los errores a continuación.")
    else:
        if not PasswordChangeRequired.objects.filter(user=request.user).exists():
            return redirect("App_LUMINOVA:dashboard")

        form = PasswordChangeForm(request.user)
        # --- CAMBIO AQUÍ: Modificar el form antes de renderizarlo ---
        form.fields["old_password"].widget.attrs["autocomplete"] = "current-password"
        form.fields["new_password1"].widget.attrs["autocomplete"] = "new-password"
        form.fields["new_password2"].widget.attrs["autocomplete"] = "new-password"

    context = {"form": form}
    return render(request, "change_password.html", context)


@login_required
@user_passes_test(es_admin)
@transaction.atomic
@require_POST
def editar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if request.method == "POST":
        usuario.username = request.POST.get("username", usuario.username)
        usuario.email = request.POST.get("email", usuario.email)
        # Actualizar rol
        rol_name = request.POST.get("rol")
        usuario.groups.clear()
        if rol_name:
            try:
                group = Group.objects.get(name=rol_name)
                usuario.groups.add(group)
            except Group.DoesNotExist:
                messages.error(request, f"El rol '{rol_name}' no existe.")

        # Actualizar estado
        estado_str = request.POST.get("estado")
        if estado_str:
            usuario.is_active = estado_str == "Activo"

        usuario.save()
        messages.success(
            request, f"Usuario '{usuario.username}' actualizado exitosamente."
        )
        return redirect("App_LUMINOVA:lista_usuarios")
    return redirect("App_LUMINOVA:lista_usuarios")  # Si no es POST


@login_required
@user_passes_test(es_admin)
@transaction.atomic
@require_POST
def eliminar_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    if usuario == request.user:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
        return redirect("App_LUMINOVA:lista_usuarios")
    try:
        nombre_usuario = usuario.username
        usuario.delete()
        messages.success(request, f"Usuario '{nombre_usuario}' eliminado exitosamente.")
    except Exception as e:
        messages.error(request, f"Error al eliminar usuario: {str(e)}")
    return redirect("App_LUMINOVA:lista_usuarios")


@login_required
def roles_permisos_view(request):
    roles = (
        Group.objects.all()
        .select_related("descripcion_extendida")
        .prefetch_related("permissions")
        .order_by("name")
    )
    context = {"roles": roles, "titulo_seccion": "Gestión de Roles y Permisos"}
    return render(request, "admin/roles_permisos.html", context)


@login_required
def auditoria_view(request):
    auditorias = AuditoriaAcceso.objects.select_related("usuario").order_by(
        "-fecha_hora"
    )

    from django.core.paginator import Paginator

    paginator = Paginator(auditorias, 25)  # 25 registros por página
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "auditorias": auditorias,  # O 'page_obj': page_obj si usas paginación
        "titulo_seccion": "Auditoría de Acceso",
    }
    return render(request, "admin/auditoria.html", context)


# --- AJAX VIEWS FOR ROLES & PERMISSIONS ---
@login_required
@user_passes_test(es_admin)
@require_POST
def crear_rol_ajax(request):
    form = RolForm(request.POST)
    if form.is_valid():
        nombre_rol = form.cleaned_data["nombre"]
        descripcion_rol = form.cleaned_data["descripcion"]
        try:
            with transaction.atomic():  # Para asegurar que ambas creaciones ocurran o ninguna
                nuevo_grupo = Group.objects.create(name=nombre_rol)
                if descripcion_rol:
                    RolDescripcion.objects.create(
                        group=nuevo_grupo, descripcion=descripcion_rol
                    )

                return JsonResponse(
                    {
                        "success": True,
                        "rol": {
                            "id": nuevo_grupo.id,
                            "nombre": nuevo_grupo.name,
                            "descripcion": descripcion_rol,
                        },
                    }
                )
        except Exception as e:
            return JsonResponse({"success": False, "errors": {"__all__": [str(e)]}})
    else:
        return JsonResponse({"success": False, "errors": form.errors})


@login_required
@user_passes_test(es_admin)
@require_GET
def get_rol_data_ajax(request):
    rol_id = request.GET.get("rol_id")
    try:
        grupo = Group.objects.get(id=rol_id)
        descripcion_extendida = ""
        if hasattr(grupo, "descripcion_extendida") and grupo.descripcion_extendida:
            descripcion_extendida = grupo.descripcion_extendida.descripcion

        return JsonResponse(
            {
                "success": True,
                "rol": {
                    "id": grupo.id,
                    "nombre": grupo.name,
                    "descripcion": descripcion_extendida,
                },
            }
        )
    except Group.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Rol no encontrado."}, status=404
        )


@login_required
@user_passes_test(es_admin)
@require_POST
def editar_rol_ajax(request):
    rol_id = request.POST.get("rol_id")  # rol_id viene del form
    try:
        grupo_a_editar = Group.objects.get(id=rol_id)
    except Group.DoesNotExist:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Rol no encontrado."]}},
            status=404,
        )

    form = RolForm(
        request.POST, initial={"rol_id": rol_id}
    )  # Pasar rol_id para validación de unicidad

    if form.is_valid():
        nombre_rol = form.cleaned_data["nombre"]
        descripcion_rol = form.cleaned_data["descripcion"]
        try:
            with transaction.atomic():
                grupo_a_editar.name = nombre_rol
                grupo_a_editar.save()

                desc_obj, created = RolDescripcion.objects.get_or_create(
                    group=grupo_a_editar
                )
                desc_obj.descripcion = descripcion_rol
                desc_obj.save()

            return JsonResponse(
                {
                    "success": True,
                    "rol": {
                        "id": grupo_a_editar.id,
                        "nombre": grupo_a_editar.name,
                        "descripcion": descripcion_rol,
                    },
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "errors": {"__all__": [str(e)]}})
    else:
        return JsonResponse({"success": False, "errors": form.errors})


@login_required
@require_POST
def eliminar_rol_ajax(request):
    import json

    try:
        data = json.loads(request.body)
        rol_id = data.get("rol_id")
        grupo = Group.objects.get(id=rol_id)

        if grupo.user_set.exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": "No se puede eliminar el rol porque tiene usuarios asignados.",
                },
                status=400,
            )

        grupo.delete()
        return JsonResponse({"success": True})
    except Group.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Rol no encontrado."}, status=404
        )
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido."}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@user_passes_test(es_admin)
@require_GET
def get_permisos_rol_ajax(request):
    rol_id = request.GET.get("rol_id")
    try:
        rol = Group.objects.get(id=rol_id)
        permisos_del_rol_ids = list(rol.permissions.values_list("id", flat=True))

        todos_los_permisos = Permission.objects.select_related("content_type").all()
        permisos_data = []
        for perm in todos_los_permisos:
            permisos_data.append(
                {
                    "id": perm.id,
                    "name": perm.name,
                    "codename": perm.codename,
                    "content_type_app_label": perm.content_type.app_label,
                    "content_type_model": perm.content_type.model,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "todos_los_permisos": permisos_data,
                "permisos_del_rol": permisos_del_rol_ids,
            }
        )
    except Group.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Rol no encontrado."}, status=404
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@user_passes_test(es_admin)
@require_POST
def actualizar_permisos_rol_ajax(request):
    import json

    try:
        data = json.loads(request.body)
        rol_id = data.get("rol_id")
        permisos_ids_str = data.get("permisos_ids", [])  # Lista de IDs como strings
        permisos_ids = [int(pid) for pid in permisos_ids_str]

        rol = Group.objects.get(id=rol_id)

        # Actualizar permisos
        rol.permissions.set(permisos_ids)  # set() maneja agregar y quitar

        return JsonResponse({"success": True, "message": "Permisos actualizados."})
    except Group.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Rol no encontrado."}, status=404
        )
    except Permission.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Uno o más permisos no son válidos."},
            status=400,
        )
    except ValueError:
        return JsonResponse(
            {"success": False, "error": "IDs de permisos inválidos."}, status=400
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Datos JSON inválidos."}, status=400
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# --- VENTAS VIEWS ---
@login_required
def lista_clientes_view(request):
    if not es_admin_o_rol(request.user, ["ventas", "administrador"]):
        messages.error(request, "Acceso denegado.")
        return redirect("App_LUMINOVA:dashboard")

    clientes = Cliente.objects.all().order_by("nombre")
    form_para_crear = ClienteForm()  # Instancia para el modal de creación

    context = {
        "clientes_list": clientes,
        "cliente_form_crear": form_para_crear,  # Para el modal de creación
        "ClienteFormClass": ClienteForm,  # Pasamos la clase del formulario
        "titulo_seccion": "Gestión de Clientes",
    }
    return render(request, "ventas/ventas_clientes.html", context)


@login_required
@transaction.atomic
def crear_cliente_view(request):
    if not es_admin_o_rol(request.user, ["ventas", "administrador"]):
        messages.error(request, "Acción no permitida.")
        return redirect("App_LUMINOVA:lista_clientes")

    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Cliente creado exitosamente.")
            except DjangoIntegrityError:
                messages.error(
                    request, "Error: Un cliente con ese nombre o email ya existe."
                )
            except Exception as e:
                messages.error(request, f"Error inesperado al crear cliente: {e}")
            return redirect("App_LUMINOVA:lista_clientes")
        else:
            # Re-render con errores (para modales puede ser complejo, simplificamos)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(
                        request, f"{form.fields[field].label or field}: {error}"
                    )
            return redirect("App_LUMINOVA:lista_clientes")
    return redirect("App_LUMINOVA:lista_clientes")


# ... (editar_cliente_view y eliminar_cliente_view pueden permanecer similares a como estaban) ...
@login_required
@transaction.atomic
def editar_cliente_view(request, cliente_id):
    if not es_admin_o_rol(request.user, ["ventas", "administrador"]):
        messages.error(request, "Acción no permitida.")
        return redirect("App_LUMINOVA:lista_clientes")
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Cliente actualizado exitosamente.")
            except DjangoIntegrityError:
                messages.error(
                    request, "Error: Otro cliente ya tiene ese nombre o email."
                )
            except Exception as e:
                messages.error(request, f"Error inesperado al actualizar cliente: {e}")
            return redirect("App_LUMINOVA:lista_clientes")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(
                        request, f"{form.fields[field].label or field}: {error}"
                    )
            return redirect("App_LUMINOVA:lista_clientes")
    return redirect("App_LUMINOVA:lista_clientes")


@login_required
@transaction.atomic
def eliminar_cliente_view(request, cliente_id):
    if not es_admin_o_rol(request.user, ["ventas", "administrador"]):
        messages.error(request, "Acción no permitida.")
        return redirect("App_LUMINOVA:lista_clientes")
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == "POST":
        try:
            nombre_cliente = cliente.nombre
            cliente.delete()
            messages.success(
                request, f'Cliente "{nombre_cliente}" eliminado exitosamente.'
            )
        except Exception as e:
            messages.error(
                request,
                f"Error al eliminar cliente: {e}. Verifique que no tenga órdenes asociadas.",
            )
    return redirect("App_LUMINOVA:lista_clientes")


@login_required
def ventas_lista_ov_view(request):
    ordenes_de_venta_query = (
        OrdenVenta.objects.select_related("cliente")
        .prefetch_related(
            "items_ov__producto_terminado",
            Prefetch(
                "ops_generadas",
                queryset=OrdenProduccion.objects.select_related(
                    "estado_op", "producto_a_producir"
                )
                .prefetch_related(
                    Prefetch(
                        "reportes_incidencia",
                        queryset=Reportes.objects.select_related(
                            "reportado_por", "sector_reporta"
                        ).order_by("-fecha"),
                    )
                )
                .order_by("numero_op"),
                to_attr="lista_ops_con_reportes_y_estado",  # Usamos un nombre claro para el resultado del prefetch
            ),
        )
        .order_by("-fecha_creacion")
    )

    # Procesar para añadir la bandera
    ordenes_list_con_info_reporte = []
    for ov in ordenes_de_venta_query:
        ov.tiene_algun_reporte_asociado = False  # Inicializar bandera
        if hasattr(
            ov, "lista_ops_con_reportes_y_estado"
        ):  # Verificar que el prefetch funcionó
            for op in ov.lista_ops_con_reportes_y_estado:
                if (
                    op.reportes_incidencia.all().exists()
                ):  # Si alguna de las OPs de esta OV tiene reportes...
                    ov.tiene_algun_reporte_asociado = True
                    break  # Salimos del bucle interior, ya sabemos que hay al menos un reporte.
        ordenes_list_con_info_reporte.append(ov)

    context = {
        "ordenes_list": ordenes_list_con_info_reporte,  # Pasamos la lista procesada a la plantilla
        "titulo_seccion": "Órdenes de Venta",
    }
    return render(request, "ventas/ventas_lista_ov.html", context)


@login_required
@transaction.atomic
def ventas_crear_ov_view(request):
    """
    Gestiona la creación de una nueva Orden de Venta y sus ítems asociados.
    Al crearse exitosamente, también genera las Órdenes de Producción correspondientes.
    """
    if not es_admin_o_rol(request.user, ["ventas", "administrador"]):
        messages.error(request, "Acción no permitida.")
        return redirect("App_LUMINOVA:ventas_lista_ov")

    if request.method == "POST":
        form_ov = OrdenVentaForm(request.POST, prefix="ov")
        formset_items = ItemOrdenVentaFormSetCreacion(request.POST, prefix="items")

        if form_ov.is_valid() and formset_items.is_valid():
            try:
                ov_instance = form_ov.save(commit=False)
                ov_instance.estado = "PENDIENTE"
                ov_instance.save() # Se necesita ID para la relación

                items_a_procesar = []
                total_ov = 0
                for form in formset_items:
                    if form.is_valid() and form.cleaned_data and not form.cleaned_data.get('DELETE'):
                        item = form.save(commit=False)
                        item.orden_venta = ov_instance
                        item.subtotal = item.cantidad * item.producto_terminado.precio_unitario
                        total_ov += item.subtotal
                        items_a_procesar.append(item)
                
                if not items_a_procesar:
                    raise ValueError("Se debe añadir al menos un producto a la orden.")

                ItemOrdenVenta.objects.bulk_create(items_a_procesar)
                ov_instance.total_ov = total_ov
                ov_instance.save(update_fields=['total_ov'])

                estado_op_inicial = EstadoOrden.objects.get(nombre__iexact="Pendiente")
                
                ops_a_crear = []
                for item_procesado in items_a_procesar:
                    next_op_number = generar_siguiente_numero_documento(OrdenProduccion, 'OP', 'numero_op')
                    ops_a_crear.append(
                        OrdenProduccion(
                            numero_op=next_op_number,
                            orden_venta_origen=ov_instance,
                            producto_a_producir=item_procesado.producto_terminado,
                            cantidad_a_producir=item_procesado.cantidad,
                            estado_op=estado_op_inicial,
                        )
                    )
                OrdenProduccion.objects.bulk_create(ops_a_crear)

                messages.success(request, f'Orden de Venta "{ov_instance.numero_ov}" y sus OPs asociadas se crearon exitosamente.')
                return redirect('App_LUMINOVA:ventas_detalle_ov', ov_id=ov_instance.id)

            except EstadoOrden.DoesNotExist:
                 messages.error(request, "Error de configuración: El estado 'Pendiente' para OP no existe. No se pudo continuar.")
                 # La transacción se revertirá.
            except ValueError as e:
                messages.error(request, str(e))
                # La transacción se revertirá.
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado. Por favor, intente de nuevo. Detalle: {e}")
                logger.exception("Error grave en la creación de OV/OPs")
                # La transacción se revertirá.
    else: # GET
        initial_data = {'numero_ov': generar_siguiente_numero_documento(OrdenVenta, 'OV', 'numero_ov')}
        form_ov = OrdenVentaForm(prefix="ov", initial=initial_data)
        formset_items = ItemOrdenVentaFormSetCreacion(prefix="items", queryset=ItemOrdenVenta.objects.none())

    context = {
        'form_ov': form_ov,
        'formset_items': formset_items,
        'titulo_seccion': "Nueva Orden de Venta"
    }
    return render(request, "ventas/ventas_crear_ov.html", context)


@login_required
def ventas_detalle_ov_view(request, ov_id):
    orden_venta = get_object_or_404(
        OrdenVenta.objects.select_related("cliente").prefetch_related(
            "items_ov__producto_terminado",
            "ops_generadas__estado_op",  # Necesitamos el estado de cada OP
            "factura_asociada",
        ),
        id=ov_id,
    )

    factura_form = None
    puede_facturar = False
    detalle_cancelacion_factura = ""

    if not hasattr(orden_venta, "factura_asociada") or not orden_venta.factura_asociada:
        # Lógica para determinar si se puede facturar
        ops_asociadas = orden_venta.ops_generadas.all()
        if not ops_asociadas.exists() and orden_venta.estado == "CONFIRMADA":
            # Si no hay OPs (ej. productos solo de stock) y está confirmada, podría facturarse.
            # Esto depende de tu flujo si una OV puede no generar OPs.
            # Por ahora, asumimos que OVs CONFIRMADAS sin OPs son para productos ya en stock.
            puede_facturar = True  # O cambiar estado a LISTA_ENTREGA primero
        elif ops_asociadas.exists():
            ops_completadas = ops_asociadas.filter(
                estado_op__nombre__iexact="Completada"
            ).count()
            ops_canceladas = ops_asociadas.filter(
                estado_op__nombre__iexact="Cancelada"
            ).count()
            ops_totales = ops_asociadas.count()

            # Se puede facturar si todas las OPs no canceladas están completadas
            if ops_completadas + ops_canceladas == ops_totales and ops_completadas > 0:
                puede_facturar = True
                if ops_canceladas > 0:
                    detalle_cancelacion_factura = f"Nota: {ops_canceladas} orden(es) de producción asociada(s) fueron canceladas."
            elif (
                orden_venta.estado == "PRODUCCION_CON_PROBLEMAS"
                and ops_completadas > 0
                and (ops_completadas + ops_canceladas == ops_totales)
            ):
                # Caso específico donde la OV está con problemas pero hay partes completadas
                puede_facturar = True
                detalle_cancelacion_factura = f"Facturación parcial. Nota: {ops_canceladas} orden(es) de producción asociada(s) fueron canceladas."
            elif orden_venta.estado == "LISTA_ENTREGA":  # Ya está explícitamente lista
                puede_facturar = True

        if puede_facturar:
            factura_form = FacturaForm()
            # Si hay detalle de cancelación, podrías pasarlo al form o al contexto
            # para incluirlo en notas de la factura si el form lo permite.
            # form.fields['notas_factura'].initial = detalle_cancelacion_factura (si tuvieras ese campo)

    context = {
        "ov": orden_venta,
        "items_ov": orden_venta.items_ov.all(),
        "factura_form": factura_form,
        "puede_facturar": puede_facturar,  # Para la plantilla
        "detalle_cancelacion_factura": detalle_cancelacion_factura,  # Para la plantilla
        "titulo_seccion": f"Detalle Orden de Venta: {orden_venta.numero_ov}",
    }
    return render(request, "ventas/ventas_detalle_ov.html", context)


@login_required
@transaction.atomic
def ventas_generar_factura_view(request, ov_id):
    """
    Gestiona la creación de una factura para una Orden de Venta.
    Esta vista ahora solo genera la factura sin cambiar el estado final de la OV.
    El estado final a 'COMPLETADA' se gestiona desde el envío en depósito.
    """
    orden_venta = get_object_or_404(
        OrdenVenta.objects.prefetch_related(
            "items_ov__producto_terminado", "ops_generadas__estado_op"
        ),
        id=ov_id,
    )

    # 1. Verificar si ya existe una factura
    if hasattr(orden_venta, "factura_asociada") and orden_venta.factura_asociada:
        messages.warning(
            request,
            f"La factura para la OV {orden_venta.numero_ov} ya ha sido generada.",
        )
        return redirect("App_LUMINOVA:ventas_detalle_ov", ov_id=orden_venta.id)

    # 2. Verificar si la OV está en un estado que permite facturación
    #    La condición principal es que esté 'LISTA_ENTREGA'.
    puede_facturar_ahora = False
    if orden_venta.estado == "LISTA_ENTREGA":
        puede_facturar_ahora = True
    else:
        # Lógica de respaldo para casos donde el estado no se actualizó, pero las condiciones se cumplen.
        ops_asociadas = orden_venta.ops_generadas.all()
        if (
            not ops_asociadas.exists() and orden_venta.estado == "CONFIRMADA"
        ):  # OV de solo stock
            puede_facturar_ahora = True
        elif ops_asociadas.exists():
            ops_completadas_count = ops_asociadas.filter(
                estado_op__nombre__iexact="Completada"
            ).count()
            ops_canceladas_count = ops_asociadas.filter(
                estado_op__nombre__iexact="Cancelada"
            ).count()
            if ops_completadas_count > 0 and (
                ops_completadas_count + ops_canceladas_count == ops_asociadas.count()
            ):
                puede_facturar_ahora = (
                    True  # Todas las OPs están resueltas (completadas o canceladas)
                )

    if not puede_facturar_ahora:
        messages.error(
            request,
            f"La Orden de Venta {orden_venta.numero_ov} no está lista para ser facturada. Estado actual: '{orden_venta.get_estado_display()}'.",
        )
        return redirect("App_LUMINOVA:ventas_detalle_ov", ov_id=orden_venta.id)

    # 3. Procesar el formulario si es un método POST
    if request.method == "POST":
        form = FacturaForm(request.POST)
        if form.is_valid():
            try:
                factura = form.save(commit=False)
                factura.orden_venta = orden_venta
                # El total a facturar es el total de la OV, ya que solo se factura cuando todo está listo.
                factura.total_facturado = orden_venta.total_ov
                factura.fecha_emision = timezone.now()
                # El cliente se puede obtener de la OV, pero no es necesario guardarlo en la factura si no está en el modelo.
                # factura.cliente = orden_venta.cliente
                factura.save()

                # --- REGISTRO EN HISTORIAL ---
                from .models import (
                    HistorialOV,
                )  # Importación local para evitar importación circular

                HistorialOV.objects.create(
                    orden_venta=orden_venta,
                    descripcion=f"Se generó la factura N° {factura.numero_factura} por un total de ${factura.total_facturado:.2f}.",
                    tipo_evento="Facturado",
                    realizado_por=request.user,
                )

                # --- CORRECCIÓN CLAVE ---
                # YA NO CAMBIAMOS EL ESTADO DE LA OV A 'COMPLETADA' AQUÍ.
                # La OV permanece en 'LISTA_ENTREGA' hasta que se confirme el envío desde depósito.

                messages.success(
                    request,
                    f"Factura N° {factura.numero_factura} generada exitosamente para la OV {orden_venta.numero_ov}.",
                )
                return redirect("App_LUMINOVA:ventas_detalle_ov", ov_id=orden_venta.id)

            except DjangoIntegrityError:
                messages.error(
                    request,
                    f"Error: El número de factura '{form.cleaned_data.get('numero_factura')}' ya existe.",
                )
            except Exception as e:
                messages.error(
                    request, f"Ocurrió un error inesperado al generar la factura: {e}"
                )
                logger.exception(f"Error generando factura para OV {ov_id}")
        else:
            messages.error(
                request,
                "El formulario de la factura contiene errores. Por favor, inténtelo de nuevo.",
            )

    # Si la petición es GET o el formulario es inválido, redirigir de vuelta a la página de detalle.
    return redirect("App_LUMINOVA:ventas_detalle_ov", ov_id=orden_venta.id)


@login_required
@transaction.atomic
def ventas_editar_ov_view(request, ov_id):
    orden_venta = get_object_or_404(
        OrdenVenta.objects.prefetch_related(
            "ops_generadas__estado_op", "items_ov__producto_terminado"
        ),
        id=ov_id,
    )
    logger.info(
        f"Editando OV: {orden_venta.numero_ov}, Estado actual OV: {orden_venta.get_estado_display()}"
    )

    puede_editar_items_y_ops = True

    if orden_venta.estado in ["COMPLETADA", "CANCELADA"]:
        messages.warning(
            request,
            f"La Orden de Venta {orden_venta.numero_ov} está en estado '{orden_venta.get_estado_display()}' y no puede ser modificada.",
        )
        return redirect("App_LUMINOVA:ventas_detalle_ov", ov_id=orden_venta.id)

    if orden_venta.estado not in ["PENDIENTE", "CONFIRMADA"]:
        puede_editar_items_y_ops = False
        logger.info(
            f"Edición de ítems deshabilitada para OV {orden_venta.numero_ov} porque su estado es '{orden_venta.get_estado_display()}'."
        )

    if puede_editar_items_y_ops:
        estados_op_avanzados = [
            "insumos recibidos",
            "producción iniciada",
            "en proceso",
            "completada",
            "cancelada por producción",
        ]
        for op_asociada in orden_venta.ops_generadas.all():
            if (
                op_asociada.estado_op
                and op_asociada.estado_op.nombre.lower() in estados_op_avanzados
            ):
                puede_editar_items_y_ops = False
                messages.error(
                    request,
                    f"No se pueden modificar los ítems de la OV {orden_venta.numero_ov} porque la OP '{op_asociada.numero_op}' ya ha avanzado (Estado OP: {op_asociada.get_estado_op_display()}).",
                )
                break

    if request.method == "POST":
        form_ov = OrdenVentaForm(request.POST, instance=orden_venta, prefix="ov")

        if form_ov.is_valid():
            if puede_editar_items_y_ops:
                formset_items = ItemOrdenVentaFormSet(
                    request.POST, instance=orden_venta, prefix="items"
                )
                if formset_items.is_valid():
                    try:
                        ov_actualizada = form_ov.save(commit=False)

                        ops_a_revisar_o_eliminar = orden_venta.ops_generadas.filter(
                            Q(estado_op__nombre__iexact="Pendiente")
                            | Q(estado_op__nombre__iexact="Insumos Solicitados")
                        )
                        if ops_a_revisar_o_eliminar.exists():
                            logger.info(
                                f"Eliminando {ops_a_revisar_o_eliminar.count()} OPs en estado inicial para OV {ov_actualizada.numero_ov}."
                            )
                            ops_a_revisar_o_eliminar.delete()
                            messages.warning(
                                request,
                                "Órdenes de Producción asociadas (en estado inicial) han sido eliminadas y se regenerarán según los nuevos ítems.",
                            )

                        formset_items.save()
                        ov_actualizada.actualizar_total()
                        ov_actualizada.save()

                        estado_op_inicial = EstadoOrden.objects.filter(
                            nombre__iexact="Pendiente"
                        ).first()
                        if not estado_op_inicial:
                            messages.error(
                                request,
                                "Error crítico: Estado 'Pendiente' para OP no configurado. No se pudieron regenerar OPs.",
                            )
                        else:
                            # --- INICIO DE LA CORRECCIÓN ---
                            for item_guardado in ov_actualizada.items_ov.all():
                                # Lógica correcta para generar número de OP secuencial
                                next_op_number = generar_siguiente_numero_documento(OrdenProduccion, 'OP', 'numero_op')

                                OrdenProduccion.objects.create(
                                    numero_op=next_op_number,
                                    orden_venta_origen=ov_actualizada,
                                    producto_a_producir=item_guardado.producto_terminado,
                                    cantidad_a_producir=item_guardado.cantidad,
                                    estado_op=estado_op_inicial,
                                )
                                messages.info(
                                    request,
                                    f'Nueva OP "{next_op_number}" generada para "{item_guardado.producto_terminado.descripcion}".',
                                )
                            # --- FIN DE LA CORRECCIÓN ---

                        messages.success(
                            request,
                            f"Orden de Venta '{ov_actualizada.numero_ov}' actualizada exitosamente.",
                        )
                        return redirect(
                            "App_LUMINOVA:ventas_detalle_ov", ov_id=ov_actualizada.id
                        )

                    except Exception as e:
                        messages.error(request, f"Error inesperado al guardar: {e}")
                        logger.exception(f"Error al editar y guardar OV {ov_id}:")
                else:
                    messages.error(
                        request,
                        "Por favor, corrija los errores en los ítems de la orden.",
                    )
            else:
                try:
                    ov_actualizada = form_ov.save()
                    messages.success(
                        request,
                        f"Datos generales de la Orden de Venta '{ov_actualizada.numero_ov}' actualizados.",
                    )
                    return redirect(
                        "App_LUMINOVA:ventas_detalle_ov", ov_id=ov_actualizada.id
                    )
                except Exception as e:
                    messages.error(
                        request, f"Error al guardar los datos generales: {e}"
                    )
        else:
            messages.error(
                request,
                "Por favor, corrija los errores en los datos generales de la orden.",
            )
            if puede_editar_items_y_ops:
                formset_items = ItemOrdenVentaFormSet(
                    request.POST, instance=orden_venta, prefix="items"
                )
            else:
                formset_items = ItemOrdenVentaFormSet(
                    instance=orden_venta, prefix="items"
                )

    else:  # GET request
        form_ov = OrdenVentaForm(instance=orden_venta, prefix="ov")
        formset_items = ItemOrdenVentaFormSet(instance=orden_venta, prefix="items")

    context = {
        "form_ov": form_ov,
        "formset_items": formset_items,
        "orden_venta": orden_venta,
        "titulo_seccion": f"Editar Orden de Venta: {orden_venta.numero_ov}",
        "puede_editar_items": puede_editar_items_y_ops,
    }
    return render(request, "ventas/ventas_editar_ov.html", context)


@login_required
@transaction.atomic
@require_POST  # Esta acción solo debe ser por POST desde el modal
def ventas_cancelar_ov_view(request, ov_id):
    # if not es_admin_o_rol(request.user, ['ventas', 'administrador']):
    #     messages.error(request, "Acción no permitida.")
    #     return redirect('App_LUMINOVA:ventas_lista_ov')

    orden_venta = get_object_or_404(OrdenVenta, id=ov_id)

    if orden_venta.estado in ["COMPLETADA", "CANCELADA"]:
        messages.warning(
            request,
            f"La Orden de Venta {orden_venta.numero_ov} ya está {orden_venta.get_estado_display()} y no puede cancelarse nuevamente.",
        )
        return redirect("App_LUMINOVA:ventas_detalle_ov", ov_id=ov_id)

    estado_op_cancelada = EstadoOrden.objects.filter(nombre__iexact="Cancelada").first()
    estado_op_completada = EstadoOrden.objects.filter(
        nombre__iexact="Completada"
    ).first()  # O 'Terminado'

    if not estado_op_cancelada:
        messages.error(
            request, "Error crítico: El estado 'Cancelada' para OP no está configurado."
        )
        return redirect("App_LUMINOVA:ventas_detalle_ov", ov_id=ov_id)

    ops_asociadas = orden_venta.ops_generadas.all()
    for op in ops_asociadas:
        if (
            op.estado_op != estado_op_completada
        ):  # No cancelar OPs que ya se completaron
            op.estado_op = estado_op_cancelada
            op.save(update_fields=["estado_op"])
            messages.info(
                request,
                f"Orden de Producción {op.numero_op} asociada ha sido cancelada.",
            )
        else:
            messages.warning(
                request,
                f"Orden de Producción {op.numero_op} ya está completada y no se cancelará.",
            )

    orden_venta.estado = "CANCELADA"
    orden_venta.save(update_fields=["estado"])
    messages.success(
        request, f"Orden de Venta {orden_venta.numero_ov} ha sido cancelada."
    )

    return redirect("App_LUMINOVA:ventas_lista_ov")


# --- COMPRAS VIEWS ---
@login_required
def compras_lista_oc_view(request):
    # if not es_admin_o_rol(request.user, ['compras', 'administrador']):
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    # Filtrar órdenes de tipo 'compra'
    # Asumiendo que tu modelo Orden tiene un campo 'tipo' y 'proveedor'
    ordenes_compra = (
        Orden.objects.filter(tipo="compra")
        .select_related(
            "proveedor",  # Si el campo se llama 'proveedor' en el modelo Orden
            "insumo_principal",  # Si el campo se llama 'insumo' en el modelo Orden
        )
        .order_by("-fecha_creacion")
    )

    # Para un futuro modal de creación de OC
    # from .forms import OrdenCompraForm # Necesitarás crear este formulario
    # form_oc = OrdenCompraForm()
    # oc_count = Orden.objects.filter(tipo='compra').count()
    # next_oc_number = f"OC-{str(oc_count + 1).zfill(4)}"
    # form_oc.fields['numero_orden'].initial = next_oc_number

    context = {
        "ordenes_list": ordenes_compra,  # Nombre genérico para la plantilla
        "titulo_seccion": "Listado de Órdenes de Compra",
        # 'form_orden': form_oc, # Para el modal de creación
        # 'tipo_orden_actual': 'compra',
    }
    # Necesitarás una plantilla para esto, ej. 'compras/compras_lista_oc.html'
    return render(request, "compras/compras_lista_oc.html", context)


@login_required
def compras_desglose_view(request):
    logger.info("--- compras_desglose_view: INICIO ---")

    UMBRAL_STOCK_BAJO_INSUMOS = 15000

    # --- LÓGICA CORREGIDA ---
    # Un insumo necesita gestión si su OC o no existe, o si está SOLAMENTE en estado 'BORRADOR'.
    # Si ya está 'APROBADA' o más allá, el equipo de compras ya hizo su parte principal.

    # 1. Obtenemos los IDs de insumos que ya tienen una OC "en firme" (es decir, post-borrador)
    ESTADOS_OC_POST_BORRADOR = [
        "APROBADA",
        "ENVIADA_PROVEEDOR",
        "EN_TRANSITO",
        "RECIBIDA_PARCIAL",
        "RECIBIDA_TOTAL",
        "COMPLETADA",
    ]
    insumos_ya_gestionados_ids = (
        Orden.objects.filter(
            tipo="compra",
            estado__in=ESTADOS_OC_POST_BORRADOR,
            insumo_principal__isnull=False,
        )
        .values_list("insumo_principal_id", flat=True)
        .distinct()
    )

    logger.info(
        f"IDs de insumos que ya tienen OC post-borrador: {list(insumos_ya_gestionados_ids)}"
    )

    # 2. Buscamos insumos críticos, EXCLUYENDO los que ya están gestionados.
    #    La lista resultante solo contendrá insumos sin OC o con OC en 'BORRADOR'.
    insumos_criticos_para_gestionar = (
        Insumo.objects.filter(stock__lt=UMBRAL_STOCK_BAJO_INSUMOS)
        .exclude(id__in=insumos_ya_gestionados_ids)
        .select_related("categoria")
        .order_by("categoria__nombre", "stock", "descripcion")
    )

    logger.info(
        f"Insumos críticos que requieren acción de Compras: {insumos_criticos_para_gestionar.count()}"
    )

    # La variable pasada a la plantilla necesita un nombre consistente
    context = {
        "insumos_criticos_list_con_estado": insumos_criticos_para_gestionar,
        "umbral_stock_bajo": UMBRAL_STOCK_BAJO_INSUMOS,
        "titulo_seccion": "Gestionar Compra por Stock Bajo",
    }
    return render(request, "compras/compras_desglose.html", context)


@login_required
def compras_seguimiento_view(request):
    """
    Muestra las Órdenes de Compra que ya fueron gestionadas y están
    en proceso de envío o recepción.
    """
    estados_en_seguimiento = ["ENVIADA_PROVEEDOR", "EN_TRANSITO", "RECIBIDA_PARCIAL"]
    ordenes = (
        Orden.objects.filter(tipo="compra", estado__in=estados_en_seguimiento)
        .select_related("proveedor")
        .order_by("-fecha_creacion")
    )

    context = {
        "ordenes_en_seguimiento": ordenes,
        "titulo_seccion": "Seguimiento de Órdenes de Compra",
    }
    return render(request, "compras/seguimiento.html", context)


@login_required
def compras_tracking_pedido_view(
    request, oc_id
):  # Cambiado para usar ID, es más robusto
    """
    Muestra la página de tracking visual para una OC específica.
    """
    orden_compra = get_object_or_404(
        Orden.objects.select_related("proveedor"),
        id=oc_id,  # Buscamos por ID
        tipo="compra",
    )
    context = {
        "orden_compra": orden_compra,
    }
    return render(request, "compras/compras_tracking_pedido.html", context)


@login_required
def compras_desglose_detalle_oc_view(request, numero_orden_desglose):
    # Aquí mostrarías el detalle de una OC específica de la vista de desglose
    # orden_compra = get_object_or_404(Orden, numero_orden=numero_orden_desglose, tipo='compra')
    # Aquí podrías listar los insumos si una OC puede tener múltiples.
    context = {
        # 'orden': orden_compra,
        "numero_orden_desglose": numero_orden_desglose,  # Pasar para mostrar en la plantilla
        "titulo_seccion": f"Detalle Desglose OC: {numero_orden_desglose}",
    }
    return render(
        request, "compras/compras_desglose_detalle.html", context
    )  # Nombre de plantilla sugerido


@login_required
def compras_seleccionar_proveedor_para_insumo_view(request, insumo_id):
    insumo_objetivo = get_object_or_404(
        Insumo.objects.select_related("categoria"), id=insumo_id
    )
    logger.info(
        f"Seleccionando proveedor para insumo: {insumo_objetivo.descripcion} (ID: {insumo_id})"
    )

    if request.method == "POST":
        oferta_id_seleccionada = request.POST.get("oferta_proveedor_id")
        proveedor_fallback_id_seleccionado = request.POST.get("proveedor_fallback_id")

        proveedor_id_final_para_oc = None  # Renombrado para claridad

        if oferta_id_seleccionada:
            try:
                oferta = OfertaProveedor.objects.get(
                    id=oferta_id_seleccionada, insumo_id=insumo_id
                )  # Asegurar que la oferta sea para este insumo
                proveedor_id_final_para_oc = oferta.proveedor.id
                logger.info(
                    f"Oferta ID {oferta_id_seleccionada} seleccionada. Proveedor ID: {proveedor_id_final_para_oc}"
                )
            except OfertaProveedor.DoesNotExist:
                messages.error(
                    request,
                    "La oferta seleccionada no es válida o no corresponde al insumo.",
                )
                return redirect(
                    "App_LUMINOVA:compras_seleccionar_proveedor_para_insumo",
                    insumo_id=insumo_id,
                )
        elif proveedor_fallback_id_seleccionado:
            proveedor_id_final_para_oc = proveedor_fallback_id_seleccionado
            logger.info(
                f"Proveedor fallback ID {proveedor_fallback_id_seleccionado} seleccionado."
            )
        else:
            messages.error(request, "Debe seleccionar un proveedor u oferta.")
            return redirect(
                "App_LUMINOVA:compras_seleccionar_proveedor_para_insumo",
                insumo_id=insumo_id,
            )

        # Redirigir a la vista de creación de OC con los nombres de parámetros que espera la URL pattern
        logger.info(
            f"Redirigiendo a crear OC con insumo_id={insumo_id} y proveedor_id={proveedor_id_final_para_oc}"
        )
        return redirect(
            "App_LUMINOVA:compras_crear_oc_desde_insumo_y_proveedor",
            insumo_id=insumo_id,  # <--- USA 'insumo_id'
            proveedor_id=proveedor_id_final_para_oc,
        )  # <--- USA 'proveedor_id'
    # ... (resto de la lógica GET) ...
    # ... (código de la lógica GET de la vista) ...
    ofertas = (
        OfertaProveedor.objects.filter(insumo_id=insumo_id)
        .select_related("proveedor")
        .order_by("precio_unitario_compra", "tiempo_entrega_estimado_dias")
    )
    insumo_objetivo = get_object_or_404(
        Insumo, id=insumo_id
    )  # Necesario para el contexto GET

    proveedores_fallback = []
    if not ofertas.exists():
        proveedores_fallback = Proveedor.objects.all().order_by("nombre")[:5]

    UMBRAL_STOCK_BAJO_INSUMOS = 15000
    context = {
        "insumo_objetivo": insumo_objetivo,
        "ofertas_proveedores": ofertas,
        "proveedores_fallback": proveedores_fallback,
        "titulo_seccion": f"Seleccionar Oferta para: {insumo_objetivo.descripcion}",
        "umbral_stock_bajo": UMBRAL_STOCK_BAJO_INSUMOS,
    }
    return render(request, "compras/compras_seleccionar_proveedor.html", context)


@login_required
def compras_detalle_oc_view(request, oc_id):
    # if not es_admin_o_rol(request.user, ['compras', 'administrador', 'deposito']): # Ajusta permisos
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:compras_lista_oc')

    orden_compra = get_object_or_404(
        Orden.objects.select_related("proveedor", "insumo_principal__categoria"),
        id=oc_id,
        tipo="compra",  # Asegurar que sea una OC
    )

    # Si tuvieras ItemsOrdenCompra, los prefetch aquí:
    # .prefetch_related('items_oc__insumo')

    context = {
        "oc": orden_compra,
        "titulo_seccion": f"Detalle OC: {orden_compra.numero_orden}",
    }
    return render(request, "compras/compras_detalle_oc.html", context)


@login_required
@transaction.atomic
def compras_crear_oc_view(request, insumo_id=None, proveedor_id=None):
    insumo_preseleccionado_obj = None
    proveedor_preseleccionado_obj = None
    initial_data = {}
    form_kwargs = {}

    if insumo_id:
        insumo_preseleccionado_obj = get_object_or_404(Insumo, id=insumo_id)
        initial_data['insumo_principal'] = insumo_preseleccionado_obj
        form_kwargs['insumo_fijado'] = insumo_preseleccionado_obj

        UMBRAL_STOCK_BAJO = 15000
        cantidad_sugerida = max(10, UMBRAL_STOCK_BAJO - insumo_preseleccionado_obj.stock)
        initial_data['cantidad_principal'] = cantidad_sugerida

        if proveedor_id:
            proveedor_preseleccionado_obj = get_object_or_404(Proveedor, id=proveedor_id)
            initial_data['proveedor'] = proveedor_preseleccionado_obj
            oferta_seleccionada = OfertaProveedor.objects.filter(insumo=insumo_preseleccionado_obj, proveedor=proveedor_preseleccionado_obj).first()
            if oferta_seleccionada:
                initial_data['precio_unitario_compra'] = oferta_seleccionada.precio_unitario_compra
                if oferta_seleccionada.tiempo_entrega_estimado_dias is not None:
                    try:
                        dias = int(oferta_seleccionada.tiempo_entrega_estimado_dias)
                        fecha_estimada = timezone.now().date() + timedelta(days=dias)
                        initial_data['fecha_estimada_entrega'] = fecha_estimada.strftime('%Y-%m-%d')
                    except (ValueError, TypeError): pass

    if request.method == 'POST':
        form = OrdenCompraForm(request.POST, **form_kwargs)
        if form.is_valid():
            orden_compra = form.save(commit=False)
            orden_compra.tipo = 'compra'
            orden_compra.estado = 'BORRADOR'
            
            # --- Aquí asignamos el número de orden usando el servicio ---
            orden_compra.numero_orden = generar_siguiente_numero_documento(Orden, 'OC', 'numero_orden')
            
            orden_compra.save()
            
            messages.success(request, f"Orden de Compra '{orden_compra.numero_orden}' creada en Borrador.")
            return redirect('App_LUMINOVA:compras_lista_oc')
        else:
            messages.error(request, "Por favor, corrija los errores del formulario.")
    else: # GET
        form = OrdenCompraForm(initial=initial_data, **form_kwargs)

    context = {
        'form_oc': form,
        'titulo_seccion': 'Crear Orden de Compra',
        'insumo_preseleccionado': insumo_preseleccionado_obj,
    }
    return render(request, 'compras/compras_crear_editar_oc.html', context)


@login_required
@transaction.atomic
def compras_editar_oc_view(request, oc_id):
    orden_compra_instance = get_object_or_404(Orden, id=oc_id, tipo="compra")
    logger.info(
        f"Editando OC: {orden_compra_instance.numero_orden} (ID: {oc_id}), Estado actual: {orden_compra_instance.estado}"
    )

    estados_no_editables_campos_principales = [
        "APROBADA",
        "ENVIADA_PROVEEDOR",
        "CONFIRMADA_PROVEEDOR",
        "EN_TRANSITO",
        "RECIBIDA_PARCIAL",
        "RECIBIDA_TOTAL",
        "COMPLETADA",
        "CANCELADA",
    ]

    if orden_compra_instance.estado in estados_no_editables_campos_principales:
        messages.warning(
            request,
            f"La OC {orden_compra_instance.numero_orden} en estado '{orden_compra_instance.get_estado_display()}' tiene edición limitada (ej. solo notas o tracking). Los campos principales no se modificarán.",
        )
        # La lógica del __init__ del form deshabilitará la mayoría de los campos.

    insumo_original_obj_al_cargar = orden_compra_instance.insumo_principal
    cantidad_original_guardada = orden_compra_instance.cantidad_principal or 0

    # Preparar kwargs para el formulario, sin incluir 'instance' aquí si se pasa explícitamente
    form_init_kwargs = {}
    if insumo_original_obj_al_cargar:
        form_init_kwargs["insumo_fijado"] = insumo_original_obj_al_cargar
    if orden_compra_instance.proveedor and orden_compra_instance.estado != "BORRADOR":
        form_init_kwargs["proveedor_fijado"] = orden_compra_instance.proveedor

    if request.method == "POST":
        # Al instanciar para POST, pasamos instance explícitamente, y el resto en form_init_kwargs
        form = OrdenCompraForm(
            request.POST, instance=orden_compra_instance, **form_init_kwargs
        )
        if form.is_valid():
            try:
                oc_actualizada = form.save(commit=False)

                insumo_nuevo_obj_form = form.cleaned_data.get("insumo_principal")
                cantidad_nueva_form = form.cleaned_data.get("cantidad_principal") or 0

                if orden_compra_instance.estado == "BORRADOR":
                    insumo_original_en_db = Orden.objects.get(
                        pk=oc_id
                    ).insumo_principal  # Estado del insumo antes de esta edición
                    cantidad_original_en_db = (
                        Orden.objects.get(pk=oc_id).cantidad_principal or 0
                    )

                    # Caso 1: El insumo principal cambió
                    if (
                        insumo_original_en_db
                        and insumo_nuevo_obj_form
                        and insumo_original_en_db.id != insumo_nuevo_obj_form.id
                    ):
                        Insumo.objects.filter(id=insumo_original_en_db.id).update(
                            cantidad_en_pedido=F("cantidad_en_pedido")
                            - cantidad_original_en_db
                        )
                        Insumo.objects.filter(id=insumo_nuevo_obj_form.id).update(
                            cantidad_en_pedido=F("cantidad_en_pedido")
                            + cantidad_nueva_form
                        )
                    # Caso 2: El insumo no cambió, pero la cantidad sí
                    elif (
                        insumo_original_en_db
                        and insumo_original_en_db.id
                        == (insumo_nuevo_obj_form.id if insumo_nuevo_obj_form else None)
                        and cantidad_original_en_db != cantidad_nueva_form
                    ):
                        cambio_neto_cantidad = (
                            cantidad_nueva_form - cantidad_original_en_db
                        )
                        Insumo.objects.filter(id=insumo_original_en_db.id).update(
                            cantidad_en_pedido=F("cantidad_en_pedido")
                            + cambio_neto_cantidad
                        )
                    # Caso 3: Se añadió un insumo donde antes no había
                    elif (
                        not insumo_original_en_db
                        and insumo_nuevo_obj_form
                        and cantidad_nueva_form > 0
                    ):
                        Insumo.objects.filter(id=insumo_nuevo_obj_form.id).update(
                            cantidad_en_pedido=F("cantidad_en_pedido")
                            + cantidad_nueva_form
                        )
                    # Caso 4: Se quitó un insumo que antes estaba
                    elif insumo_original_en_db and not insumo_nuevo_obj_form:
                        Insumo.objects.filter(id=insumo_original_en_db.id).update(
                            cantidad_en_pedido=F("cantidad_en_pedido")
                            - cantidad_original_en_db
                        )

                oc_actualizada.save()
                messages.success(
                    request,
                    f"Orden de Compra '{oc_actualizada.numero_orden}' actualizada exitosamente.",
                )
                return redirect(
                    "App_LUMINOVA:compras_detalle_oc", oc_id=oc_actualizada.id
                )

            except DjangoIntegrityError as e_int:
                if (
                    "UNIQUE constraint" in str(e_int).lower()
                    and "numero_orden" in str(e_int).lower()
                ):
                    messages.error(
                        request,
                        f"Error: El N° de OC '{form.cleaned_data.get('numero_orden', '')}' ya existe.",
                    )
                else:
                    messages.error(request, f"Error de base de datos: {e_int}")
            except Exception as e:
                messages.error(request, f"Error inesperado al actualizar la OC: {e}")
                logger.exception(f"Error al editar OC {oc_id} (POST):")
        else:  # Formulario no es válido
            logger.warning(f"Formulario OC (edición) inválido: {form.errors.as_json()}")
            messages.error(request, "Por favor, corrija los errores en el formulario.")
            # El form con errores (ya instanciado con request.POST, instance y form_init_kwargs)
            # se pasará al contexto
    else:  # GET request
        # Al instanciar para GET, pasamos instance explícitamente y el resto en form_init_kwargs
        form = OrdenCompraForm(instance=orden_compra_instance, **form_init_kwargs)

    context = {
        "form_oc": form,
        "titulo_seccion": f"Editar Orden de Compra: {orden_compra_instance.numero_orden}",
        "oc_instance": orden_compra_instance,
        "insumo_preseleccionado": orden_compra_instance.insumo_principal,
        "proveedor_preseleccionado": orden_compra_instance.proveedor,
    }
    return render(request, "compras/compras_crear_editar_oc.html", context)


@login_required
@require_POST  # Esta acción debería ser un POST, ya que modifica datos
@transaction.atomic
def compras_aprobar_oc_directamente_view(request, oc_id):  # Nuevo nombre
    # if not es_admin_o_rol(request.user, ['compras_manager', 'administrador']): # Permisos
    #     messages.error(request, "No tiene permiso para aprobar Órdenes de Compra.")
    #     return redirect('App_LUMINOVA:compras_lista_oc')

    orden_compra = get_object_or_404(Orden, id=oc_id, tipo="compra")

    if orden_compra.estado == "BORRADOR":  # Solo aprobar desde borrador
        try:
            orden_compra.estado = "APROBADA"
            # Aquí es un buen lugar para confirmar/actualizar la cantidad_en_pedido del insumo
            # si no se hizo al crear el borrador, o si quieres que solo las aprobadas la afecten.
            if (
                orden_compra.insumo_principal
                and orden_compra.cantidad_principal
                and orden_compra.cantidad_principal > 0
            ):
                # Asegúrate que esta lógica no duplique si ya lo hiciste en la creación del borrador.
                # Si la cantidad_en_pedido se suma al crear el BORRADOR, no necesitas hacerlo de nuevo aquí.
                # Si solo se suma al APROBAR, entonces este es el lugar:
                # Insumo.objects.filter(id=orden_compra.insumo_principal.id).update(
                #     cantidad_en_pedido=F('cantidad_en_pedido') + orden_compra.cantidad_principal
                # )
                # logger.info(f"OC {orden_compra.numero_orden} aprobada. Incrementada cantidad_en_pedido para {orden_compra.insumo_principal.descripcion}.")
                pass  # Asumimos que cantidad_en_pedido ya se actualizó al crear el borrador

            orden_compra.save(update_fields=["estado"])
            messages.success(
                request,
                f"Orden de Compra '{orden_compra.numero_orden}' ha sido APROBADA.",
            )
            logger.info(
                f"OC {orden_compra.numero_orden} (ID: {oc_id}) cambió estado a APROBADA por {request.user.username}"
            )
        except Exception as e:
            messages.error(request, f"Error al aprobar la OC: {e}")
            logger.error(f"Error al cambiar estado de OC {oc_id} a APROBADA: {e}")
    else:
        messages.warning(
            request,
            f"La OC '{orden_compra.numero_orden}' no está en estado 'Borrador'. Estado actual: {orden_compra.get_estado_display()}",
        )

    return redirect("App_LUMINOVA:compras_lista_oc")


@login_required
@require_GET  # Esta vista solo necesita obtener datos
def get_oferta_proveedor_ajax(request):
    insumo_id = request.GET.get("insumo_id")
    proveedor_id = request.GET.get("proveedor_id")

    if not insumo_id or not proveedor_id:
        return JsonResponse({"error": "Faltan IDs de insumo o proveedor"}, status=400)

    try:
        insumo_id = int(insumo_id)
        proveedor_id = int(proveedor_id)
    except ValueError:
        return JsonResponse({"error": "IDs inválidos"}, status=400)

    oferta = OfertaProveedor.objects.filter(
        insumo_id=insumo_id, proveedor_id=proveedor_id
    ).first()

    if oferta:
        fecha_estimada_entrega_calculada = None
        if oferta.tiempo_entrega_estimado_dias is not None:
            try:
                dias = int(oferta.tiempo_entrega_estimado_dias)
                fecha_estimada_entrega_calculada = (
                    timezone.now().date() + timedelta(days=dias)
                ).strftime("%Y-%m-%d")
            except ValueError:
                pass  # No se pudo calcular

        data = {
            "success": True,
            "precio_unitario": oferta.precio_unitario_compra,
            "tiempo_entrega_dias": oferta.tiempo_entrega_estimado_dias,
            "fecha_estimada_entrega": fecha_estimada_entrega_calculada,
            "fecha_actualizacion_oferta": (
                oferta.fecha_actualizacion_precio.strftime("%d/%m/%Y")
                if oferta.fecha_actualizacion_precio
                else None
            ),
        }
        return JsonResponse(data)
    else:
        return JsonResponse(
            {"success": False, "error": "No se encontró oferta para esta combinación."},
            status=404,
        )


@login_required
@require_GET
def ajax_get_proveedores_for_insumo(request):
    insumo_id = request.GET.get("insumo_id")
    if not insumo_id:
        return JsonResponse({"proveedores": []})

    try:
        # Obtiene los IDs de los proveedores que tienen una oferta para el insumo dado.
        proveedor_ids = (
            OfertaProveedor.objects.filter(insumo_id=insumo_id)
            .values_list("proveedor_id", flat=True)
            .distinct()
        )

        # Obtiene los objetos Proveedor correspondientes a esos IDs.
        proveedores = (
            Proveedor.objects.filter(id__in=proveedor_ids)
            .values("id", "nombre")
            .order_by("nombre")
        )

        return JsonResponse({"proveedores": list(proveedores)})
    except ValueError:
        return JsonResponse({"error": "ID de insumo inválido"}, status=400)
    except Exception as e:
        logger.error(f"Error en ajax_get_proveedores_for_insumo: {e}")
        return JsonResponse({"error": "Ocurrió un error en el servidor"}, status=500)


# --- PRODUCCIÓN VIEWS ---
def proveedor_create_view(request):
    if not request.user.is_authenticated:
        return redirect("App_LUMINOVA:login")

    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(
                request, f"Proveedor {proveedor.nombre} creado exitosamente."
            )
            return redirect("App_LUMINOVA:proveedor_list")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(
                        request, f"{form.fields[field].label or field}: {error}"
                    )
    else:
        form = ProveedorForm()

    context = {
        "form": form,
        "titulo_seccion": "Crear Proveedor",
    }
    return render(request, "ventas/proveedores/proveedor_crear.html", context)


@login_required
def produccion_lista_op_view(request):
    """
    Muestra el listado de Órdenes de Producción, separadas en pestañas
    para "Activas" y "Finalizadas" (Completadas/Canceladas).
    """

    # Estados que consideramos "finalizados" y que irán a la pestaña de historial.
    ESTADOS_FINALIZADOS = ["Completada", "Cancelada"]

    # Creamos una consulta base para no repetir el código.
    # Esta consulta ya incluye las optimizaciones de select_related y prefetch_related.
    base_query = OrdenProduccion.objects.select_related(
        "producto_a_producir__categoria",
        "orden_venta_origen__cliente",
        "estado_op",
        "sector_asignado_op",
    ).prefetch_related(
        Prefetch(
            "reportes_incidencia",
            queryset=Reportes.objects.filter(resuelto=False).select_related(
                "reportado_por", "sector_reporta"
            ),
            to_attr="reportes_abiertos",  # El resultado se guardará en op.reportes_abiertos
        )
    )

    # 1. Lista de OPs "Activas": todas aquellas cuyo estado NO está en la lista de finalizados.
    #    Se ordenan por las más antiguas primero para darles prioridad.
    ops_activas = base_query.exclude(
        estado_op__nombre__in=ESTADOS_FINALIZADOS
    ).order_by("fecha_solicitud")

    # 2. Lista de OPs "Finalizadas": todas aquellas cuyo estado SÍ está en la lista.
    #    Se ordenan por las más recientes primero para ver lo último que se terminó.
    ops_finalizadas = base_query.filter(
        estado_op__nombre__in=ESTADOS_FINALIZADOS
    ).order_by("-fecha_solicitud")

    context = {
        "ops_activas_list": ops_activas,
        "ops_finalizadas_list": ops_finalizadas,
        "titulo_seccion": "Listado de Órdenes de Producción",
        # No es necesario pasar el form_update_op aquí, ya que no se usa en la vista de lista.
    }

    return render(request, "produccion/produccion_lista_op.html", context)


@login_required
def planificacion_produccion_view(request):
    # if not es_admin_o_rol(request.user, ['produccion', 'administrador']):
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    if request.method == "POST":
        op_id_a_actualizar = request.POST.get("op_id")
        try:
            op_a_actualizar = get_object_or_404(OrdenProduccion, id=op_id_a_actualizar)

            # Usamos un formulario para validar y limpiar los datos
            form = OrdenProduccionUpdateForm(request.POST, instance=op_a_actualizar)

            # Solo nos interesan ciertos campos del formulario en esta vista
            sector_id = request.POST.get("sector_asignado_op")
            fecha_inicio_p = request.POST.get("fecha_inicio_planificada")
            fecha_fin_p = request.POST.get("fecha_fin_planificada")

            if sector_id:
                op_a_actualizar.sector_asignado_op_id = sector_id
            if fecha_inicio_p:
                op_a_actualizar.fecha_inicio_planificada = fecha_inicio_p
            if fecha_fin_p:
                op_a_actualizar.fecha_fin_planificada = fecha_fin_p

            op_a_actualizar.save()
            messages.success(
                request,
                f"Planificación para OP {op_a_actualizar.numero_op} actualizada.",
            )
        except Exception as e:
            messages.error(request, f"Error al actualizar la planificación: {e}")

        return redirect("App_LUMINOVA:planificacion_produccion")

    # --- LÓGICA GET MEJORADA ---
    # Obtener todas las OPs que no estén en un estado final
    estados_finales = ["Completada", "Cancelada"]
    ops_para_planificar = (
        OrdenProduccion.objects.exclude(estado_op__nombre__in=estados_finales)
        .select_related(
            "producto_a_producir",
            "orden_venta_origen__cliente",
            "estado_op",
            "sector_asignado_op",
        )
        .order_by("estado_op__id", "fecha_solicitud")
    )  # Ordenar por estado y luego por fecha

    sectores = SectorAsignado.objects.all().order_by("nombre")

    context = {
        "ops_para_planificar_list": ops_para_planificar,
        "sectores_list": sectores,
        "titulo_seccion": "Planificación de Órdenes de Producción",
    }
    return render(request, "produccion/planificacion.html", context)


@login_required
@require_POST
@transaction.atomic
def solicitar_insumos_op_view(request, op_id):
    op = get_object_or_404(
        OrdenProduccion.objects.select_related(
            "estado_op", "orden_venta_origen", "producto_a_producir"
        ),
        id=op_id,
    )
    estado_op_anterior_obj = op.estado_op

    estado_actual_op_nombre = op.estado_op.nombre.lower() if op.estado_op else ""
    if estado_actual_op_nombre not in ["pendiente", "planificada"]:
        messages.error(
            request,
            f"La OP {op.numero_op} no está en un estado válido para solicitar insumos (actual: {op.get_estado_op_display()}).",
        )
        return redirect("App_LUMINOVA:produccion_detalle_op", op_id=op.id)

    try:
        estado_insumos_solicitados_op = EstadoOrden.objects.get(
            nombre__iexact="Insumos Solicitados"
        )

        # Log de cambio de estado de OP antes de guardar
        if (
            op.orden_venta_origen
            and estado_op_anterior_obj != estado_insumos_solicitados_op
        ):
            descripcion_op = (
                f"La OP {op.numero_op} ('{op.producto_a_producir.descripcion}') cambió su estado "
                f"de '{estado_op_anterior_obj.nombre if estado_op_anterior_obj else 'N/A'}' "
                f"a '{estado_insumos_solicitados_op.nombre}'."
            )
            HistorialOV.objects.create(
                orden_venta=op.orden_venta_origen,
                descripcion=descripcion_op,
                tipo_evento="Cambio Estado OP",
                realizado_por=request.user,
            )

        op.estado_op = estado_insumos_solicitados_op
        op.save(update_fields=["estado_op"])
        messages.success(
            request, f"Solicitud de insumos para OP {op.numero_op} enviada a Depósito."
        )

        # Actualizar estado de la OV si corresponde
        if op.orden_venta_origen:
            orden_venta_asociada = op.orden_venta_origen
            if orden_venta_asociada.estado in ["PENDIENTE", "CONFIRMADA"]:
                estado_ov_anterior_str = orden_venta_asociada.get_estado_display()
                orden_venta_asociada.estado = "INSUMOS_SOLICITADOS"
                orden_venta_asociada.save(update_fields=["estado"])

                # Log de cambio de estado de OV
                descripcion_ov = f"Estado de la OV cambió de '{estado_ov_anterior_str}' a 'Insumos Solicitados'."
                HistorialOV.objects.create(
                    orden_venta=orden_venta_asociada,
                    descripcion=descripcion_ov,
                    tipo_evento="Cambio Estado OV",
                    realizado_por=request.user,
                )

                messages.info(
                    request,
                    f"Estado de OV {orden_venta_asociada.numero_ov} actualizado.",
                )

    except EstadoOrden.DoesNotExist:
        messages.error(
            request,
            "Error crítico: El estado 'Insumos Solicitados' no está configurado.",
        )
    except Exception as e:
        messages.error(request, f"Error al solicitar insumos: {str(e)}")

    return redirect("App_LUMINOVA:produccion_detalle_op", op_id=op.id)


@login_required
@transaction.atomic
def produccion_detalle_op_view(request, op_id):
    op = get_object_or_404(
        OrdenProduccion.objects.select_related(
            "producto_a_producir__categoria",
            "orden_venta_origen__cliente",
            "estado_op",
            "sector_asignado_op",
        ).prefetch_related(
            "orden_venta_origen__ops_generadas__estado_op",
            "producto_a_producir__componentes_requeridos__insumo",
        ),
        id=op_id,
    )
    estado_op_anterior_obj = op.estado_op

    insumos_necesarios_data = []
    todos_los_insumos_disponibles = True
    if op.producto_a_producir:
        componentes_requeridos = op.producto_a_producir.componentes_requeridos.all()
        if not componentes_requeridos:
            todos_los_insumos_disponibles = False
        for comp in componentes_requeridos:
            cantidad_total_requerida_para_op = (
                comp.cantidad_necesaria * op.cantidad_a_producir
            )
            suficiente = comp.insumo.stock >= cantidad_total_requerida_para_op
            if not suficiente:
                todos_los_insumos_disponibles = False
            insumos_necesarios_data.append(
                {
                    "insumo_descripcion": comp.insumo.descripcion,
                    "cantidad_por_unidad_pt": comp.cantidad_necesaria,
                    "cantidad_total_requerida_op": cantidad_total_requerida_para_op,
                    "stock_actual_insumo": comp.insumo.stock,
                    "suficiente_stock": suficiente,
                    "insumo_id": comp.insumo.id,
                }
            )
    else:
        todos_los_insumos_disponibles = False

    puede_solicitar_insumos = False
    mostrar_boton_reportar = False
    estado_op_queryset_para_form = EstadoOrden.objects.all().order_by("nombre")

    ESTADO_OP_PENDIENTE_LOWER = "pendiente"
    ESTADO_OP_PLANIFICADA_LOWER = "planificada"
    ESTADO_OP_INSUMOS_SOLICITADOS_LOWER = "insumos solicitados"
    ESTADO_OP_INSUMOS_RECIBIDOS_LOWER = "insumos recibidos"
    ESTADO_OP_PRODUCCION_INICIADA_LOWER = "producción iniciada"
    ESTADO_OP_EN_PROCESO_LOWER = "en proceso"
    ESTADO_OP_PAUSADA_LOWER = "pausada"
    NOMBRE_ESTADO_OP_COMPLETADA_CONST = "Completada"
    ESTADO_OP_COMPLETADA_LOWER = NOMBRE_ESTADO_OP_COMPLETADA_CONST.lower()
    ESTADO_OP_CANCELADA_LOWER = "cancelada"

    if op.estado_op:
        estado_actual_nombre_lower = op.estado_op.nombre.lower()
        estado_actual_nombre_original = op.estado_op.nombre
        nombres_permitidos_dropdown = [estado_actual_nombre_original]

        if (
            estado_actual_nombre_lower
            in [ESTADO_OP_PENDIENTE_LOWER, ESTADO_OP_PLANIFICADA_LOWER]
            and op.sector_asignado_op
        ):
            puede_solicitar_insumos = True
        elif estado_actual_nombre_lower == ESTADO_OP_INSUMOS_SOLICITADOS_LOWER:
            nombres_permitidos_dropdown.extend(["Pausada", "Cancelada"])
        elif estado_actual_nombre_lower == ESTADO_OP_INSUMOS_RECIBIDOS_LOWER:
            nombres_permitidos_dropdown.extend(
                ["Producción Iniciada", "Pausada", "Cancelada"]
            )
        elif estado_actual_nombre_lower == ESTADO_OP_PRODUCCION_INICIADA_LOWER:
            nombres_permitidos_dropdown.extend(
                ["En Proceso", "Pausada", "Completada", "Cancelada"]
            )
        elif estado_actual_nombre_lower == ESTADO_OP_EN_PROCESO_LOWER:
            nombres_permitidos_dropdown.extend(["Pausada", "Completada", "Cancelada"])
        elif estado_actual_nombre_lower == ESTADO_OP_PAUSADA_LOWER:
            nombres_permitidos_dropdown.extend(["Cancelada"])
            if EstadoOrden.objects.filter(
                nombre__iexact=ESTADO_OP_INSUMOS_RECIBIDOS_LOWER
            ).exists():
                nombres_permitidos_dropdown.append("Insumos Recibidos")
            if EstadoOrden.objects.filter(
                nombre__iexact=ESTADO_OP_PRODUCCION_INICIADA_LOWER
            ).exists():
                nombres_permitidos_dropdown.append("Producción Iniciada")
            if EstadoOrden.objects.filter(
                nombre__iexact=ESTADO_OP_PENDIENTE_LOWER
            ).exists():
                nombres_permitidos_dropdown.append("Pendiente")

        if estado_actual_nombre_lower not in [
            ESTADO_OP_COMPLETADA_LOWER,
            ESTADO_OP_CANCELADA_LOWER,
        ]:
            mostrar_boton_reportar = True

        q_permitidos = Q()
        for n in list(set(nombres_permitidos_dropdown)):
            q_permitidos |= Q(nombre__iexact=n)
        if q_permitidos:
            estado_op_queryset_para_form = EstadoOrden.objects.filter(
                q_permitidos
            ).order_by("nombre")
        elif op.estado_op:
            estado_op_queryset_para_form = EstadoOrden.objects.filter(
                id=op.estado_op.id
            )

    if request.method == "POST":
        form_update = OrdenProduccionUpdateForm(
            request.POST, instance=op, estado_op_queryset=estado_op_queryset_para_form
        )
        if form_update.is_valid():
            nuevo_estado_op_obj = form_update.cleaned_data.get("estado_op")

            # Log de cambio de estado de OP
            if op.orden_venta_origen and estado_op_anterior_obj != nuevo_estado_op_obj:
                descripcion_op = (
                    f"La OP {op.numero_op} ('{op.producto_a_producir.descripcion}') cambió su estado "
                    f"de '{estado_op_anterior_obj.nombre if estado_op_anterior_obj else 'N/A'}' "
                    f"a '{nuevo_estado_op_obj.nombre if nuevo_estado_op_obj else 'N/A'}'."
                )
                HistorialOV.objects.create(
                    orden_venta=op.orden_venta_origen,
                    descripcion=descripcion_op,
                    tipo_evento="Cambio Estado OP",
                    realizado_por=request.user,
                )

            op_actualizada = form_update.save(commit=False)
            se_esta_completando_op_ahora = False
            if (
                nuevo_estado_op_obj
                and nuevo_estado_op_obj.nombre.lower() == ESTADO_OP_COMPLETADA_LOWER
            ):
                if (
                    not estado_op_anterior_obj
                    or estado_op_anterior_obj.nombre.lower()
                    != ESTADO_OP_COMPLETADA_LOWER
                ):
                    se_esta_completando_op_ahora = True
                    op_actualizada.fecha_fin_real = (
                        timezone.now()
                        if not op_actualizada.fecha_fin_real
                        else op_actualizada.fecha_fin_real
                    )

            if se_esta_completando_op_ahora:
                producto_terminado_obj = op_actualizada.producto_a_producir
                cantidad_producida = op_actualizada.cantidad_a_producir
                if producto_terminado_obj and cantidad_producida > 0:

                    # 1. Actualizar el stock principal del ProductoTerminado
                    producto_terminado_obj.stock = F("stock") + cantidad_producida
                    producto_terminado_obj.save(update_fields=["stock"])
                    logger.info(
                        f"Stock de '{producto_terminado_obj.descripcion}' incrementado en {cantidad_producida}."
                    )

                    # 2. Crear el lote para registro y envío
                    LoteProductoTerminado.objects.create(
                        producto=producto_terminado_obj,
                        op_asociada=op_actualizada,
                        cantidad=cantidad_producida,
                    )
                    messages.info(
                        request,
                        f"Lote de {cantidad_producida} x '{producto_terminado_obj.descripcion}' generado y stock actualizado.",
                    )

            op_actualizada.save()
            messages.success(
                request,
                f"Orden de Producción {op_actualizada.numero_op} actualizada a '{op_actualizada.get_estado_op_display()}'.",
            )

            if op_actualizada.orden_venta_origen:
                orden_venta_asociada = op_actualizada.orden_venta_origen
                ops_de_la_ov = OrdenProduccion.objects.filter(
                    orden_venta_origen=orden_venta_asociada
                )

                total_ops_en_ov = ops_de_la_ov.count()
                count_completada = ops_de_la_ov.filter(
                    estado_op__nombre__iexact=ESTADO_OP_COMPLETADA_LOWER
                ).count()
                count_cancelada = ops_de_la_ov.filter(
                    estado_op__nombre__iexact=ESTADO_OP_CANCELADA_LOWER
                ).count()

                if total_ops_en_ov > 0 and (
                    count_completada + count_cancelada == total_ops_en_ov
                ):
                    if orden_venta_asociada.estado != "LISTA_ENTREGA":
                        estado_ov_anterior_str = (
                            orden_venta_asociada.get_estado_display()
                        )
                        orden_venta_asociada.estado = "LISTA_ENTREGA"
                        orden_venta_asociada.save(update_fields=["estado"])

                        descripcion_ov = f"Estado de la OV cambió de '{estado_ov_anterior_str}' a 'Lista para Entrega'."
                        HistorialOV.objects.create(
                            orden_venta=orden_venta_asociada,
                            descripcion=descripcion_ov,
                            tipo_evento="Cambio Estado OV",
                            realizado_por=request.user,
                        )

                        messages.info(
                            request,
                            f"Todos los ítems de la OV {orden_venta_asociada.numero_ov} están listos. El estado de la OV se ha actualizado a 'Lista para Entrega'.",
                        )
                        logger.info(
                            f"OV {orden_venta_asociada.numero_ov} actualizada a 'LISTA_ENTREGA' porque todas sus OPs han finalizado."
                        )

            return redirect(
                "App_LUMINOVA:produccion_detalle_op", op_id=op_actualizada.id
            )
        else:
            messages.error(
                request,
                "Error al actualizar la OP. Por favor, revise los datos del formulario.",
            )
            logger.warning(
                f"Formulario OrdenProduccionUpdateForm inválido para OP {op.id}: {form_update.errors.as_json()}"
            )
            if op.estado_op and op.estado_op.nombre.lower() in [
                ESTADO_OP_PAUSADA_LOWER,
                ESTADO_OP_CANCELADA_LOWER,
            ]:
                mostrar_boton_reportar = True
    else:
        form_update = OrdenProduccionUpdateForm(
            instance=op, estado_op_queryset=estado_op_queryset_para_form
        )
    estados_activos_para_reportar = [
        "insumos solicitados",
        "producción iniciada",
        "en proceso",
        "pausada",
        "producción con problemas",
    ]
    mostrar_boton_reportar = (
        op.estado_op and op.estado_op.nombre.lower() in estados_activos_para_reportar
    )

    context = {
        "op": op,
        "insumos_necesarios_list": insumos_necesarios_data,
        "form_update_op": form_update,
        "todos_los_insumos_disponibles_variable_de_contexto": todos_los_insumos_disponibles,
        "puede_solicitar_insumos": puede_solicitar_insumos,
        "mostrar_boton_reportar": mostrar_boton_reportar,
        "titulo_seccion": f"Detalle OP: {op.numero_op}",
    }
    return render(request, "produccion/produccion_detalle_op.html", context)


@login_required
def reportes_produccion_view(request, reporte_id=None, resolver=False):
    # --- Lógica para resolver un reporte ---
    if resolver and reporte_id and request.method == "POST":
        reporte_a_resolver = get_object_or_404(Reportes, id=reporte_id)
        if not reporte_a_resolver.resuelto:
            reporte_a_resolver.resuelto = True
            reporte_a_resolver.fecha_resolucion = timezone.now()
            reporte_a_resolver.save()

            # Cambiar estado de la OP asociada, si la tiene
            op_asociada = reporte_a_resolver.orden_produccion_asociada
            if (
                op_asociada
                and op_asociada.estado_op
                and op_asociada.estado_op.nombre
                in ["Pausada", "Producción con Problemas"]
            ):
                try:
                    # Intenta volver al estado 'En Proceso' que es lo más lógico.
                    estado_reanudado = EstadoOrden.objects.get(
                        nombre__iexact="En Proceso"
                    )
                    op_asociada.estado_op = estado_reanudado
                    op_asociada.save()
                    messages.success(
                        request,
                        f"El problema del reporte {reporte_a_resolver.n_reporte} ha sido resuelto y la OP {op_asociada.numero_op} ha sido reanudada.",
                    )
                except EstadoOrden.DoesNotExist:
                    messages.warning(
                        request,
                        f"Reporte {reporte_a_resolver.n_reporte} resuelto, pero no se encontró el estado 'En Proceso' para reanudar la OP.",
                    )
            else:
                messages.success(
                    request,
                    f"El reporte {reporte_a_resolver.n_reporte} ha sido marcado como resuelto.",
                )
        else:
            messages.info(request, "Este reporte ya había sido resuelto anteriormente.")
        return redirect("App_LUMINOVA:reportes_produccion")

    # --- Lógica para mostrar las listas en pestañas (para peticiones GET) ---
    reportes_abiertos = (
        Reportes.objects.filter(resuelto=False)
        .select_related("orden_produccion_asociada", "reportado_por", "sector_reporta")
        .order_by("-fecha")
    )
    reportes_resueltos = (
        Reportes.objects.filter(resuelto=True)
        .select_related("orden_produccion_asociada", "reportado_por", "sector_reporta")
        .order_by("-fecha_resolucion")
    )

    context = {
        "reportes_abiertos": reportes_abiertos,
        "reportes_resueltos": reportes_resueltos,
        "titulo_seccion": "Reportes de Producción",
    }
    return render(request, "produccion/reportes.html", context)


@login_required
@transaction.atomic
def crear_reporte_produccion_view(request, op_id):
    orden_produccion = get_object_or_404(OrdenProduccion, id=op_id)

    # Solo permitir reportar si la OP está en un estado problemático o según tu lógica
    # if not (orden_produccion.estado_op and orden_produccion.estado_op.nombre.lower() in ["pausada", "cancelada", "producción con problemas"]):
    #     messages.error(request, "Solo se pueden crear reportes para Órdenes de Producción en estados problemáticos.")
    #     return redirect('App_LUMINOVA:produccion_detalle_op', op_id=op_id)

    if request.method == "POST":
        form = ReporteProduccionForm(request.POST, orden_produccion=orden_produccion)
        if form.is_valid():
            reporte = form.save(commit=False)
            reporte.orden_produccion_asociada = orden_produccion
            reporte.reportado_por = request.user
            reporte.fecha = timezone.now()

            # Generar n_reporte único
            reporte.n_reporte = generar_siguiente_numero_documento(Reportes, 'RP', 'n_reporte')

            reporte.save()  
            messages.success(
                request,
                f"Reporte '{reporte.n_reporte}' creado exitosamente para la OP {orden_produccion.numero_op}.",
            )
            return redirect(
                "App_LUMINOVA:reportes_produccion"
            )  # Ir a la lista de todos los reportes
        else:
            messages.error(
                request, "Por favor, corrija los errores en el formulario de reporte."
            )
    else:  # GET
        # Pasar la OP al form para preseleccionar el sector si es posible
        form = ReporteProduccionForm(orden_produccion=orden_produccion)

    context = {
        "form_reporte": form,
        "orden_produccion": orden_produccion,
        "titulo_seccion": f"Crear Reporte para OP: {orden_produccion.numero_op}",
    }
    return render(request, "produccion/crear_reporte.html", context)


# --- DEPÓSITO VIEWS ---
@login_required
@transaction.atomic
def deposito_enviar_insumos_op_view(request, op_id):
    op = get_object_or_404(
        OrdenProduccion.objects.select_related(
            "orden_venta_origen",
            "producto_a_producir",  # Necesario para los componentes
        ),
        id=op_id,
    )
    logger.info(
        f"Procesando envío de insumos para OP: {op.numero_op} (Estado actual: {op.estado_op.nombre if op.estado_op else 'N/A'})"
    )

    if request.method == "POST":
        # Solo permitir esta acción si la OP está en "Insumos Solicitados"
        if not op.estado_op or op.estado_op.nombre.lower() != "insumos solicitados":
            messages.error(
                request,
                f"La OP {op.numero_op} no está en estado 'Insumos Solicitados'. No se pueden enviar insumos.",
            )
            return redirect("App_LUMINOVA:deposito_detalle_solicitud_op", op_id=op.id)

        insumos_descontados_correctamente = True
        errores_stock = []

        if not op.producto_a_producir:
            messages.error(
                request,
                f"Error crítico: La OP {op.numero_op} no tiene un producto asignado.",
            )
            return redirect("App_LUMINOVA:deposito_detalle_solicitud_op", op_id=op.id)

        componentes_requeridos = ComponenteProducto.objects.filter(
            producto_terminado=op.producto_a_producir
        ).select_related("insumo")

        if not componentes_requeridos.exists():
            messages.error(
                request,
                f"No se puede procesar: No hay BOM definido para el producto '{op.producto_a_producir.descripcion}'.",
            )
            logger.error(
                f"BOM no definido para producto {op.producto_a_producir.id} en OP {op.numero_op}"
            )
            return redirect("App_LUMINOVA:deposito_detalle_solicitud_op", op_id=op.id)

        for comp in componentes_requeridos:
            cantidad_a_descontar = comp.cantidad_necesaria * op.cantidad_a_producir
            try:
                # Bloquear la fila del insumo para evitar condiciones de carrera (si tu DB lo soporta bien)
                # insumo_a_actualizar = Insumo.objects.select_for_update().get(id=comp.insumo.id)
                insumo_a_actualizar = Insumo.objects.get(
                    id=comp.insumo.id
                )  # Versión más simple

                if insumo_a_actualizar.stock >= cantidad_a_descontar:
                    # Usar F() expression para una actualización atómica es preferible
                    Insumo.objects.filter(id=insumo_a_actualizar.id).update(
                        stock=F("stock") - cantidad_a_descontar
                    )
                    logger.info(
                        f"Stock de '{insumo_a_actualizar.descripcion}' (ID: {insumo_a_actualizar.id}) descontado en {cantidad_a_descontar}."
                    )
                else:
                    errores_stock.append(
                        f"Stock insuficiente para '{insumo_a_actualizar.descripcion}'. Requeridos: {cantidad_a_descontar}, Disponible: {insumo_a_actualizar.stock}"
                    )
                    insumos_descontados_correctamente = False
                    # Aquí podrías decidir si continuar verificando otros insumos o hacer break.
                    # Si haces break, solo se reportará el primer error de stock.
            except Insumo.DoesNotExist:
                errores_stock.append(
                    f"Insumo '{comp.insumo.descripcion}' (ID: {comp.insumo.id}) no encontrado durante el descuento. Error de datos."
                )
                insumos_descontados_correctamente = False
                break  # Error crítico, no continuar si un insumo del BOM no existe

        if errores_stock:  # Si hubo algún error de stock
            for error_msg in errores_stock:
                messages.error(request, error_msg)
            # No es necesario reasignar insumos_descontados_correctamente = False aquí, ya se hizo.

        if insumos_descontados_correctamente:
            try:
                # Estado al que pasa la OP DESPUÉS de que Depósito envía los insumos
                nombre_estado_op_post_deposito = (
                    "Insumos Recibidos"  # ESTE ES EL NUEVO ESTADO OBJETIVO
                )

                estado_siguiente_op_obj = EstadoOrden.objects.get(
                    nombre__iexact=nombre_estado_op_post_deposito
                )

                op.estado_op = estado_siguiente_op_obj
                # Considera si fecha_inicio_real se debe setear aquí o cuando producción realmente empieza.
                # Si es cuando depósito entrega, está bien.
                if (
                    not op.fecha_inicio_real
                ):  # O un nuevo campo como 'fecha_insumos_entregados'
                    op.fecha_inicio_real = timezone.now()
                op.save(update_fields=["estado_op", "fecha_inicio_real"])

                messages.success(
                    request,
                    f"Insumos para OP {op.numero_op} marcados como enviados/recibidos. OP ahora en estado '{estado_siguiente_op_obj.nombre}'.",
                )
                logger.info(
                    f"OP {op.numero_op} actualizada a estado '{estado_siguiente_op_obj.nombre}' por Depósito."
                )

                # La OV podría seguir en "INSUMOS_SOLICITADOS" o pasar a un estado intermedio si lo tienes.
                # La transición a "PRODUCCION_INICIADA" para la OV debería ocurrir cuando Producción
                # explícitamente inicia la OP (cambiándola de "Insumos Recibidos" a "Producción Iniciada").
                # No hay cambio directo de estado de OV aquí, se deja a la lógica de produccion_detalle_op_view.

            except EstadoOrden.DoesNotExist:
                messages.error(
                    request,
                    f"Error de Configuración: El estado de OP '{nombre_estado_op_post_deposito}' no fue encontrado. Insumos descontados, pero el estado de la OP no se actualizó correctamente. Por favor, cree este estado en el panel de administración.",
                )
                logger.error(
                    f"CRÍTICO: Estado OP '{nombre_estado_op_post_deposito}' no encontrado. OP {op.numero_op} podría quedar en estado incorrecto."
                )
            return redirect(
                "App_LUMINOVA:deposito_solicitudes_insumos"
            )  # Vuelve a la lista de solicitudes pendientes
        else:  # Hubo errores de stock
            logger.warning(
                f"Errores de stock al procesar OP {op.numero_op}. Redirigiendo a detalle de solicitud."
            )
            return redirect("App_LUMINOVA:deposito_detalle_solicitud_op", op_id=op.id)

    # Si es GET
    messages.info(
        request,
        "Esta acción de enviar insumos debe realizarse mediante POST desde la página de detalle de la solicitud.",
    )
    return redirect("App_LUMINOVA:deposito_detalle_solicitud_op", op_id=op.id)


@login_required
def deposito_solicitudes_insumos_view(request):
    ops_pendientes_preparacion = OrdenProduccion.objects.none()
    ops_con_insumos_enviados = OrdenProduccion.objects.none()

    titulo_seccion = "Gestión de Insumos para Producción"  # Correcto
    logger.info(
        "--- Entrando a deposito_solicitudes_insumos_view ---"
    )  # Log de entrada

    try:
        # 1. OBTENER OPs QUE ESTÁN SOLICITANDO INSUMOS
        estado_insumos_solicitados_obj = EstadoOrden.objects.filter(
            nombre__iexact="Insumos Solicitados"
        ).first()  # Renombrado para claridad

        if estado_insumos_solicitados_obj:
            logger.info(
                f"Estado 'Insumos Solicitados' encontrado (ID: {estado_insumos_solicitados_obj.id}, Nombre: '{estado_insumos_solicitados_obj.nombre}')."
            )
            ops_pendientes_preparacion = (
                OrdenProduccion.objects.filter(
                    estado_op=estado_insumos_solicitados_obj  # Usar el objeto encontrado
                )
                .select_related(
                    "producto_a_producir", "estado_op", "orden_venta_origen__cliente"
                )
                .order_by("fecha_solicitud")
            )
            logger.info(
                f"Encontradas {ops_pendientes_preparacion.count()} OPs pendientes de preparación."
            )
        else:
            messages.error(
                request,
                "Configuración crítica: El estado 'Insumos Solicitados' no existe en la base de datos. No se pueden mostrar las solicitudes pendientes.",
            )
            logger.error(
                "CRÍTICO: Estado 'Insumos Solicitados' no encontrado en deposito_solicitudes_insumos_view."
            )

        # 2. OBTENER OPs A LAS QUE YA SE LES ENVIARON INSUMOS (AHORA EN ESTADO "En Proceso")
        estado_en_proceso_nombre_buscado = "En Proceso"
        estado_en_proceso_obj = EstadoOrden.objects.filter(
            nombre__iexact=estado_en_proceso_nombre_buscado
        ).first()  # Renombrado

        if estado_en_proceso_obj:
            logger.info(
                f"Estado '{estado_en_proceso_nombre_buscado}' encontrado (ID: {estado_en_proceso_obj.id}, Nombre: '{estado_en_proceso_obj.nombre}')."
            )
            ops_con_insumos_enviados = (
                OrdenProduccion.objects.filter(
                    estado_op=estado_en_proceso_obj  # Usar el objeto encontrado
                )
                .select_related(
                    "producto_a_producir", "estado_op", "orden_venta_origen__cliente"
                )
                .order_by("-fecha_inicio_real", "-fecha_solicitud")
            )
            logger.info(
                f"Encontradas {ops_con_insumos_enviados.count()} OPs con insumos ya enviados/en proceso."
            )
        else:
            messages.warning(
                request,
                f"Advertencia de configuración: El estado '{estado_en_proceso_nombre_buscado}' no existe. No se mostrará la lista de OPs con insumos enviados.",
            )
            logger.warning(
                f"Configuración: Estado '{estado_en_proceso_nombre_buscado}' no encontrado en deposito_solicitudes_insumos_view."
            )

    except Exception as e:  # Captura más genérica para cualquier otro error inesperado
        messages.error(
            request,
            f"Ocurrió un error inesperado al cargar las solicitudes de insumos: {e}",
        )
        logger.exception("Excepción inesperada en deposito_solicitudes_insumos_view:")
        # ops_pendientes_preparacion y ops_con_insumos_enviados ya están como QuerySet vacíos.

    context = {
        "ops_pendientes_list": ops_pendientes_preparacion,
        "ops_enviadas_list": ops_con_insumos_enviados,
        "titulo_seccion": titulo_seccion,
    }
    logger.info(
        f"Contexto para deposito_solicitudes_insumos.html: ops_pendientes_list count = {ops_pendientes_preparacion.count()}, ops_enviadas_list count = {ops_con_insumos_enviados.count()}"
    )
    return render(request, "deposito/deposito_solicitudes_insumos.html", context)


@login_required
def recepcion_pedidos_view(request):
    """
    Muestra una lista de Órdenes de Compra que están "En Tránsito" y listas para ser recibidas.
    """
    # if not es_admin_o_rol(request.user, ['deposito', 'administrador']):
    #     messages.error(request, "Acceso no permitido.")
    #     return redirect('App_LUMINOVA:dashboard')

    ocs_en_transito = (
        Orden.objects.filter(tipo="compra", estado="EN_TRANSITO")
        .select_related("proveedor", "insumo_principal")
        .order_by("fecha_estimada_entrega")
    )

    context = {
        "ordenes_a_recibir": ocs_en_transito,
        "titulo_seccion": "Recepción de Pedidos de Compra",
    }
    return render(request, "deposito/deposito_recepcion.html", context)


@login_required
@require_POST
@transaction.atomic
def recibir_pedido_oc_view(request, oc_id):
    """
    Procesa la recepción de una Orden de Compra.
    """
    # if not es_admin_o_rol(request.user, ['deposito', 'administrador']):
    #     messages.error(request, "Acción no permitida.")
    #     return redirect('App_LUMINOVA:deposito_recepcion_pedidos')

    orden_a_recibir = get_object_or_404(Orden, id=oc_id, estado="EN_TRANSITO")

    insumo_recibido = orden_a_recibir.insumo_principal
    cantidad_recibida = orden_a_recibir.cantidad_principal

    if insumo_recibido and cantidad_recibida:
        # 1. Incrementar el stock del insumo
        insumo_recibido.stock = F("stock") + cantidad_recibida

        # 2. Decrementar la cantidad en pedido
        insumo_recibido.cantidad_en_pedido = F("cantidad_en_pedido") - cantidad_recibida

        insumo_recibido.save(update_fields=["stock", "cantidad_en_pedido"])
        logger.info(
            f"Stock de '{insumo_recibido.descripcion}' actualizado (+{cantidad_recibida}) y 'en pedido' actualizado (-{cantidad_recibida})."
        )

        # 3. Actualizar el estado de la OC a "Completada" (o "Recibida Totalmente")
        orden_a_recibir.estado = "COMPLETADA"
        orden_a_recibir.save(update_fields=["estado"])

        messages.success(
            request,
            f"Pedido {orden_a_recibir.numero_orden} recibido exitosamente. Se agregaron {cantidad_recibida} unidades de '{insumo_recibido.descripcion}' al stock.",
        )
    else:
        messages.error(
            request,
            f"Error: La OC {orden_a_recibir.numero_orden} no tiene un insumo o cantidad principal válidos.",
        )

    return redirect("App_LUMINOVA:deposito_recepcion_pedidos")


@login_required
def deposito_view(request):
    logger.info("--- deposito_view: INICIO ---")

    categorias_I = CategoriaInsumo.objects.all()
    categorias_PT = CategoriaProductoTerminado.objects.all()

    ops_pendientes_deposito_list = OrdenProduccion.objects.none()
    ops_pendientes_deposito_count = 0
    try:
        estado_sol = EstadoOrden.objects.filter(
            nombre__iexact="Insumos Solicitados"
        ).first()
        if estado_sol:
            ops_pendientes_deposito_list = (
                OrdenProduccion.objects.filter(estado_op=estado_sol)
                .select_related("producto_a_producir")
                .order_by("fecha_solicitud")
            )
            ops_pendientes_deposito_count = ops_pendientes_deposito_list.count()
    except Exception as e_op:
        logger.error(f"Deposito_view (OPs): Excepción al cargar OPs: {e_op}")

    lotes_en_stock = (
        LoteProductoTerminado.objects.filter(enviado=False)
        .select_related("producto", "op_asociada")
        .order_by("-fecha_creacion")
    )

    # --- INICIO DE LA CORRECCIÓN DE LÓGICA ---
    UMBRAL_STOCK_BAJO_INSUMOS = 15000
    insumos_con_stock_bajo = Insumo.objects.filter(stock__lt=UMBRAL_STOCK_BAJO_INSUMOS)

    # Estados que consideramos como "pedido en firme" (ya no es tarea del depósito)
    UMBRAL_STOCK_BAJO_INSUMOS = 15000
    insumos_con_stock_bajo = Insumo.objects.filter(stock__lt=UMBRAL_STOCK_BAJO_INSUMOS)

    # Estados que consideramos como "pedido en firme" (ya no es tarea del depósito/compras iniciar)
    ESTADOS_OC_EN_PROCESO = [
        "APROBADA",
        "ENVIADA_PROVEEDOR",
        "EN_TRANSITO",
        "RECIBIDA_PARCIAL",
    ]

    insumos_a_gestionar = []
    insumos_en_pedido = []

    for insumo in insumos_con_stock_bajo:
        # Buscamos si existe una OC que ya está aprobada y en proceso
        oc_en_proceso = (
            Orden.objects.filter(
                insumo_principal=insumo, estado__in=ESTADOS_OC_EN_PROCESO
            )
            .order_by("-fecha_creacion")
            .first()
        )

        if oc_en_proceso:
            # Si ya está en proceso, va a la tabla "En Pedido"
            insumos_en_pedido.append({"insumo": insumo, "oc": oc_en_proceso})
        else:
            # Si no hay OC en proceso (puede no existir o estar solo en Borrador),
            # es una acción pendiente.
            insumos_a_gestionar.append({"insumo": insumo})
    # --- FIN DE LA CORRECCIÓN DE LÓGICA ---

    context = {
        "categorias_I": categorias_I,
        "categorias_PT": categorias_PT,
        "ops_pendientes_deposito_list": ops_pendientes_deposito_list,
        "ops_pendientes_deposito_count": ops_pendientes_deposito_count,
        "lotes_productos_terminados_en_stock": lotes_en_stock,
        "insumos_a_gestionar_list": insumos_a_gestionar,  # Nueva lista para la primera tabla
        "insumos_en_pedido_list": insumos_en_pedido,  # Nueva lista para la segunda tabla
        "umbral_stock_bajo": UMBRAL_STOCK_BAJO_INSUMOS,
    }

    return render(request, "deposito/deposito.html", context)


@login_required
def deposito_solicitudes_insumos_view(request):
    # if not es_admin_o_rol(request.user, ['deposito', 'administrador']): # Control de permisos
    #     messages.error(request, "Acceso denegado.")
    #     return redirect('App_LUMINOVA:dashboard')

    ops_necesitan_insumos = (
        OrdenProduccion.objects.none()
    )  # Inicializar con un queryset vacío

    try:
        estado_objetivo = EstadoOrden.objects.get(nombre__iexact="Insumos Solicitados")
        ops_necesitan_insumos = (
            OrdenProduccion.objects.filter(  # ASIGNACIÓN AQUÍ (Camino A)
                estado_op=estado_objetivo
            )
            .select_related(
                "producto_a_producir", "estado_op", "orden_venta_origen__cliente"
            )
            .order_by("fecha_solicitud")
        )

    except EstadoOrden.DoesNotExist:
        messages.error(
            request,
            "Error: El estado 'Insumos Solicitados' no está configurado para las Órdenes de Producción. No se pueden listar las solicitudes.",
        )
        # ops_necesitan_insumos ya es un queryset vacío, así que está bien.
        # O podrías decidir mostrar un error más prominente o redirigir.
        # Para mantener la funcionalidad de la plantilla, dejaremos ops_necesitan_insumos como un queryset vacío.

    context = {
        "ops_necesitan_insumos_list": ops_necesitan_insumos,
        "titulo_seccion": "Solicitudes de Insumos desde Producción",
    }
    return render(request, "deposito/deposito_solicitudes_insumos.html", context)


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

    op = get_object_or_404(
        OrdenProduccion.objects.select_related("producto_a_producir", "estado_op"),
        id=op_id,
    )
    insumos_necesarios_data = []
    todos_los_insumos_disponibles = (
        True  # Asumir que sí hasta que se demuestre lo contrario
    )

    if op.producto_a_producir:
        componentes_requeridos = ComponenteProducto.objects.filter(
            producto_terminado=op.producto_a_producir
        ).select_related("insumo")

        if not componentes_requeridos.exists():
            messages.warning(
                request,
                f"No se ha definido el BOM (lista de componentes) para el producto '{op.producto_a_producir.descripcion}'. No se pueden determinar los insumos.",
            )
            todos_los_insumos_disponibles = False  # No se puede proceder

        for comp in componentes_requeridos:
            cantidad_total_req = comp.cantidad_necesaria * op.cantidad_a_producir
            suficiente = comp.insumo.stock >= cantidad_total_req
            if not suficiente:
                todos_los_insumos_disponibles = False
            insumos_necesarios_data.append(
                {
                    "insumo_id": comp.insumo.id,
                    "insumo_descripcion": comp.insumo.descripcion,
                    "cantidad_total_requerida_op": cantidad_total_req,
                    "stock_actual_insumo": comp.insumo.stock,
                    "suficiente_stock": suficiente,
                }
            )

    context = {
        "op": op,
        "insumos_necesarios_list": insumos_necesarios_data,
        "todos_los_insumos_disponibles": todos_los_insumos_disponibles,  # Para habilitar/deshabilitar botón
        "titulo_seccion": f"Detalle Solicitud Insumos para OP: {op.numero_op}",
    }
    return render(request, "deposito/deposito_detalle_solicitud_op.html", context)


@login_required
@require_POST
@transaction.atomic
def deposito_enviar_lote_pt_view(request, lote_id):
    """
    Procesa el envío de un lote de producto terminado.
    - Descuenta el stock del producto.
    - Marca el lote como enviado.
    - Actualiza el estado de la OV si corresponde.
    """
    lote = get_object_or_404(
        LoteProductoTerminado.objects.select_related(
            "producto", "op_asociada__orden_venta_origen"
        ),
        id=lote_id,
    )

    if lote.enviado:
        messages.warning(
            request,
            f"El lote del producto '{lote.producto.descripcion}' ya fue enviado anteriormente.",
        )
        return redirect("App_LUMINOVA:deposito_view")

    producto_terminado = lote.producto
    cantidad_a_enviar = lote.cantidad

    if producto_terminado.stock < cantidad_a_enviar:
        messages.error(
            request,
            f"Error de consistencia de datos: No hay stock suficiente para '{producto_terminado.descripcion}' para enviar el lote. Stock actual: {producto_terminado.stock}, se necesita: {cantidad_a_enviar}.",
        )
        return redirect("App_LUMINOVA:deposito_view")

    producto_terminado.stock -= cantidad_a_enviar
    producto_terminado.save(update_fields=["stock"])
    logger.info(
        f"Stock de '{producto_terminado.descripcion}' descontado en {cantidad_a_enviar}."
    )

    lote.enviado = True
    lote.save(update_fields=["enviado"])
    logger.info(
        f"Lote ID {lote.id} (OP: {lote.op_asociada.numero_op}) marcado como enviado."
    )

    # Registro en el historial
    if lote.op_asociada.orden_venta_origen:
        HistorialOV.objects.create(
            orden_venta=lote.op_asociada.orden_venta_origen,
            descripcion=f"Lote de {lote.cantidad} x '{lote.producto.descripcion}' (de OP {lote.op_asociada.numero_op}) enviado al cliente.",
            tipo_evento="Envío",
            realizado_por=request.user,
        )

    orden_venta = lote.op_asociada.orden_venta_origen
    if orden_venta:
        todos_los_lotes_de_la_ov = LoteProductoTerminado.objects.filter(
            op_asociada__orden_venta_origen=orden_venta
        )
        if not todos_los_lotes_de_la_ov.filter(enviado=False).exists():
            estado_ov_anterior_str = orden_venta.get_estado_display()
            orden_venta.estado = "COMPLETADA"
            orden_venta.save(update_fields=["estado"])

            # Log de cambio de estado de OV
            descripcion_ov = f"Estado de la Orden de Venta cambió de '{estado_ov_anterior_str}' a 'Completada/Entregada'."
            HistorialOV.objects.create(
                orden_venta=orden_venta,
                descripcion=descripcion_ov,
                tipo_evento="Cambio Estado OV",
                realizado_por=request.user,
            )

            messages.info(
                request,
                f"Todos los lotes para la OV '{orden_venta.numero_ov}' han sido enviados. La orden se ha marcado como 'Completada/Entregada'.",
            )
            logger.info(f"OV {orden_venta.numero_ov} actualizada a COMPLETADA.")

    messages.success(
        request,
        f"Lote de {cantidad_a_enviar} x '{producto_terminado.descripcion}' enviado exitosamente.",
    )
    return redirect("App_LUMINOVA:deposito_view")


# --- CLASS-BASED VIEWS (CRUDs) ---
class Categoria_IListView(ListView):
    model = CategoriaInsumo
    template_name = "deposito/deposito_view.html"
    context_object_name = (
        "categorias_I"  # Para diferenciar en el template deposito.html
    )


class Categoria_IDetailView(DetailView):
    model = CategoriaInsumo
    template_name = "deposito/categoria_insumo_detail.html"
    context_object_name = "categoria_I"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["insumos_de_categoria"] = Insumo.objects.filter(categoria=self.object)
        return context


class Categoria_ICreateView(CreateView):
    model = CategoriaInsumo
    template_name = "deposito/categoria_insumo_crear.html"
    fields = ("nombre", "imagen")
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


class Categoria_IUpdateView(UpdateView):
    model = CategoriaInsumo
    template_name = "deposito/categoria_insumo_editar.html"
    fields = ("nombre", "imagen")
    context_object_name = "categoria"
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


class Categoria_IDeleteView(DeleteView):
    model = CategoriaInsumo
    template_name = "deposito/categoria_insumo_confirm_delete.html"
    context_object_name = "categoria"
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasar los insumos protegidos a la plantilla para que se puedan listar
        # (Esto se podría hacer de forma más compleja si quieres una lista completa en caso de error,
        # pero el mensaje de ProtectedError ya los lista)
        context["insumos_asociados_count"] = (
            self.object.insumos.count()
        )  # insumos es el related_name
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            # Intenta eliminar el objeto
            response = super().delete(request, *args, **kwargs)
            messages.success(
                request,
                f"Categoría de Insumo '{self.object.nombre}' eliminada exitosamente.",
            )
            return response
        except ProtectedError as e:
            # e.protected_objects contiene los objetos que impiden la eliminación
            nombres_insumos_protegidos = [str(insumo) for insumo in e.protected_objects]
            mensaje_error = (
                f"No se puede eliminar la categoría '{self.object.nombre}' porque está "
                f"siendo utilizada por los siguientes insumos: {', '.join(nombres_insumos_protegidos)}. "
                "Por favor, reasigne o elimine estos insumos primero."
            )
            messages.error(request, mensaje_error)
            logger.warning(
                f"Intento fallido de eliminar CategoriaInsumo ID {self.object.id} debido a ProtectedError: {e}"
            )
            # Redirigir de vuelta a la página de detalle de la categoría o a la confirmación de borrado
            return redirect("App_LUMINOVA:categoria_i_detail", pk=self.object.pk)
            # O a: return self.get(request, *args, **kwargs) para volver a mostrar la página de confirmación con el mensaje


# --- CRUD Categorias Producto Terminado ---
class Categoria_PTListView(ListView):
    model = CategoriaProductoTerminado
    template_name = "deposito/deposito.html"
    context_object_name = "categorias_PT"


class Categoria_PTDetailView(DetailView):
    model = CategoriaProductoTerminado
    template_name = "deposito/categoria_producto_terminado_detail.html"
    context_object_name = "categoria_PT"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["productos_de_categoria"] = ProductoTerminado.objects.filter(
            categoria=self.object
        )
        return context


class Categoria_PTCreateView(CreateView):
    model = CategoriaProductoTerminado
    template_name = "deposito/categoria_producto_terminado_crear.html"
    fields = ("nombre", "imagen")
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


class Categoria_PTUpdateView(UpdateView):
    model = CategoriaProductoTerminado
    template_name = "deposito/categoria_producto_terminado_editar.html"
    fields = ("nombre", "imagen")
    context_object_name = "categoria"
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


class Categoria_PTDeleteView(DeleteView):
    model = CategoriaProductoTerminado
    template_name = "deposito/categoria_producto_terminado_confirm_delete.html"
    context_object_name = "categoria"  # 'categoria' se usa en la plantilla
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasar los productos terminados asociados a la plantilla para información
        context["productos_asociados_count"] = self.object.productos_terminados.count()
        if context["productos_asociados_count"] > 0:
            # Pasar una lista pequeña para mostrar ejemplos si es necesario,
            # aunque el mensaje de error ya los listará si ocurre el ProtectedError.
            context["productos_ejemplo"] = self.object.productos_terminados.all()[
                :5
            ]  # Muestra hasta 5 ejemplos
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # Es importante tener el objeto disponible
        nombre_categoria = self.object.nombre  # Guardar nombre para el mensaje de éxito

        try:
            # super().delete() es lo que realmente llama al self.object.delete()
            response = super().delete(request, *args, **kwargs)
            messages.success(
                request,
                f"Categoría de Producto Terminado '{nombre_categoria}' eliminada exitosamente.",
            )
            return response
        except ProtectedError as e:
            # Construir un mensaje detallado
            nombres_productos_protegidos = [str(pt) for pt in e.protected_objects]
            mensaje_error = (
                f"No se puede eliminar la categoría '{nombre_categoria}' porque está "
                f"siendo utilizada por los siguientes productos terminados: {', '.join(nombres_productos_protegidos)}. "
                "Por favor, reasigne o elimine estos productos primero."
            )
            messages.error(request, mensaje_error)
            logger.warning(
                f"Intento fallido de eliminar CategoriaProductoTerminado ID {self.object.id} ('{nombre_categoria}') debido a ProtectedError: {e}"
            )

            # Redirigir de vuelta a la página de detalle de la categoría
            # o a la confirmación de borrado para que el usuario vea el mensaje.
            # En este caso, volvemos a la página de detalle donde el usuario puede ver los productos.
            return redirect("App_LUMINOVA:categoria_pt_detail", pk=self.object.pk)
            # Alternativa: volver a mostrar la página de confirmación (necesitaría pasar el contexto de nuevo)
            # context = self.get_context_data(object=self.object)
            # return self.render_to_response(context)


# Funciones para el CRUD de Insumos
class InsumosListView(ListView):
    model = Insumo
    template_name = "deposito/insumos_list.html"  # Para una vista de todos los insumos si es necesaria
    context_object_name = "insumos"


class InsumoDetailView(DetailView):
    model = Insumo
    template_name = "deposito/insumo_detail.html"
    context_object_name = "insumo"


class InsumoCreateView(CreateView):
    model = Insumo
    template_name = "deposito/insumo_crear.html"
    # Define los campos que SÍ están en el modelo Insumo y quieres en el formulario de creación
    fields = ["descripcion", "categoria", "fabricante", "stock", "imagen"]
    # success_url = reverse_lazy('App_LUMINOVA:deposito_view') # Redirige a la vista principal de depósito

    def form_valid(self, form):
        messages.success(
            self.request, f"Insumo '{form.instance.descripcion}' creado exitosamente."
        )
        logger.info(
            f"Insumo creado: {form.instance.descripcion} (ID: {form.instance.id}) por usuario {self.request.user.username}"
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.warning(
            f"InsumoCreateView - Formulario inválido: {form.errors.as_json()}"
        )
        messages.error(
            self.request,
            "Error al crear el insumo. Por favor, revise los campos marcados.",
        )
        return super().form_invalid(form)

    def get_initial(self):
        initial = super().get_initial()
        categoria_id = self.request.GET.get("categoria")
        if categoria_id:
            try:
                initial["categoria"] = CategoriaInsumo.objects.get(pk=categoria_id)
            except CategoriaInsumo.DoesNotExist:
                messages.warning(
                    self.request,
                    "La categoría preseleccionada para el insumo no es válida.",
                )
        return initial

    def get_success_url(self):
        # Redirigir al detalle de la categoría del insumo creado, o a la vista principal de depósito
        if hasattr(self.object, "categoria") and self.object.categoria:
            return reverse_lazy(
                "App_LUMINOVA:categoria_i_detail",
                kwargs={"pk": self.object.categoria.pk},
            )
        return reverse_lazy("App_LUMINOVA:deposito_view")


class InsumoUpdateView(UpdateView):
    model = Insumo
    template_name = "deposito/insumo_editar.html"  # Asegúrate que sea el nombre correcto de tu plantilla
    fields = [
        "descripcion",
        "categoria",
        "fabricante",
        "stock",
        "imagen",
    ]  # Lista los campos que quieres que sean editables
    # O usa un formulario personalizado:
    # form_class = InsumoForm
    context_object_name = (
        "insumo"  # Nombre del objeto en la plantilla (puedes usar 'object' también)
    )

    def get_success_url(self):
        # Redirigir al detalle de la categoría del insumo editado, o a donde prefieras
        messages.success(
            self.request,
            f"Insumo '{self.object.descripcion}' actualizado exitosamente.",
        )
        if hasattr(self.object, "categoria") and self.object.categoria:
            return reverse_lazy(
                "App_LUMINOVA:categoria_i_detail",
                kwargs={"pk": self.object.categoria.pk},
            )
        return reverse_lazy("App_LUMINOVA:deposito_view")  # Fallback

    def form_valid(self, form):
        logger.info(
            f"InsumoUpdateView: Formulario válido para insumo ID {self.object.id}. Guardando cambios."
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.warning(
            f"InsumoUpdateView: Formulario inválido para insumo ID {self.object.id if self.object else 'Nuevo'}. Errores: {form.errors.as_json()}"
        )
        messages.error(
            self.request,
            "Hubo errores al intentar guardar el insumo. Por favor, revise los campos.",
        )
        return super().form_invalid(form)


class InsumoDeleteView(DeleteView):
    model = Insumo
    template_name = "deposito/insumo_confirm_delete.html"
    context_object_name = "insumo"
    # success_url = reverse_lazy('App_LUMINOVA:deposito_view') # success_url se maneja en get_success_url

    def get_success_url(self):
        # Redirigir al detalle de la categoría del insumo eliminado, o a la vista principal de depósito
        if (
            hasattr(self.object, "categoria") and self.object.categoria
        ):  # self.object es el insumo borrado
            return reverse_lazy(
                "App_LUMINOVA:categoria_i_detail",
                kwargs={"pk": self.object.categoria.pk},
            )
        return reverse_lazy("App_LUMINOVA:deposito_view")

    def form_valid(self, form):
        # Este método se llama DESPUÉS de que la eliminación fue exitosa (si no hay ProtectedError)
        # Aquí se guarda el nombre para usarlo en el mensaje ANTES de que self.object se elimine completamente.
        insumo_descripcion = self.object.descripcion
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"El insumo '{insumo_descripcion}' ha sido eliminado exitosamente.",
        )
        return response

    def post(self, request, *args, **kwargs):
        self.object = (
            self.get_object()
        )  # Cargar el objeto para tener acceso a él en caso de error
        try:
            # Intenta llamar al método delete de la clase base, que es lo que realmente borra
            # y donde se podría lanzar ProtectedError.
            # Si la eliminación es exitosa, se llamará a form_valid y luego a get_success_url.
            return super().delete(request, *args, **kwargs)
        except ProtectedError as e:
            # Construir un mensaje más detallado sobre qué está protegiendo la eliminación
            protecting_objects = []
            if hasattr(
                e, "protected_objects"
            ):  # e.protected_objects contiene los objetos que causan la protección
                for obj in e.protected_objects:
                    if isinstance(obj, ComponenteProducto):
                        protecting_objects.append(
                            f"el producto terminado '{obj.producto_terminado.descripcion}' (usa {obj.cantidad_necesaria} unidades)"
                        )
                    else:
                        protecting_objects.append(str(obj))  # Representación genérica

            error_message = f"No se puede eliminar el insumo '{self.object.descripcion}' porque está referenciado y protegido."
            if protecting_objects:
                error_message += (
                    " Específicamente, es usado por: "
                    + ", ".join(protecting_objects)
                    + "."
                )
            error_message += (
                " Por favor, primero elimine o modifique estas referencias."
            )

            messages.error(request, error_message)
            # Redirigir de vuelta a la página de confirmación de borrado o a una página relevante
            # Podrías redirigir al detalle del insumo o a la lista donde el usuario pueda ver el error
            # o incluso a la página desde donde vino.
            # Para simplificar, redirigimos a donde iría si la eliminación fuera exitosa (ej. la categoría o depósito)
            # para que vea el mensaje de error allí.
            if hasattr(self.object, "categoria") and self.object.categoria:
                return redirect(
                    reverse_lazy(
                        "App_LUMINOVA:categoria_i_detail",
                        kwargs={"pk": self.object.categoria.pk},
                    )
                )
            return redirect(reverse_lazy("App_LUMINOVA:deposito_view"))


# Funciones para el CRUD de Productos Terminados
class ProductoTerminadosListView(ListView):
    model = ProductoTerminado
    template_name = "deposito/productoterminados_list.html"  # Para una vista de todos los PT si es necesaria
    context_object_name = "productos_terminados"


class ProductoTerminadoDetailView(DetailView):
    model = ProductoTerminado
    template_name = "deposito/productoterminado_detail.html"
    context_object_name = "producto_terminado"


class ProductoTerminadoCreateView(CreateView):
    model = ProductoTerminado
    template_name = "deposito/productoterminado_crear.html"
    fields = "__all__"
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


class ProductoTerminadoUpdateView(UpdateView):
    model = ProductoTerminado
    template_name = "deposito/productoterminado_editar.html"
    fields = "__all__"
    context_object_name = "producto_terminado"

    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


class ProductoTerminadoDeleteView(DeleteView):
    model = ProductoTerminado
    template_name = "deposito/productoterminado_confirm_delete.html"
    context_object_name = "producto_terminado"
    # success_url = reverse_lazy('App_LUMINOVA:deposito_view') # Se manejará con get_success_url

    def get_success_url(self):
        # Redirigir al detalle de la categoría del producto, o a la vista principal de depósito
        if hasattr(self.object, "categoria") and self.object.categoria:
            return reverse_lazy(
                "App_LUMINOVA:categoria_pt_detail",
                kwargs={"pk": self.object.categoria.pk},
            )
        return reverse_lazy("App_LUMINOVA:deposito_view")

    def form_valid(self, form):
        # Guardar descripción para el mensaje antes de borrar
        producto_descripcion = self.object.descripcion
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"El producto terminado '{producto_descripcion}' ha sido eliminado exitosamente.",
        )
        return response

    def post(self, request, *args, **kwargs):
        self.object = (
            self.get_object()
        )  # Cargar el objeto para tener acceso a él en caso de error
        try:
            return super().delete(request, *args, **kwargs)
        except ProtectedError as e:
            protecting_objects_details = []
            if hasattr(e, "protected_objects"):
                for obj in e.protected_objects:
                    if isinstance(obj, ItemOrdenVenta):
                        protecting_objects_details.append(
                            f"la Orden de Venta N° {obj.orden_venta.numero_ov}"
                        )
                    elif isinstance(obj, OrdenProduccion):
                        protecting_objects_details.append(
                            f"la Orden de Producción N° {obj.numero_op}"
                        )
                    # Añade más 'elif isinstance' si ProductoTerminado es FK en otros modelos con PROTECT
                    else:
                        protecting_objects_details.append(
                            f"un registro del tipo '{obj.__class__.__name__}'"
                        )

            error_message = f"No se puede eliminar el producto terminado '{self.object.descripcion}' porque está referenciado y protegido."
            if protecting_objects_details:
                error_message += (
                    " Específicamente, es usado por: "
                    + ", ".join(protecting_objects_details)
                    + "."
                )
            error_message += (
                " Por favor, primero elimine o modifique estas referencias."
            )

            messages.error(request, error_message)
            # Redirigir de vuelta a una página relevante donde se muestre el mensaje
            if hasattr(self.object, "categoria") and self.object.categoria:
                return redirect(
                    reverse_lazy(
                        "App_LUMINOVA:categoria_pt_detail",
                        kwargs={"pk": self.object.categoria.pk},
                    )
                )
            return redirect(reverse_lazy("App_LUMINOVA:deposito_view"))


class ProveedorListView(ListView):
    model = Proveedor
    template_name = "ventas/proveedores/proveedor_list.html"
    context_object_name = "proveedores"


class ProveedorDetailView(DetailView):
    model = Proveedor
    template_name = "ventas/proveedores/proveedor_detail.html"
    context_object_name = "proveedor"


class ProveedorUpdateView(UpdateView):
    model = Proveedor
    template_name = "ventas/proveedores/proveedor_editar.html"
    fields = "__all__"
    context_object_name = "proveedor"
    success_url = reverse_lazy("App_LUMINOVA:proveedor_list")


class ProveedorDeleteView(DeleteView):
    model = Proveedor
    template_name = "ventas/proveedores/proveedor_confirm_delete.html"
    context_object_name = "proveedor"
    success_url = reverse_lazy("App_LUMINOVA:proveedor_list")


class FabricanteListView(ListView):
    model = Fabricante
    template_name = "ventas/fabricantes/fabricante_list.html"
    context_object_name = "fabricantes"


class FabricanteDetailView(DetailView):
    model = Fabricante
    template_name = "ventas/fabricantes/fabricante_detail.html"
    context_object_name = "fabricante"


class FabricanteCreateView(CreateView):
    model = Fabricante
    template_name = "ventas/fabricantes/fabricante_crear.html"
    fields = "__all__"
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


class FabricanteUpdateView(UpdateView):
    model = Fabricante
    template_name = "ventas/fabricantes/fabricante_editar.html"
    fields = "__all__"
    context_object_name = "fabricante"
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


class FabricanteDeleteView(DeleteView):
    model = Fabricante
    template_name = "ventas/fabricantes/fabricante_confirm_delete.html"
    context_object_name = "fabricante"
    success_url = reverse_lazy("App_LUMINOVA:deposito_view")


# --- PDF VIEW ---
@login_required
def ventas_ver_factura_pdf_view(request, factura_id):
    """
    Vista que obtiene los datos de una factura y delega la generación
    del PDF a un servicio dedicado.
    """
    try:
        # Esta consulta optimizada busca todo lo necesario de una vez
        factura = (
            Factura.objects.select_related(
                "orden_venta__cliente"
            )
            .prefetch_related(
                Prefetch(
                    "orden_venta__items_ov",
                    queryset=ItemOrdenVenta.objects.select_related("producto_terminado"),
                )
            )
            .get(id=factura_id)
        )
    except Factura.DoesNotExist:
        messages.error(request, "La factura solicitada no existe.")
        return redirect("App_LUMINOVA:ventas_lista_ov")

    # Llamamos a nuestro servicio y retornamos directamente su respuesta
    return generar_pdf_factura(factura)


# --- CONTROL DE CALIDAD (Placeholder) ---
@login_required
def control_calidad_view(request):
    return render(request, "control_calidad/control_calidad.html")
