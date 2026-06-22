# Converter

Aplicacion de escritorio para convertir imagenes por lote entre formatos comunes:
PNG, JPG, JPEG, WEBP, AVIF, BMP, TIFF, GIF, ICO, PDF y SVG.
Tambien importa RAW de camara comunes como DNG, CR2, CR3, NEF, ARW, RAF, ORF, RW2 y SRW para convertirlos a formatos normales.

Descarga la version para Windows desde [GitHub Releases](https://github.com/Enryuuh/Converter/releases/latest).

Permite agregar imagenes con botones o arrastrando archivos/carpetas a la zona superior.
Al agregar carpetas, detecta imagenes por extension y tambien por contenido cuando el archivo viene sin extension o con una extension rara.
La tabla muestra el tipo real detectado, tamano, modo de color y ruta de cada archivo.

## Funciones

- Vista previa de la imagen seleccionada.
- Miniaturas en la cola para identificar fotos rapido.
- Peso estimado automatico de la imagen seleccionada antes de convertir.
- Peso estimado por archivo directamente en la cola.
- Cache compartido de estimaciones para evitar recalcular el mismo formato varias veces.
- Comparacion antes/despues con peso estimado de salida.
- Comparacion con fondo cuadriculado para transparencias y zoom rapido.
- Peso real mostrado en la cola al terminar cada archivo.
- Estimacion de peso y ahorro total para todo el lote antes de convertir.
- Analisis de lote por formato con ahorro estimado.
- Barra de progreso total y barra del archivo actual.
- Pausar/reanudar conversiones, cancelar y reintentar solo archivos con error.
- Drag and drop de archivos y carpetas, incluyendo subcarpetas.
- Filtros por estado, formato, peso original, busqueda por nombre/ruta y orden por nombre, peso, formato, estado o tamano.
- Reordenar la cola arrastrando filas o con botones Subir/Bajar.
- Deteccion de duplicados por contenido al agregar archivos o carpetas.
- Vista previa de rutas de salida en tabla antes de convertir.
- Guardado y restauracion automatica de la sesion de cola.
- Avisos visuales en detalle para RAW, transparencia, animados, archivos pesados o problemas.
- Panel dedicado de errores con reintento y copiado de detalles.
- Reportes TXT, CSV y HTML al terminar cada conversion.
- ZIP final opcional con todos los archivos generados.
- Presets para web, Instagram, WhatsApp, impresion, producto, SVG, fondo transparente, ahorro maximo, sin perdida, ICO y PDF.
- Autodeteccion por contenido para imagenes sin extension o con extension no estandar.
- Importacion de RAW de camara mediante `rawpy`/LibRaw.
- Quitar fondo para fondos limpios conectados a los bordes.
- Quitar fondo mejorado con deteccion desde mas puntos del borde, sin modelos pesados de IA.
- Suavizado configurable del borde al quitar fondo.
- Salida SVG vectorial simplificada y mas compacta para logos e ilustraciones.
- Edicion basica por lote: rotar, voltear, recortar bordes, ajustar brillo/contraste/saturacion y crear lienzo cuadrado.
- Feedback de formato real, dimensiones, peso, transparencia y frames animados.
- Estado por archivo en la cola: pendiente, procesando, OK, error o cancelado.
- Reordenar la cola con botones para subir y bajar imagenes.
- Barra de progreso y estado por archivo.
- Conversion paralela configurable.
- Conversion a varios formatos en una sola corrida usando `Formatos extra`.
- Regla para archivos pesados: si superan cierto KB, usar una calidad mas agresiva.
- Cancelacion de conversion en curso.
- Repetir la ultima conversion.
- Historial de conversiones y errores con exportacion a TXT.
- Redimensionado con o sin proporcion.
- Mantener estructura de carpetas al convertir directorios completos.
- Guardar en subcarpeta automatica `Converter_Output`.
- Compresion por peso objetivo en KB para formatos con calidad configurable.
- Aviso cuando el peso objetivo no se puede alcanzar sin cambiar dimensiones/formato.
- Los avisos de peso objetivo no marcan como error los archivos generados correctamente.
- Fondo configurable para formatos sin transparencia como JPG, BMP y PDF.
- Opcion para quitar o conservar metadatos EXIF cuando el formato lo soporta.
- Apertura automatica de la carpeta de salida al terminar.
- Ajustes rapidos: web, maxima calidad, reducir peso, icono ICO y PDF desde imagenes.
- Perfiles personalizados guardados en el equipo.
- Importacion y exportacion de perfiles en JSON.
- Exportacion de un solo perfil, perfiles default integrados y restauracion rapida de ajustes.
- Archivos `.converterprofile` para importar perfiles abriendolos con Converter.
- Importacion y exportacion de ajustes completos en JSON.
- Ajustes guardados automaticamente en `%APPDATA%\Converter\settings.json`.
- Logs persistentes en `%APPDATA%\Converter\converter.log`.
- Cache persistente de metadatos para acelerar carpetas grandes.
- Renombrado por lote: conservar, numerar o prefijo/sufijo.
- Opcion para sobrescribir o crear nombres nuevos automaticamente.
- Boton para abrir la carpeta de salida.
- Interfaz moderna con logo propio y nombre `Converter`.
- Modo nocturno/claro con cambio desde la cabecera.
- Modo compacto/completo y modo bajo consumo.
- Tooltips y guia integrada para explicar cada opcion de salida.
- Menu contextual opcional de Windows para abrir archivos o carpetas desde clic derecho.
- Menu contextual opcional tambien desde el instalador.
- Instalador con opcion portable y asociacion de `.converterprofile`.
- El modo portable cae a `%APPDATA%\Converter` si la carpeta instalada no permite escritura.
- Auto-update: revisa GitHub Releases y descarga instalador, EXE o ZIP portable desde la app.
- Panel de integridad con ruta y SHA256 del binario actual.
- PDF con tamano de pagina Original, A4 o Carta y orientacion automatica.
- Modo CLI: convierte desde terminal con `Converter.exe archivo.png --to webp`.
- ZIP portable oficial en Releases y modo portable creando `portable.flag` junto al ejecutable.
- Campos contextuales: las opciones que no aplican se desactivan automaticamente.
- Cache de metadatos y conversion optimizada para no procesar frames innecesarios.
- Verificacion de actualizaciones contra GitHub Releases.
- Carga de metadatos en segundo plano para no congelar la interfaz con carpetas grandes.
- Escaneos antiguos se descartan si limpias/restauras la cola mientras siguen trabajando.
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

Este paso actualiza `dist\checksums-sha256.txt` para el ejecutable y el instalador locales.

## Paquete portable

El release automatico tambien publica:

```text
dist\ConverterPortable.zip
```

Incluye `Converter.exe` y `portable.flag`, por lo que guarda datos en la carpeta `data` junto al ejecutable.

## Firma digital opcional

El proyecto incluye `scripts\sign_windows.ps1`. Si defines estos secrets en GitHub, el workflow firma los binarios automaticamente:

- `WINDOWS_CERTIFICATE_BASE64`: certificado PFX codificado en base64.
- `WINDOWS_CERTIFICATE_PASSWORD`: clave del certificado.

Si esos secrets no existen, el workflow publica el release sin firma. En ese caso Windows puede mostrar una advertencia de "editor desconocido".

## Releases automaticos

El workflow `.github/workflows/release.yml` construye `Converter.exe`, `ConverterSetup.exe`, `ConverterPortable.zip` y publica todos como assets cuando se sube un tag:

```powershell
git tag v1.3.10
git push origin v1.3.10
```

Cada release incluye `checksums-sha256.txt` para verificar la integridad de `Converter.exe`, `ConverterSetup.exe` y `ConverterPortable.zip`.

## Ejecutar sin compilar

```powershell
python -m pip install -r requirements.txt
python app.py
```

Modo CLI:

```powershell
python app.py foto.png --to webp --output .\salida --quality 80
```

## Notas

- Al convertir a JPG, BMP o PDF, la transparencia se reemplaza con fondo blanco.
- Para GIF, WEBP, TIFF y PDF se intenta conservar multiples frames cuando la imagen origen los tiene.
- RAW funciona como entrada, no como formato de salida. Converter revela el RAW a RGB y lo exporta a JPG, PNG, WEBP, AVIF, TIFF, PDF u otros formatos soportados.
- SVG es vectorizacion simplificada por formas de color; funciona mejor con logos, iconos e ilustraciones que con fotografia compleja.
- Quitar fondo funciona mejor con fondos de estudio, blancos o planos. Para fondos muy complejos se necesitaria segmentacion por IA.
- El menu contextual se instala desde la app en el usuario actual, sin permisos de administrador.
- Para modo portable, crea un archivo vacio llamado `portable.flag` junto al ejecutable; los ajustes se guardaran en `data`.
- La compatibilidad exacta depende de Pillow y de los codecs disponibles en Windows.
