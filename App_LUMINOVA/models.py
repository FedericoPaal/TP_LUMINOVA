from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class CategoriaProductoTerminado(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    imagen = models.ImageField(upload_to='categorias_productos/', null=True, blank=True)

    class Meta:
        verbose_name = "Categoría de Producto Terminado"
        verbose_name_plural = "Categorías de Productos Terminados"

    def __str__(self):
        return self.nombre

class ProductoTerminado(models.Model):
    descripcion = models.CharField(max_length=100)
    categoria = models.ForeignKey(CategoriaProductoTerminado, on_delete=models.CASCADE, related_name='productos_terminados')
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField()
    modelo = models.CharField(max_length=50)
    potencia = models.IntegerField()
    acabado = models.CharField(max_length=50)
    color_luz = models.CharField(max_length=50)
    material = models.CharField(max_length=50)
    imagen = models.ImageField(null=True, blank=True, upload_to='productos_terminados')

    def __str__(self):
        return self.descripcion

class CategoriaInsumo(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    imagen = models.ImageField(upload_to='categorias_insumos/', null=True, blank=True)

    class Meta:
        verbose_name = "Categoría de Insumo"
        verbose_name_plural = "Categorías de Insumos"

    def __str__(self):
        return self.nombre

class Insumo(models.Model):
    descripcion = models.CharField(max_length=100)
    categoria = models.ForeignKey(CategoriaInsumo, on_delete=models.CASCADE, related_name='insumos')
    fabricante = models.CharField(max_length=60)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    tiempo_entrega = models.IntegerField() # Tiempo de entrega en días
    imagen = models.ImageField(null=True, blank=True, upload_to='insumos')
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