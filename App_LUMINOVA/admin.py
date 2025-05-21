from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(ProductoTerminado)
admin.site.register(Insumo)
admin.site.register(Orden)
admin.site.register(Usuario)
admin.site.register(Proveedor)
admin.site.register(Cliente)
admin.site.register(Factura)

# Registro del modelo RolDescripcion en el admin de Django
from django.contrib import admin
from .models import RolDescripcion

admin.site.register(RolDescripcion)