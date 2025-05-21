# Proyecto Luminova

Este es un proyecto Django para la gestión de usuarios, roles y auditorías. Este repositorio está diseñado para que varios colaboradores trabajen juntos en el desarrollo del proyecto.

## Requisitos previos

- Python 3.12 o superior
- pip (gestor de paquetes de Python)
- Entorno virtual (opcional pero recomendado)

## Instalación

1. Clona este repositorio:
   ```bash
   git clone
https://github.com/tu-usuario/tu-repositorio.git

   cd tu-repositorio
   ```

2. Crea un entorno virtual:
   ```bash
   python -m venv env       # En Windows
   python3 -m venv env      # En Linux/Mac

   env\Scripts\activate     # En Windows
   source env/bin/activate  # En Linux/Mac
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Realiza las migraciones de la base de datos:
   ```bash
   python manage.py migrate
   ```

5. Inicia el servidor de desarrollo:
   ```bash
   python manage.py runserver
   ```

## Flujo de trabajo para colaboradores

1. **Haz un fork del repositorio (si no tienes acceso directo)😗*
   - Ve a la página del repositorio en GitHub y haz clic en el botón "Fork".

2. **Clona el repositorio (o tu fork)😗*
   ```bash
   git clone
https://github.com/tu-usuario/tu-repositorio.git

   cd tu-repositorio
   ```

3. **Crea una rama para tu funcionalidad o corrección😗*
   ```bash
   git checkout -b nombre-de-la-rama
   ```

4. **Realiza tus cambios y haz commits😗*
   ```bash
   git add .
   git commit -m "Descripción de los cambios realizados"
   ```

5. **Envía tus cambios al repositorio remoto😗*
   ```bash
   git push origin nombre-de-la-rama
   ```

6. **Abre un Pull Request😗*
   - Ve al repositorio en GitHub y abre un Pull Request desde tu rama.

## Buenas prácticas para colaborar

- Asegúrate de que tu código esté limpio y bien documentado.
- Antes de trabajar en una nueva funcionalidad, verifica que no haya conflictos con la rama principal (`main`).
- Realiza pruebas locales antes de enviar tus cambios.
- Usa mensajes de commit claros y descriptivos.

## Estructura del proyecto

- **`App_Luminova/`**: Contiene la aplicación principal del proyecto.
- **`templates/`**: Contiene las plantillas HTML.
- **`static/`**: Contiene los archivos estáticos como CSS, JavaScript e imágenes.
- **`requirements.txt`**: Lista de dependencias necesarias para ejecutar el proyecto.

## Contacto

Si tienes preguntas o necesitas ayuda, no dudes en abrir un issue en el repositorio o contactar al administrador del proyecto.



superuser {
    username: Federico_Paal
    email: federicopaal@gmail.com
    password: 123456
    password (again): 123456
}