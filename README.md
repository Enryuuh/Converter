# Converter

Aplicacion de escritorio para convertir imagenes por lote entre formatos comunes:
PNG, JPG, JPEG, WEBP, AVIF, BMP, TIFF, GIF, ICO y PDF.

Descarga la version para Windows desde [GitHub Releases](https://github.com/Enryuuh/Converter/releases/latest).

Permite agregar imagenes con botones o arrastrando archivos/carpetas a la zona superior.
La tabla muestra el tipo detectado, tamano, modo de color y ruta de cada archivo.

## Funciones

- Vista previa de la imagen seleccionada.
- Drag and drop de archivos y carpetas, incluyendo subcarpetas.
- Feedback de formato real, dimensiones, peso, transparencia y frames animados.
- Barra de progreso y estado por archivo.
- Historial de conversiones y errores.
- Redimensionado con o sin proporcion.
- Fondo configurable para formatos sin transparencia como JPG, BMP y PDF.
- Presets: web, maxima calidad, reducir peso, icono ICO y PDF desde imagenes.
- Renombrado por lote: conservar, numerar o prefijo/sufijo.
- Opcion para sobrescribir o crear nombres nuevos automaticamente.
- Boton para abrir la carpeta de salida.
- Interfaz moderna con logo propio y nombre `Converter`.
- Cache de metadatos y conversion optimizada para no procesar frames innecesarios.

## Crear el .exe

En PowerShell:

```powershell
.\build_exe.ps1
```

El ejecutable queda en:

```text
dist\Converter.exe
```

## Ejecutar sin compilar

```powershell
python -m pip install -r requirements.txt
python app.py
```

## Notas

- Al convertir a JPG, BMP o PDF, la transparencia se reemplaza con fondo blanco.
- Para GIF, WEBP, TIFF y PDF se intenta conservar multiples frames cuando la imagen origen los tiene.
- La compatibilidad exacta depende de Pillow y de los codecs disponibles en Windows.
