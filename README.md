# Converter

Aplicacion de escritorio para convertir imagenes por lote entre formatos comunes:
PNG, JPG, JPEG, WEBP, AVIF, BMP, TIFF, GIF, ICO y PDF.

Descarga la version para Windows desde [GitHub Releases](https://github.com/Enryuuh/Converter/releases/latest).

Permite agregar imagenes con botones o arrastrando archivos/carpetas a la zona superior.
La tabla muestra el tipo detectado, tamano, modo de color y ruta de cada archivo.

## Funciones

- Vista previa de la imagen seleccionada.
- Comparacion antes/despues con peso estimado de salida.
- Estimacion de peso para todo el lote antes de convertir.
- Drag and drop de archivos y carpetas, incluyendo subcarpetas.
- Feedback de formato real, dimensiones, peso, transparencia y frames animados.
- Estado por archivo en la cola: pendiente, procesando, OK, error o cancelado.
- Reordenar la cola con botones para subir y bajar imagenes.
- Barra de progreso y estado por archivo.
- Conversion paralela configurable.
- Conversion a varios formatos en una sola corrida usando `Formatos extra`.
- Cancelacion de conversion en curso.
- Historial de conversiones y errores con exportacion a TXT.
- Redimensionado con o sin proporcion.
- Compresion por peso objetivo en KB para formatos con calidad configurable.
- Aviso cuando el peso objetivo no se puede alcanzar sin cambiar dimensiones/formato.
- Fondo configurable para formatos sin transparencia como JPG, BMP y PDF.
- Opcion para quitar o conservar metadatos EXIF cuando el formato lo soporta.
- Apertura automatica de la carpeta de salida al terminar.
- Presets: web, maxima calidad, reducir peso, icono ICO y PDF desde imagenes.
- Perfiles personalizados guardados en el equipo.
- Ajustes guardados automaticamente en `%APPDATA%\Converter\settings.json`.
- Logs persistentes en `%APPDATA%\Converter\converter.log`.
- Renombrado por lote: conservar, numerar o prefijo/sufijo.
- Opcion para sobrescribir o crear nombres nuevos automaticamente.
- Boton para abrir la carpeta de salida.
- Interfaz moderna con logo propio y nombre `Converter`.
- Modo nocturno/claro con cambio desde la cabecera.
- Cache de metadatos y conversion optimizada para no procesar frames innecesarios.
- Verificacion de actualizaciones contra GitHub Releases.
- Carga de metadatos en segundo plano para no congelar la interfaz con carpetas grandes.
- Build aislado en `.venv-build` para evitar empaquetar dependencias globales innecesarias.
- Compresion por peso objetivo optimizada con busqueda binaria de calidad.

## Crear el .exe

En PowerShell:

```powershell
.\build_exe.ps1
```

El ejecutable queda en:

```text
dist\Converter.exe
```

El build usa un entorno virtual local `.venv-build` para generar un binario mas limpio y consistente.
Para publicar una version se recomienda usar el workflow de GitHub, porque tambien genera instalador y checksums SHA256.

## Crear instalador

Requiere Inno Setup 6 instalado y disponible como `iscc`:

```powershell
.\build_installer.ps1
```

El instalador queda en:

```text
dist\ConverterSetup.exe
```

## Firma digital opcional

El proyecto incluye `scripts\sign_windows.ps1`. Si defines estos secrets en GitHub, el workflow firma los binarios automaticamente:

- `WINDOWS_CERTIFICATE_BASE64`: certificado PFX codificado en base64.
- `WINDOWS_CERTIFICATE_PASSWORD`: clave del certificado.

Si esos secrets no existen, el workflow publica el release sin firma. En ese caso Windows puede mostrar una advertencia de "editor desconocido".

## Releases automaticos

El workflow `.github/workflows/release.yml` construye `Converter.exe`, `ConverterSetup.exe` y publica ambos como assets cuando se sube un tag:

```powershell
git tag v1.3.0
git push origin v1.3.0
```

Cada release incluye `checksums-sha256.txt` para verificar la integridad de `Converter.exe` y `ConverterSetup.exe`.

## Ejecutar sin compilar

```powershell
python -m pip install -r requirements.txt
python app.py
```

## Notas

- Al convertir a JPG, BMP o PDF, la transparencia se reemplaza con fondo blanco.
- Para GIF, WEBP, TIFF y PDF se intenta conservar multiples frames cuando la imagen origen los tiene.
- La compatibilidad exacta depende de Pillow y de los codecs disponibles en Windows.
