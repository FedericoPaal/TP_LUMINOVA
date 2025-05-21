from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class ProductoTerminado(models.Model):
    descripcion = models.CharField(max_length=100)
    categoria = models.CharField(max_length=50)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField()
    modelo = models.CharField(max_length=50)
    potencia = models.IntegerField()
    acabado = models.CharField(max_length=50)
    color_luz = models.CharField(max_length=50)
    material = models.CharField(max_length=50)
    imagen = models.ImageField(null=True, blank=True)

    def __str__(self):
        return self.descripcion

class Insumo(models.Model):
    descripcion = models.CharField(max_length=100)
    categoria = models.CharField(max_length=50)
    fabricante = models.CharField(max_length=60)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    tiempo_entrega = models.IntegerField() # Tiempo de entrega en días
    imagen = models.ImageField(null=True, blank=True)
    proveedor = models.CharField(max_length=60)
    stock = models.IntegerField()

    def __str__(self):
        return f"{self.descripcion}"

class Orden(models.Model):
    TIPO_ORDEN_CHOICES = [
        ('produccion', 'Orden de Producción'),
        ('compra', 'Orden de Compra'),
        ('venta', 'Orden de Venta'),
    ]

    numero_orden = models.CharField(max_length=20)
    fecha = models.DateField()
    cliente = models.CharField(max_length=100)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    tipo = models.CharField(max_length=20, choices=TIPO_ORDEN_CHOICES)

    def __str__(self):
        return f"{self.numero_orden} - {self.get_tipo_display()}"

class Usuario(models.Model):
    nombre = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    rol = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre

class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    contacto = models.CharField(max_length=100)
    telefono = models.CharField(max_length=15)
    email = models.EmailField()

    def __str__(self):
        return self.nombre

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.TextField()
    telefono = models.CharField(max_length=15)
    email = models.EmailField()

    def __str__(self):
        return self.nombre

class Factura(models.Model):
    numero_factura = models.CharField(max_length=20)
    fecha = models.DateField()
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.numero_factura


# Creacion del modelo RolDescripcion
from django.db import models
from django.contrib.auth.models import Group

class RolDescripcion(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='descripcion_extendida')
    descripcion = models.TextField("Descripción del rol", blank=True)

    def __str__(self):
        return f"{self.group.name}"

# Creacion del modelo AuditoriaAcceso
class AuditoriaAcceso(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    accion = models.CharField(max_length=100)
    fecha_hora = models.DateTimeField(auto_now_add=True)