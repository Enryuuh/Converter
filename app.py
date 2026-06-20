from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageColor, ImageSequence, ImageTk, UnidentifiedImageError

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    TkBase = TkinterDnD.Tk
    DND_AVAILABLE = True
except Exception:
    DND_FILES = None
    TkBase = tk.Tk
    DND_AVAILABLE = False

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    pass


APP_NAME = "Converter"
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
LOGO_PNG = BASE_DIR / "assets" / "converter-logo.png"
LOGO_ICO = BASE_DIR / "assets" / "converter-logo.ico"

SUPPORTED_INPUT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".ico",
    ".heic",
    ".heif",
    ".ppm",
    ".pgm",
    ".pbm",
    ".avif",
}

OUTPUT_FORMATS = {
    "PNG": {"ext": ".png", "save_format": "PNG", "supports_alpha": True, "quality": False},
    "JPG": {"ext": ".jpg", "save_format": "JPEG", "supports_alpha": False, "quality": True},
    "JPEG": {"ext": ".jpeg", "save_format": "JPEG", "supports_alpha": False, "quality": True},
    "WEBP": {"ext": ".webp", "save_format": "WEBP", "supports_alpha": True, "quality": True},
    "AVIF": {"ext": ".avif", "save_format": "AVIF", "supports_alpha": True, "quality": True},
    "BMP": {"ext": ".bmp", "save_format": "BMP", "supports_alpha": False, "quality": False},
    "TIFF": {"ext": ".tiff", "save_format": "TIFF", "supports_alpha": True, "quality": False},
    "GIF": {"ext": ".gif", "save_format": "GIF", "supports_alpha": True, "quality": False},
    "ICO": {"ext": ".ico", "save_format": "ICO", "supports_alpha": True, "quality": False},
    "PDF": {"ext": ".pdf", "save_format": "PDF", "supports_alpha": False, "quality": False},
}

INPUT_FILE_TYPES = [
    (
        "Imagenes",
        "*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff *.ico *.heic *.heif *.ppm *.pgm *.pbm *.avif",
    ),
    ("Todos los archivos", "*.*"),
]


@dataclass(frozen=True)
class ConversionOptions:
    output_format: str
    quality: int
    output_dir: Path
    resize_enabled: bool
    width: int | None
    height: int | None
    keep_aspect: bool
    background: tuple[int, int, int]
    naming_mode: str
    prefix: str
    suffix: str
    overwrite: bool
    combine_pdf: bool


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS


def describe_image(path: Path) -> tuple[str, str, str, str]:
    try:
        with Image.open(path) as image:
            image_format = image.format or path.suffix.replace(".", "").upper() or "DESCONOCIDO"
            dimensions = f"{image.width} x {image.height}"
            details = image.mode
            if "A" in image.mode or "transparency" in image.info:
                details += ", transparencia"
            if getattr(image, "is_animated", False):
                details += f", {getattr(image, 'n_frames', 1)} frames"
            weight = format_size(path.stat().st_size)
            return image_format, dimensions, details, weight
    except Exception:
        extension = path.suffix.replace(".", "").upper() or "DESCONOCIDO"
        return extension, "No detectado", "No se pudo leer", format_size(path.stat().st_size) if path.exists() else "-"


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def safe_name_part(text: str) -> str:
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if char in invalid else char for char in text.strip())
    return cleaned


def build_output_path(source: Path, output_dir: Path, options: ConversionOptions, index: int) -> Path:
    suffix = OUTPUT_FORMATS[options.output_format]["ext"]
    stem = source.stem
    if options.naming_mode == "Numerado":
        stem = f"{index:03d}_{stem}"
    elif options.naming_mode == "Prefijo/sufijo":
        stem = f"{safe_name_part(options.prefix)}{stem}{safe_name_part(options.suffix)}"

    candidate = output_dir / f"{stem}{suffix}"
    if options.overwrite:
        return candidate

    counter = 1
    while candidate.exists():
        candidate = output_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def resize_image(image: Image.Image, options: ConversionOptions) -> Image.Image:
    if not options.resize_enabled:
        return image.copy()

    width = options.width
    height = options.height
    if not width and not height:
        return image.copy()

    original_width, original_height = image.size
    if options.keep_aspect:
        if width and height:
            ratio = min(width / original_width, height / original_height)
        elif width:
            ratio = width / original_width
        else:
            ratio = height / original_height
        new_size = (max(1, round(original_width * ratio)), max(1, round(original_height * ratio)))
    else:
        new_size = (width or original_width, height or original_height)

    if new_size == image.size:
        return image.copy()
    return image.resize(new_size, Image.Resampling.LANCZOS)


def flatten_alpha(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (*background, 255))
        canvas.alpha_composite(rgba)
        return canvas.convert("RGB")

    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def prepare_frame(image: Image.Image, options: ConversionOptions) -> Image.Image:
    output_format = options.output_format
    supports_alpha = OUTPUT_FORMATS[output_format]["supports_alpha"]
    resized = resize_image(image, options)

    if not supports_alpha:
        return flatten_alpha(resized, options.background)
    if output_format == "GIF":
        return resized.convert("P", palette=Image.Palette.ADAPTIVE)
    if output_format == "ICO":
        return resized.convert("RGBA")
    return resized.copy()


def convert_image(source: Path, destination: Path, options: ConversionOptions) -> Path:
    save_format = OUTPUT_FORMATS[options.output_format]["save_format"]

    with Image.open(source) as image:
        preserve_frames = getattr(image, "is_animated", False) and options.output_format in {"GIF", "WEBP", "TIFF", "PDF"}
        if preserve_frames:
            frames = [prepare_frame(frame, options) for frame in ImageSequence.Iterator(image)]
        else:
            frames = [prepare_frame(image, options)]
        first = frames[0]

        save_kwargs = {}
        if OUTPUT_FORMATS[options.output_format]["quality"]:
            save_kwargs["quality"] = options.quality
            save_kwargs["optimize"] = True

        if options.output_format == "PNG":
            save_kwargs["optimize"] = True
        if options.output_format == "TIFF":
            save_kwargs["compression"] = "tiff_deflate"

        if preserve_frames and len(frames) > 1:
            save_kwargs["save_all"] = True
            save_kwargs["append_images"] = frames[1:]
            if options.output_format in {"GIF", "WEBP"}:
                save_kwargs["duration"] = image.info.get("duration", 100)
                save_kwargs["loop"] = image.info.get("loop", 0)

        first.save(destination, save_format, **save_kwargs)
    return destination


def combine_images_to_pdf(files: list[Path], destination: Path, options: ConversionOptions) -> Path:
    pages: list[Image.Image] = []
    for source in files:
        with Image.open(source) as image:
            first_frame = next(ImageSequence.Iterator(image))
            pages.append(flatten_alpha(resize_image(first_frame, options), options.background))

    if not pages:
        raise ValueError("No hay imagenes para PDF.")

    first = pages[0]
    first.save(destination, "PDF", save_all=True, append_images=pages[1:])
    return destination


class ImageConverterApp(TkBase):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1240x780")
        self.minsize(1080, 700)
        if LOGO_ICO.exists():
            self.iconbitmap(LOGO_ICO)

        self.files: list[Path] = []
        self.metadata_cache: dict[Path, tuple[str, str, str, str]] = {}
        self.logo_image: ImageTk.PhotoImage | None = None
        self.preview_image: ImageTk.PhotoImage | None = None

        self.output_dir = tk.StringVar(value=str(Path.home() / "Pictures"))
        self.output_format = tk.StringVar(value="WEBP")
        self.quality = tk.IntVar(value=85)
        self.status = tk.StringVar(value="Listo para convertir. Agrega imagenes para empezar.")
        self.preview_info = tk.StringVar(value="Selecciona una imagen para ver detalles y vista previa.")
        self.resize_enabled = tk.BooleanVar(value=False)
        self.resize_width = tk.StringVar(value="")
        self.resize_height = tk.StringVar(value="")
        self.keep_aspect = tk.BooleanVar(value=True)
        self.background_hex = tk.StringVar(value="#ffffff")
        self.naming_mode = tk.StringVar(value="Conservar")
        self.prefix = tk.StringVar(value="")
        self.suffix = tk.StringVar(value="")
        self.overwrite = tk.BooleanVar(value=False)
        self.combine_pdf = tk.BooleanVar(value=False)
        self.progress = tk.DoubleVar(value=0)

        self._build_ui()
        self._refresh_quality_state()

    def _build_ui(self) -> None:
        self.colors = {
            "bg": "#f6f8fb",
            "surface": "#ffffff",
            "surface_soft": "#f8fafc",
            "line": "#e2e8f0",
            "text": "#0f172a",
            "muted": "#64748b",
            "primary": "#2563eb",
            "primary_dark": "#1d4ed8",
            "success": "#14b8a6",
            "warning": "#f59e0b",
            "drop": "#eef6ff",
            "drop_active": "#dbeafe",
        }
        self.configure(background=self.colors["bg"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=self.colors["surface"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.colors["bg"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("CardMuted.TLabel", background=self.colors["surface"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("TCombobox", padding=6)
        style.configure("TEntry", padding=6)
        style.configure("Treeview", rowheight=34, background=self.colors["surface"], fieldbackground=self.colors["surface"], borderwidth=0)
        style.configure(
            "Treeview.Heading",
            padding=(10, 10),
            background="#edf2f7",
            foreground="#334155",
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", self.colors["text"])])
        style.configure("Horizontal.TProgressbar", troughcolor="#e5e7eb", background=self.colors["primary"], bordercolor="#e5e7eb")

        header = tk.Frame(self, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["line"])
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        if LOGO_PNG.exists():
            logo = Image.open(LOGO_PNG).resize((58, 58), Image.Resampling.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(logo)
            tk.Label(header, image=self.logo_image, bg=self.colors["surface"]).grid(row=0, column=0, rowspan=2, padx=(20, 14), pady=14)
        else:
            tk.Label(header, text="C", bg=self.colors["primary"], fg="#ffffff", font=("Segoe UI", 22, "bold"), width=3).grid(
                row=0, column=0, rowspan=2, padx=(20, 14), pady=14
            )
        tk.Label(header, text="Converter", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 24, "bold")).grid(
            row=0, column=1, sticky="sw", pady=(14, 0)
        )
        tk.Label(
            header,
            text="Convierte imagenes por lote con vista previa, presets, redimensionado y salida optimizada.",
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).grid(row=1, column=1, sticky="nw", pady=(0, 14))
        actions = tk.Frame(header, bg=self.colors["surface"])
        actions.grid(row=0, column=2, rowspan=2, sticky="e", padx=20)
        self._button(actions, "Agregar imagenes", self.add_files, "primary").grid(row=0, column=0, padx=(0, 8))
        self._button(actions, "Agregar carpeta", self.add_folder).grid(row=0, column=1, padx=(0, 8))
        self._button(actions, "Abrir salida", self.open_output_dir).grid(row=0, column=2)

        summary = tk.Frame(self, bg=self.colors["bg"])
        summary.grid(row=1, column=0, sticky="ew", padx=18, pady=(14, 10))
        summary.columnconfigure(0, weight=1)
        self._stat(summary, "1", "Agrega", "Arrastra archivos o carpetas").grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._stat(summary, "2", "Ajusta", "Formato, calidad y tamano").grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self._stat(summary, "3", "Convierte", "Revisa progreso e historial").grid(row=0, column=2, sticky="ew")

        content = tk.Frame(self, bg=self.colors["bg"])
        content.grid(row=2, column=0, sticky="nsew")
        content.configure(padx=18)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        left_panel = self._card(content)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(2, weight=1)

        left_header = tk.Frame(left_panel, bg=self.colors["surface"])
        left_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        left_header.columnconfigure(0, weight=1)
        tk.Label(left_header, text="Cola de imagenes", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        queue_actions = tk.Frame(left_header, bg=self.colors["surface"])
        queue_actions.grid(row=0, column=1, sticky="e")
        self._button(queue_actions, "Quitar", self.remove_selected, "ghost").grid(row=0, column=0, padx=(0, 8))
        self._button(queue_actions, "Limpiar", self.clear_files, "ghost").grid(row=0, column=1)

        self.drop_zone = tk.Canvas(left_panel, height=94, bg=self.colors["drop"], highlightthickness=0, bd=0)
        self.drop_zone.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.drop_zone.bind("<Configure>", self._draw_drop_zone)
        if DND_AVAILABLE:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self.handle_drop)
            self.drop_zone.bind("<Enter>", lambda _event: self._set_drop_active(True))
            self.drop_zone.bind("<Leave>", lambda _event: self._set_drop_active(False))
        else:
            self.drop_zone.create_text(20, 32, text="Arrastrar no esta disponible", anchor="w", fill=self.colors["primary"], font=("Segoe UI", 13, "bold"))

        table_frame = tk.Frame(left_panel, bg=self.colors["surface"])
        table_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("name", "format", "dimensions", "weight", "details", "path")
        self.file_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "name": "Archivo",
            "format": "Tipo",
            "dimensions": "Tamano",
            "weight": "Peso",
            "details": "Detalle",
            "path": "Ruta",
        }
        widths = {"name": 230, "format": 78, "dimensions": 110, "weight": 86, "details": 170, "path": 280}
        for column, heading in headings.items():
            self.file_tree.heading(column, text=heading)
            self.file_tree.column(column, width=widths[column], minwidth=70, anchor="center" if column != "path" else "w")
        self.file_tree.grid(row=0, column=0, sticky="nsew")
        self.file_tree.bind("<<TreeviewSelect>>", self.update_preview)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.file_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_tree.configure(yscrollcommand=scrollbar.set)

        right_panel = tk.Frame(content, bg=self.colors["bg"])
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        preview_frame = self._card(right_panel)
        preview_frame.grid(row=0, column=0, sticky="ew")
        preview_frame.columnconfigure(0, weight=1)
        tk.Label(preview_frame, text="Vista previa", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 10)
        )
        self.preview_canvas = tk.Canvas(preview_frame, height=240, bg=self.colors["surface_soft"], bd=0, highlightthickness=1, highlightbackground=self.colors["line"])
        self.preview_canvas.grid(row=1, column=0, sticky="ew", padx=16)
        tk.Label(
            preview_frame,
            textvariable=self.preview_info,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
            wraplength=390,
            justify="left",
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(10, 14))

        history_frame = self._card(right_panel)
        history_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(1, weight=1)
        tk.Label(history_frame, text="Historial", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 10)
        )
        self.history_list = tk.Listbox(
            history_frame,
            activestyle="none",
            height=7,
            bg=self.colors["surface_soft"],
            fg=self.colors["text"],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors["line"],
            font=("Segoe UI", 9),
        )
        self.history_list.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        history_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_list.yview)
        history_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 16), padx=(0, 16))
        self.history_list.configure(yscrollcommand=history_scroll.set)

        options = self._card(self)
        options.grid(row=3, column=0, sticky="ew", padx=18, pady=(10, 10))
        for column in range(10):
            options.columnconfigure(column, weight=1 if column in {3, 5, 9} else 0)

        tk.Label(options, text="Salida y optimizacion", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=10, sticky="w", padx=16, pady=(14, 10)
        )

        self._field_label(options, "Preset").grid(row=1, column=0, sticky="w", padx=(16, 8), pady=(0, 10))
        self.preset_combo = ttk.Combobox(
            options,
            values=["Personalizado", "Para web", "Maxima calidad", "Reducir peso", "Icono .ico", "PDF desde imagenes"],
            state="readonly",
            width=18,
        )
        self.preset_combo.set("Personalizado")
        self.preset_combo.grid(row=1, column=1, sticky="ew", padx=(0, 14), pady=(0, 10))
        self.preset_combo.bind("<<ComboboxSelected>>", self.apply_preset)

        self._field_label(options, "Formato").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(0, 10))
        format_combo = ttk.Combobox(
            options,
            textvariable=self.output_format,
            values=list(OUTPUT_FORMATS.keys()),
            state="readonly",
            width=10,
        )
        format_combo.grid(row=1, column=3, sticky="ew", padx=(0, 14), pady=(0, 10))
        format_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_quality_state())

        self._field_label(options, "Calidad").grid(row=1, column=4, sticky="w", padx=(0, 8), pady=(0, 10))
        self.quality_scale = ttk.Scale(options, from_=1, to=100, variable=self.quality, orient="horizontal")
        self.quality_scale.grid(row=1, column=5, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.quality_label = tk.Label(options, textvariable=self.quality, width=4, bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 10))
        self.quality_label.grid(row=1, column=6, sticky="w", pady=(0, 10))

        self._check(options, "PDF unico", self.combine_pdf).grid(row=1, column=7, sticky="w", padx=(14, 0), pady=(0, 10))

        self._field_label(options, "Carpeta de salida").grid(row=2, column=0, sticky="w", padx=(16, 8), pady=(0, 10))
        output_entry = ttk.Entry(options, textvariable=self.output_dir)
        output_entry.grid(row=2, column=1, columnspan=6, sticky="ew", padx=(0, 10), pady=(0, 10))
        self._button(options, "Examinar", self.choose_output_dir, "ghost").grid(row=2, column=7, sticky="ew", padx=(0, 8), pady=(0, 10))
        self._button(options, "Abrir", self.open_output_dir, "ghost").grid(row=2, column=8, sticky="ew", pady=(0, 10))

        self._check(options, "Redimensionar", self.resize_enabled).grid(row=3, column=0, sticky="w", padx=(16, 8), pady=(0, 10))
        self._field_label(options, "Ancho").grid(row=3, column=1, sticky="e", padx=(0, 8), pady=(0, 10))
        ttk.Entry(options, textvariable=self.resize_width, width=8).grid(row=3, column=2, sticky="ew", padx=(0, 12), pady=(0, 10))
        self._field_label(options, "Alto").grid(row=3, column=3, sticky="e", padx=(0, 8), pady=(0, 10))
        ttk.Entry(options, textvariable=self.resize_height, width=8).grid(row=3, column=4, sticky="ew", padx=(0, 12), pady=(0, 10))
        self._check(options, "Mantener proporcion", self.keep_aspect).grid(row=3, column=5, sticky="w", padx=(0, 12), pady=(0, 10))
        self._button(options, "Fondo", self.choose_background, "ghost").grid(row=3, column=6, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.color_swatch = tk.Label(
            options,
            textvariable=self.background_hex,
            bg=self.background_hex.get(),
            fg=self.colors["text"],
            width=10,
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
        )
        self.color_swatch.grid(row=3, column=7, columnspan=2, sticky="ew", pady=(0, 10))

        self._field_label(options, "Nombre").grid(row=4, column=0, sticky="w", padx=(16, 8), pady=(0, 16))
        ttk.Combobox(
            options,
            textvariable=self.naming_mode,
            values=["Conservar", "Numerado", "Prefijo/sufijo"],
            state="readonly",
            width=15,
        ).grid(row=4, column=1, sticky="ew", padx=(0, 12), pady=(0, 16))
        self._field_label(options, "Prefijo").grid(row=4, column=2, sticky="e", padx=(0, 8), pady=(0, 16))
        ttk.Entry(options, textvariable=self.prefix, width=12).grid(row=4, column=3, sticky="ew", padx=(0, 12), pady=(0, 16))
        self._field_label(options, "Sufijo").grid(row=4, column=4, sticky="e", padx=(0, 8), pady=(0, 16))
        ttk.Entry(options, textvariable=self.suffix, width=12).grid(row=4, column=5, sticky="ew", padx=(0, 12), pady=(0, 16))
        self._check(options, "Sobrescribir", self.overwrite).grid(row=4, column=6, sticky="w", pady=(0, 16))

        footer = tk.Frame(self, bg=self.colors["bg"])
        footer.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 16))
        footer.columnconfigure(0, weight=1)
        tk.Label(footer, textvariable=self.status, bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(footer, variable=self.progress, maximum=100, style="Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=(14, 12), ipady=3)
        footer.columnconfigure(1, weight=1)
        self.convert_button = self._button(footer, "Convertir", self.start_conversion, "primary")
        self.convert_button.grid(row=0, column=2, sticky="e")

    def _card(self, parent) -> tk.Frame:
        return tk.Frame(parent, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["line"])

    def _field_label(self, parent, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=self.colors["surface"], fg=self.colors["muted"], font=("Segoe UI", 9, "bold"))

    def _check(self, parent, text: str, variable: tk.BooleanVar) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            activebackground=self.colors["surface"],
            activeforeground=self.colors["text"],
            selectcolor=self.colors["surface"],
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=0,
        )

    def _button(self, parent, text: str, command, variant: str = "secondary") -> tk.Button:
        palette = {
            "primary": (self.colors["primary"], "#ffffff", self.colors["primary_dark"]),
            "secondary": (self.colors["surface_soft"], self.colors["text"], "#e2e8f0"),
            "ghost": ("#f1f5f9", self.colors["text"], "#e2e8f0"),
        }
        bg, fg, active = palette[variant]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

    def _stat(self, parent, number: str, title: str, detail: str) -> tk.Frame:
        frame = self._card(parent)
        frame.columnconfigure(1, weight=1)
        badge = tk.Label(frame, text=number, bg=self.colors["primary"], fg="#ffffff", font=("Segoe UI", 11, "bold"), width=3)
        badge.grid(row=0, column=0, rowspan=2, padx=14, pady=12)
        tk.Label(frame, text=title, bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 11, "bold")).grid(
            row=0, column=1, sticky="sw", pady=(12, 0)
        )
        tk.Label(frame, text=detail, bg=self.colors["surface"], fg=self.colors["muted"], font=("Segoe UI", 9)).grid(
            row=1, column=1, sticky="nw", pady=(0, 12)
        )
        return frame

    def _draw_drop_zone(self, _event=None) -> None:
        if not hasattr(self, "drop_zone"):
            return
        self.drop_zone.delete("all")
        width = max(self.drop_zone.winfo_width(), 300)
        height = max(self.drop_zone.winfo_height(), 90)
        self.drop_zone.create_rectangle(10, 10, width - 10, height - 10, outline="#93c5fd", width=2, dash=(8, 6))
        self.drop_zone.create_text(
            width // 2,
            height // 2 - 10,
            text="Arrastra imagenes o carpetas aqui",
            fill=self.colors["primary"],
            font=("Segoe UI", 13, "bold"),
        )
        self.drop_zone.create_text(
            width // 2,
            height // 2 + 16,
            text="Tambien puedes usar los botones superiores",
            fill=self.colors["muted"],
            font=("Segoe UI", 9),
        )

    def _set_drop_active(self, active: bool) -> None:
        self.drop_zone.configure(bg=self.colors["drop_active"] if active else self.colors["drop"])
        self._draw_drop_zone()

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Selecciona imagenes", filetypes=INPUT_FILE_TYPES)
        self._add_paths(Path(path) for path in paths)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona una carpeta con imagenes")
        if folder:
            self._add_paths(self._iter_images(Path(folder)))

    def handle_drop(self, event) -> None:
        paths = [Path(path) for path in self.tk.splitlist(event.data)]
        expanded_paths: list[Path] = []
        for path in paths:
            if path.is_dir():
                expanded_paths.extend(self._iter_images(path))
            else:
                expanded_paths.append(path)
        self._add_paths(expanded_paths)

    def _iter_images(self, folder: Path):
        yield from (path for path in folder.rglob("*") if path.is_file() and is_supported_image(path))

    def _add_paths(self, paths) -> None:
        existing = {path.resolve() for path in self.files}
        added = 0
        rejected = 0

        for path in paths:
            resolved = path.resolve()
            if not resolved.is_file() or not is_supported_image(resolved):
                rejected += 1
                continue
            if resolved in existing:
                continue

            metadata = self.metadata_cache.get(resolved)
            if metadata is None:
                metadata = describe_image(resolved)
                self.metadata_cache[resolved] = metadata
            image_format, dimensions, details, weight = metadata
            self.files.append(resolved)
            existing.add(resolved)
            self.file_tree.insert(
                "",
                tk.END,
                iid=str(resolved),
                values=(resolved.name, image_format, dimensions, weight, details, str(resolved.parent)),
            )
            added += 1

        self.status.set(f"{len(self.files)} imagen(es) listas. Agregadas: {added}. Rechazadas: {rejected}.")
        if added and not self.file_tree.selection():
            first = str(self.files[0])
            self.file_tree.selection_set(first)
            self.file_tree.focus(first)
            self.update_preview()

    def remove_selected(self) -> None:
        selected = list(self.file_tree.selection())
        selected_paths = {Path(item) for item in selected}
        for item in selected:
            self.file_tree.delete(item)
        self.files = [path for path in self.files if path not in selected_paths]
        self.preview_canvas.delete("all")
        self.preview_info.set("Selecciona una imagen para ver la vista previa.")
        self.status.set(f"{len(self.files)} imagen(es) listas.")

    def clear_files(self) -> None:
        self.files.clear()
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        self.preview_canvas.delete("all")
        self.preview_info.set("Selecciona una imagen para ver la vista previa.")
        self.status.set("Lista limpia.")

    def update_preview(self, _event=None) -> None:
        selected = self.file_tree.selection()
        if not selected:
            return
        path = Path(selected[0])
        self.preview_canvas.delete("all")
        try:
            with Image.open(path) as image:
                image.thumbnail((410, 240), Image.Resampling.LANCZOS)
                preview = image.convert("RGBA")
                self.preview_image = ImageTk.PhotoImage(preview)
                width = self.preview_canvas.winfo_width() or 360
                self.preview_canvas.create_image(width // 2, 120, image=self.preview_image, anchor="center")
            metadata = self.metadata_cache.get(path)
            if metadata is None:
                metadata = describe_image(path)
                self.metadata_cache[path] = metadata
            image_format, dimensions, details, weight = metadata
            self.preview_info.set(f"{path.name} | {image_format} | {dimensions} | {weight} | {details}")
        except Exception as exc:
            self.preview_info.set(f"No se pudo previsualizar: {exc}")

    def choose_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona carpeta de salida")
        if folder:
            self.output_dir.set(folder)

    def open_output_dir(self) -> None:
        output_dir = Path(self.output_dir.get()).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(output_dir)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudo abrir la carpeta:\n{exc}")

    def choose_background(self) -> None:
        color = colorchooser.askcolor(color=self.background_hex.get(), title="Color de fondo para formatos sin transparencia")
        if color and color[1]:
            self.background_hex.set(color[1])
            self.color_swatch.configure(bg=color[1])

    def apply_preset(self, _event=None) -> None:
        preset = self.preset_combo.get()
        if preset == "Para web":
            self.output_format.set("WEBP")
            self.quality.set(82)
            self.resize_enabled.set(True)
            self.resize_width.set("1600")
            self.resize_height.set("")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
        elif preset == "Maxima calidad":
            self.output_format.set("PNG")
            self.quality.set(100)
            self.resize_enabled.set(False)
            self.combine_pdf.set(False)
        elif preset == "Reducir peso":
            self.output_format.set("WEBP")
            self.quality.set(65)
            self.resize_enabled.set(True)
            self.resize_width.set("1200")
            self.resize_height.set("")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
        elif preset == "Icono .ico":
            self.output_format.set("ICO")
            self.resize_enabled.set(True)
            self.resize_width.set("256")
            self.resize_height.set("256")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
        elif preset == "PDF desde imagenes":
            self.output_format.set("PDF")
            self.combine_pdf.set(True)
            self.resize_enabled.set(False)
            self.background_hex.set("#ffffff")
            self.color_swatch.configure(bg="#ffffff")
        self._refresh_quality_state()

    def _refresh_quality_state(self) -> None:
        enabled = OUTPUT_FORMATS[self.output_format.get()]["quality"]
        state = tk.NORMAL if enabled else tk.DISABLED
        self.quality_scale.configure(state=state)
        self.quality_label.configure(foreground="#202938" if enabled else "#98a2b3")

    def _read_options(self) -> ConversionOptions | None:
        try:
            background = ImageColor.getrgb(self.background_hex.get())
            width = int(self.resize_width.get()) if self.resize_width.get().strip() else None
            height = int(self.resize_height.get()) if self.resize_height.get().strip() else None
            if width is not None and width <= 0 or height is not None and height <= 0:
                raise ValueError("El ancho y alto deben ser mayores a cero.")
        except ValueError as exc:
            messagebox.showerror(APP_NAME, f"Opcion invalida:\n{exc}")
            return None

        return ConversionOptions(
            output_format=self.output_format.get(),
            quality=int(self.quality.get()),
            output_dir=Path(self.output_dir.get()).expanduser(),
            resize_enabled=self.resize_enabled.get(),
            width=width,
            height=height,
            keep_aspect=self.keep_aspect.get(),
            background=background,
            naming_mode=self.naming_mode.get(),
            prefix=self.prefix.get(),
            suffix=self.suffix.get(),
            overwrite=self.overwrite.get(),
            combine_pdf=self.combine_pdf.get(),
        )

    def start_conversion(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_NAME, "Agrega al menos una imagen.")
            return

        options = self._read_options()
        if options is None:
            return

        try:
            options.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudo crear la carpeta de salida:\n{exc}")
            return

        files = list(self.files)
        self.convert_button.configure(state=tk.DISABLED)
        self.progress.set(0)
        thread = threading.Thread(target=self._convert_worker, args=(files, options), daemon=True)
        thread.start()

    def _convert_worker(self, files: list[Path], options: ConversionOptions) -> None:
        converted = 0
        errors: list[str] = []
        outputs: list[Path] = []

        try:
            if options.combine_pdf and options.output_format == "PDF":
                destination = options.output_dir / "imagenes_convertidas.pdf"
                if not options.overwrite:
                    counter = 1
                    while destination.exists():
                        destination = options.output_dir / f"imagenes_convertidas_{counter}.pdf"
                        counter += 1
                self._set_status("Creando PDF unico...")
                combine_images_to_pdf(files, destination, options)
                outputs.append(destination)
                converted = len(files)
                self._set_progress(100)
            else:
                total = len(files)
                for index, source in enumerate(files, start=1):
                    self._set_status(f"Convirtiendo {index}/{total}: {source.name}")
                    try:
                        destination = build_output_path(source, options.output_dir, options, index)
                        convert_image(source, destination, options)
                        outputs.append(destination)
                        converted += 1
                    except (OSError, UnidentifiedImageError, ValueError) as exc:
                        errors.append(f"{source.name}: {exc}")
                    self._set_progress(index / total * 100)
        finally:
            self.after(0, lambda: self.convert_button.configure(state=tk.NORMAL))

        self.after(0, lambda: self._finish_conversion(converted, errors, outputs))

    def _finish_conversion(self, converted: int, errors: list[str], outputs: list[Path]) -> None:
        for output in outputs:
            self.history_list.insert(tk.END, f"OK  {output.name} -> {output.parent}")
        for error in errors[:25]:
            self.history_list.insert(tk.END, f"ERR {error}")
        self.history_list.yview_moveto(1)

        if errors:
            self.status.set(f"Convertidas: {converted}. Errores: {len(errors)}.")
            messagebox.showwarning(APP_NAME, "Algunas imagenes no se pudieron convertir:\n\n" + "\n".join(errors[:10]))
        else:
            self.status.set(f"Listo. Convertidas: {converted}.")
            messagebox.showinfo(APP_NAME, f"Conversion terminada.\nImagenes convertidas: {converted}")

    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self.status.set(text))

    def _set_progress(self, value: float) -> None:
        self.after(0, lambda: self.progress.set(value))


if __name__ == "__main__":
    app = ImageConverterApp()
    app.mainloop()
