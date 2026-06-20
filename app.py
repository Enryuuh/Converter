from __future__ import annotations

import concurrent.futures
import io
import json
import os
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageColor, ImageOps, ImageSequence, ImageTk, UnidentifiedImageError

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
APP_VERSION = "1.2.0"
GITHUB_REPO = "Enryuuh/Converter"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
LATEST_RELEASE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
LOGO_PNG = BASE_DIR / "assets" / "converter-logo.png"
LOGO_ICO = BASE_DIR / "assets" / "converter-logo.ico"
CONFIG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "Converter"
PROFILES_PATH = CONFIG_DIR / "profiles.json"

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
    target_size_enabled: bool
    target_size_kb: int | None
    max_workers: int


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS


def parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.strip().lstrip("v").split("."):
        digits = "".join(char for char in part if char.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


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


def build_output_path(source: Path, output_dir: Path, options: ConversionOptions, index: int, reserved: set[Path] | None = None) -> Path:
    suffix = OUTPUT_FORMATS[options.output_format]["ext"]
    stem = source.stem
    if options.naming_mode == "Numerado":
        stem = f"{index:03d}_{stem}"
    elif options.naming_mode == "Prefijo/sufijo":
        stem = f"{safe_name_part(options.prefix)}{stem}{safe_name_part(options.suffix)}"

    candidate = output_dir / f"{stem}{suffix}"
    counter = 1
    if options.overwrite:
        if reserved is not None:
            while candidate in reserved:
                candidate = output_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            reserved.add(candidate)
        return candidate

    while candidate.exists() or (reserved is not None and candidate in reserved):
        candidate = output_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    if reserved is not None:
        reserved.add(candidate)
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


def build_save_kwargs(options: ConversionOptions, quality_override: int | None = None) -> dict:
    save_kwargs = {}
    if OUTPUT_FORMATS[options.output_format]["quality"]:
        save_kwargs["quality"] = quality_override if quality_override is not None else options.quality
        save_kwargs["optimize"] = True
    if options.output_format == "PNG":
        save_kwargs["optimize"] = True
    if options.output_format == "TIFF":
        save_kwargs["compression"] = "tiff_deflate"
    return save_kwargs


def prepared_frames_from_source(source: Path, options: ConversionOptions) -> tuple[list[Image.Image], bool, dict]:
    with Image.open(source) as image:
        preserve_frames = getattr(image, "is_animated", False) and options.output_format in {"GIF", "WEBP", "TIFF", "PDF"}
        source_info = {
            "duration": image.info.get("duration", 100),
            "loop": image.info.get("loop", 0),
        }
        if preserve_frames:
            frames = [prepare_frame(frame, options) for frame in ImageSequence.Iterator(image)]
        else:
            oriented = ImageOps.exif_transpose(image)
            frames = [prepare_frame(oriented, options)]
    return frames, preserve_frames, source_info


def save_prepared_frames(
    frames: list[Image.Image],
    destination: Path | io.BytesIO,
    options: ConversionOptions,
    preserve_frames: bool,
    source_info: dict,
    quality_override: int | None = None,
) -> Path | io.BytesIO:
    save_format = OUTPUT_FORMATS[options.output_format]["save_format"]
    save_kwargs = build_save_kwargs(options, quality_override)
    first = frames[0]

    if preserve_frames and len(frames) > 1:
        save_kwargs["save_all"] = True
        save_kwargs["append_images"] = frames[1:]
        if options.output_format in {"GIF", "WEBP"}:
            save_kwargs["duration"] = source_info.get("duration", 100)
            save_kwargs["loop"] = source_info.get("loop", 0)

    first.save(destination, save_format, **save_kwargs)
    return destination


def converted_first_frame(source: Path, options: ConversionOptions) -> Image.Image:
    with Image.open(source) as image:
        return prepare_frame(ImageOps.exif_transpose(image), options)


def estimate_output_size(source: Path, options: ConversionOptions) -> int:
    frames, preserve_frames, source_info = prepared_frames_from_source(source, options)
    buffer = io.BytesIO()
    save_prepared_frames(frames, buffer, options, preserve_frames, source_info)
    return len(buffer.getvalue())


def convert_image(source: Path, destination: Path, options: ConversionOptions, quality_override: int | None = None) -> Path:
    frames, preserve_frames, source_info = prepared_frames_from_source(source, options)
    save_prepared_frames(frames, destination, options, preserve_frames, source_info, quality_override)
    return destination


def convert_image_optimized(source: Path, destination: Path, options: ConversionOptions) -> Path:
    if not options.target_size_enabled or not options.target_size_kb or not OUTPUT_FORMATS[options.output_format]["quality"]:
        convert_image(source, destination, options)
        return destination

    frames, preserve_frames, source_info = prepared_frames_from_source(source, options)
    save_prepared_frames(frames, destination, options, preserve_frames, source_info)
    target_bytes = options.target_size_kb * 1024
    if destination.stat().st_size <= target_bytes:
        return destination

    low = 15
    high = min(options.quality, 95)
    best_bytes: bytes | None = None
    best_quality = low

    while low <= high:
        quality = (low + high) // 2
        buffer = io.BytesIO()
        save_prepared_frames(frames, buffer, replace(options, quality=quality), preserve_frames, source_info, quality)
        payload = buffer.getvalue()
        if len(payload) <= target_bytes:
            best_bytes = payload
            best_quality = quality
            low = quality + 1
        else:
            high = quality - 1

    if best_bytes is None:
        buffer = io.BytesIO()
        save_prepared_frames(frames, buffer, replace(options, quality=best_quality), preserve_frames, source_info, best_quality)
        best_bytes = buffer.getvalue()

    destination.write_bytes(best_bytes)
    return destination


def combine_images_to_pdf(files: list[Path], destination: Path, options: ConversionOptions) -> Path:
    pages: list[Image.Image] = []
    for source in files:
        with Image.open(source) as image:
            first_frame = ImageOps.exif_transpose(next(ImageSequence.Iterator(image)))
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
        self.preview_images: list[ImageTk.PhotoImage] = []
        self.cancel_event = threading.Event()
        self.profiles: dict[str, dict] = self._load_profiles()
        self.history_entries: list[str] = []
        self.conversion_running = False

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
        self.target_size_enabled = tk.BooleanVar(value=False)
        self.target_size_kb = tk.StringVar(value="")
        self.max_workers = tk.IntVar(value=min(4, max(1, os.cpu_count() or 1)))
        self.profile_name = tk.StringVar(value="")
        self.dark_mode = tk.BooleanVar(value=False)
        self.progress = tk.DoubleVar(value=0)

        self._build_ui()
        self._refresh_quality_state()

    def _theme_colors(self) -> dict[str, str]:
        if self.dark_mode.get():
            return {
                "bg": "#0b1120",
                "surface": "#111827",
                "surface_soft": "#1f2937",
                "line": "#334155",
                "text": "#e5e7eb",
                "muted": "#94a3b8",
                "primary": "#60a5fa",
                "primary_dark": "#3b82f6",
                "success": "#2dd4bf",
                "warning": "#fbbf24",
                "drop": "#172554",
                "drop_active": "#1e3a8a",
                "tree_heading": "#1f2937",
                "tree_selected": "#1d4ed8",
                "badge_bg": "#1e40af",
                "badge_fg": "#dbeafe",
                "ghost": "#1f2937",
                "ghost_active": "#334155",
                "input": "#0f172a",
            }
        return {
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
            "tree_heading": "#edf2f7",
            "tree_selected": "#dbeafe",
            "badge_bg": "#dbeafe",
            "badge_fg": "#2563eb",
            "ghost": "#f1f5f9",
            "ghost_active": "#e2e8f0",
            "input": "#ffffff",
        }

    def _build_ui(self) -> None:
        self.colors = self._theme_colors()
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
        control_bg = self.colors["input"]
        control_disabled_bg = self.colors["surface_soft"]
        control_fg = self.colors["text"]
        control_disabled_fg = self.colors["muted"]
        style.configure(
            "TCombobox",
            padding=6,
            arrowsize=14,
            fieldbackground=control_bg,
            background=control_bg,
            foreground=control_fg,
            arrowcolor=control_fg,
            bordercolor=self.colors["line"],
            lightcolor=self.colors["line"],
            darkcolor=self.colors["line"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", control_bg), ("disabled", control_disabled_bg), ("!disabled", control_bg)],
            foreground=[("disabled", control_disabled_fg), ("readonly", control_fg), ("!disabled", control_fg)],
            background=[("active", self.colors["ghost_active"]), ("disabled", control_disabled_bg), ("readonly", control_bg), ("!disabled", control_bg)],
            arrowcolor=[("disabled", control_disabled_fg), ("active", control_fg), ("!disabled", control_fg)],
            selectbackground=[("readonly", control_bg), ("!disabled", self.colors["tree_selected"])],
            selectforeground=[("readonly", control_fg), ("!disabled", control_fg)],
        )
        style.configure(
            "TEntry",
            padding=6,
            fieldbackground=control_bg,
            foreground=control_fg,
            insertcolor=control_fg,
            bordercolor=self.colors["line"],
            lightcolor=self.colors["line"],
            darkcolor=self.colors["line"],
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", control_disabled_bg), ("readonly", control_bg), ("!disabled", control_bg)],
            foreground=[("disabled", control_disabled_fg), ("readonly", control_fg), ("!disabled", control_fg)],
            selectbackground=[("!disabled", self.colors["tree_selected"])],
            selectforeground=[("!disabled", control_fg)],
        )
        style.configure("Treeview", rowheight=34, background=self.colors["surface"], fieldbackground=self.colors["surface"], borderwidth=0)
        style.configure(
            "Treeview.Heading",
            padding=(8, 4),
            background=self.colors["tree_heading"],
            foreground=self.colors["text"],
            bordercolor=self.colors["line"],
            relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Treeview", background=[("selected", self.colors["tree_selected"])], foreground=[("selected", self.colors["text"])])
        style.map(
            "Treeview.Heading",
            background=[("active", self.colors["ghost_active"]), ("!active", self.colors["tree_heading"])],
            foreground=[("active", self.colors["text"]), ("!active", self.colors["text"])],
        )
        style.configure("Horizontal.TProgressbar", troughcolor=self.colors["line"], background=self.colors["primary"], bordercolor=self.colors["line"])
        style.configure(
            "Horizontal.TScale",
            background=self.colors["surface"],
            troughcolor=self.colors["line"],
            bordercolor=self.colors["line"],
            lightcolor=self.colors["line"],
            darkcolor=self.colors["line"],
        )
        style.map("Horizontal.TScale", background=[("active", self.colors["surface"])])
        self.option_add("*TCombobox*Listbox.background", control_bg)
        self.option_add("*TCombobox*Listbox.foreground", control_fg)
        self.option_add("*TCombobox*Listbox.selectBackground", self.colors["tree_selected"])
        self.option_add("*TCombobox*Listbox.selectForeground", control_fg)

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
        brand = tk.Frame(header, bg=self.colors["surface"])
        brand.grid(row=0, column=1, sticky="sw", pady=(14, 0))
        tk.Label(brand, text="Converter", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 24, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            brand,
            text=f"v{APP_VERSION}",
            bg=self.colors["badge_bg"],
            fg=self.colors["badge_fg"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=3,
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))
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
        self._button(actions, "Abrir salida", self.open_output_dir).grid(row=0, column=2, padx=(0, 8))
        self._button(actions, "Actualizar", self.check_for_updates, "ghost").grid(row=0, column=3, padx=(0, 8))
        self._button(actions, "Nocturno" if not self.dark_mode.get() else "Claro", self.toggle_theme, "ghost").grid(row=0, column=4)

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
        widths = {"name": 210, "format": 74, "dimensions": 96, "weight": 78, "details": 150, "path": 178}
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
        preview_head = tk.Frame(preview_frame, bg=self.colors["surface"])
        preview_head.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 10))
        preview_head.columnconfigure(0, weight=1)
        tk.Label(preview_head, text="Vista previa", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self._button(preview_head, "Comparar salida", self.preview_output, "ghost").grid(row=0, column=1, sticky="e")
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
            fg=self._text_color_for_background(self.background_hex.get()),
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

        self._field_label(options, "Perfil").grid(row=5, column=0, sticky="w", padx=(16, 8), pady=(0, 16))
        self.profile_combo = ttk.Combobox(
            options,
            textvariable=self.profile_name,
            values=sorted(self.profiles.keys()),
            state="readonly",
            width=18,
        )
        self.profile_combo.grid(row=5, column=1, sticky="ew", padx=(0, 8), pady=(0, 16))
        self._button(options, "Cargar", self.load_selected_profile, "ghost").grid(row=5, column=2, sticky="ew", padx=(0, 8), pady=(0, 16))
        self._button(options, "Guardar", self.save_current_profile, "ghost").grid(row=5, column=3, sticky="ew", padx=(0, 12), pady=(0, 16))
        self._check(options, "Objetivo KB", self.target_size_enabled).grid(row=5, column=4, sticky="w", padx=(0, 8), pady=(0, 16))
        ttk.Entry(options, textvariable=self.target_size_kb, width=9).grid(row=5, column=5, sticky="ew", padx=(0, 12), pady=(0, 16))
        self._field_label(options, "Procesos").grid(row=5, column=6, sticky="e", padx=(0, 8), pady=(0, 16))
        tk.Spinbox(
            options,
            from_=1,
            to=max(1, min(16, os.cpu_count() or 1)),
            textvariable=self.max_workers,
            width=5,
            bg=self.colors["input"],
            fg=self.colors["text"],
            disabledbackground=self.colors["surface_soft"],
            disabledforeground=self.colors["muted"],
            insertbackground=self.colors["text"],
            buttonbackground=self.colors["ghost"],
            highlightbackground=self.colors["line"],
            highlightcolor=self.colors["primary"],
            highlightthickness=1,
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
        ).grid(row=5, column=7, sticky="w", pady=(0, 16))

        footer = tk.Frame(self, bg=self.colors["bg"])
        footer.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 16))
        footer.columnconfigure(0, weight=1)
        tk.Label(footer, textvariable=self.status, bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(footer, variable=self.progress, maximum=100, style="Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=(14, 12), ipady=3)
        footer.columnconfigure(1, weight=1)
        self.convert_button = self._button(footer, "Convertir", self.start_conversion, "primary")
        self.convert_button.grid(row=0, column=2, sticky="e")
        self.cancel_button = self._button(footer, "Cancelar", self.cancel_conversion, "ghost")
        self.cancel_button.grid(row=0, column=3, sticky="e", padx=(8, 0))
        self.cancel_button.configure(state=tk.DISABLED)

    def _card(self, parent) -> tk.Frame:
        return tk.Frame(parent, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["line"])

    def _field_label(self, parent, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=self.colors["surface"], fg=self.colors["muted"], font=("Segoe UI", 9, "bold"))

    def _text_color_for_background(self, color: str) -> str:
        try:
            red, green, blue = ImageColor.getrgb(color)[:3]
        except ValueError:
            return self.colors["text"]
        luminance = (red * 299 + green * 587 + blue * 114) / 1000
        return "#0f172a" if luminance >= 150 else "#f8fafc"

    def _refresh_color_swatch(self) -> None:
        if hasattr(self, "color_swatch"):
            color = self.background_hex.get()
            self.color_swatch.configure(bg=color, fg=self._text_color_for_background(color))

    def _check(self, parent, text: str, variable: tk.BooleanVar) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            activebackground=self.colors["surface"],
            activeforeground=self.colors["text"],
            selectcolor=self.colors["input"],
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=0,
        )

    def _button(self, parent, text: str, command, variant: str = "secondary") -> tk.Button:
        palette = {
            "primary": (self.colors["primary"], "#ffffff", self.colors["primary_dark"]),
            "secondary": (self.colors["surface_soft"], self.colors["text"], self.colors["ghost_active"]),
            "ghost": (self.colors["ghost"], self.colors["text"], self.colors["ghost_active"]),
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

    def toggle_theme(self) -> None:
        if self.conversion_running:
            messagebox.showinfo(APP_NAME, "Espera a que termine la conversion o cancelala antes de cambiar el tema.")
            return
        selected = []
        if hasattr(self, "file_tree"):
            selected = [Path(item) for item in self.file_tree.selection()]
        self.dark_mode.set(not self.dark_mode.get())
        for child in self.winfo_children():
            child.destroy()
        self.logo_image = None
        self.preview_image = None
        self.preview_images = []
        self._build_ui()
        self._refresh_quality_state()
        self._restore_file_tree(selected)
        self._restore_history()
        self.status.set("Modo nocturno activo." if self.dark_mode.get() else "Modo claro activo.")

    def _restore_file_tree(self, selected: list[Path] | None = None) -> None:
        selected = selected or []
        for resolved in self.files:
            metadata = self.metadata_cache.get(resolved)
            if metadata is None:
                metadata = describe_image(resolved)
                self.metadata_cache[resolved] = metadata
            image_format, dimensions, details, weight = metadata
            self.file_tree.insert(
                "",
                tk.END,
                iid=str(resolved),
                values=(resolved.name, image_format, dimensions, weight, details, str(resolved.parent)),
            )
        valid_selection = [str(path) for path in selected if path in self.files]
        if valid_selection:
            self.file_tree.selection_set(valid_selection)
            self.file_tree.focus(valid_selection[0])
            self.update_preview()
        elif self.files:
            first = str(self.files[0])
            self.file_tree.selection_set(first)
            self.file_tree.focus(first)
            self.update_preview()

    def _restore_history(self) -> None:
        for entry in self.history_entries:
            self.history_list.insert(tk.END, entry)
        self.history_list.yview_moveto(1)

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Selecciona imagenes", filetypes=INPUT_FILE_TYPES)
        self._add_paths(Path(path) for path in paths)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona una carpeta con imagenes")
        if folder:
            self._add_drop_paths([Path(folder)])

    def handle_drop(self, event) -> None:
        paths = [Path(path) for path in self.tk.splitlist(event.data)]
        self._add_drop_paths(paths)

    def _iter_images(self, folder: Path):
        yield from (path for path in folder.rglob("*") if path.is_file() and is_supported_image(path))

    def _add_drop_paths(self, paths: list[Path]) -> None:
        self.status.set("Escaneando archivos...")
        thread = threading.Thread(target=self._expand_and_add_paths_worker, args=(paths,), daemon=True)
        thread.start()

    def _expand_and_add_paths_worker(self, paths: list[Path]) -> None:
        expanded_paths: list[Path] = []
        for path in paths:
            if path.is_dir():
                expanded_paths.extend(self._iter_images(path))
            else:
                expanded_paths.append(path)
        self._scan_paths(expanded_paths)

    def _add_paths(self, paths) -> None:
        self.status.set("Leyendo metadatos...")
        thread = threading.Thread(target=self._scan_paths, args=(list(paths),), daemon=True)
        thread.start()

    def _scan_paths(self, paths: list[Path]) -> None:
        existing = {path.resolve() for path in self.files}
        entries: list[tuple[Path, tuple[str, str, str, str]]] = []
        added = 0
        rejected = 0

        for path in paths:
            try:
                resolved = path.resolve()
            except OSError:
                rejected += 1
                continue
            if not resolved.is_file() or not is_supported_image(resolved):
                rejected += 1
                continue
            if resolved in existing:
                continue

            metadata = self.metadata_cache.get(resolved)
            if metadata is None:
                metadata = describe_image(resolved)
                self.metadata_cache[resolved] = metadata
            existing.add(resolved)
            entries.append((resolved, metadata))
            added += 1

        self.after(0, lambda: self._insert_scanned_paths(entries, added, rejected))

    def _insert_scanned_paths(self, entries: list[tuple[Path, tuple[str, str, str, str]]], added: int, rejected: int) -> None:
        existing = set(self.files)
        for resolved, metadata in entries:
            if resolved in existing:
                continue
            image_format, dimensions, details, weight = metadata
            self.files.append(resolved)
            existing.add(resolved)
            self.file_tree.insert(
                "",
                tk.END,
                iid=str(resolved),
                values=(resolved.name, image_format, dimensions, weight, details, str(resolved.parent)),
            )

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
                image.draft("RGB", (410, 240))
                image = ImageOps.exif_transpose(image)
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
            self._refresh_color_swatch()

    def preview_output(self) -> None:
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showinfo(APP_NAME, "Selecciona una imagen para comparar.")
            return
        options = self._read_options()
        if options is None:
            return

        path = Path(selected[0])
        try:
            with Image.open(path) as image:
                image.draft("RGB", (190, 190))
                original = ImageOps.exif_transpose(image)
                original.thumbnail((190, 190), Image.Resampling.LANCZOS)
                original = original.convert("RGBA")
            output = converted_first_frame(path, options).convert("RGBA")
            output.thumbnail((190, 190), Image.Resampling.LANCZOS)

            original_photo = ImageTk.PhotoImage(original)
            output_photo = ImageTk.PhotoImage(output)
            self.preview_images = [original_photo, output_photo]

            self.preview_canvas.delete("all")
            width = self.preview_canvas.winfo_width() or 410
            left_x = width // 4
            right_x = width * 3 // 4
            self.preview_canvas.create_text(left_x, 18, text="Original", fill=self.colors["muted"], font=("Segoe UI", 9, "bold"))
            self.preview_canvas.create_text(right_x, 18, text="Salida", fill=self.colors["primary"], font=("Segoe UI", 9, "bold"))
            self.preview_canvas.create_image(left_x, 122, image=original_photo, anchor="center")
            self.preview_canvas.create_image(right_x, 122, image=output_photo, anchor="center")

            original_size = path.stat().st_size
            estimated_size = estimate_output_size(path, options)
            self.preview_info.set(
                f"{path.name} | original {format_size(original_size)} | estimado {format_size(estimated_size)} | {options.output_format}"
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"No se pudo generar la comparacion:\n{exc}")

    def cancel_conversion(self) -> None:
        self.cancel_event.set()
        self.status.set("Cancelando conversion...")

    def _load_profiles(self) -> dict[str, dict]:
        try:
            if PROFILES_PATH.exists():
                return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _save_profiles(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        PROFILES_PATH.write_text(json.dumps(self.profiles, indent=2), encoding="utf-8")

    def _current_profile_data(self) -> dict:
        return {
            "output_format": self.output_format.get(),
            "quality": int(self.quality.get()),
            "resize_enabled": self.resize_enabled.get(),
            "resize_width": self.resize_width.get(),
            "resize_height": self.resize_height.get(),
            "keep_aspect": self.keep_aspect.get(),
            "background_hex": self.background_hex.get(),
            "naming_mode": self.naming_mode.get(),
            "prefix": self.prefix.get(),
            "suffix": self.suffix.get(),
            "overwrite": self.overwrite.get(),
            "combine_pdf": self.combine_pdf.get(),
            "target_size_enabled": self.target_size_enabled.get(),
            "target_size_kb": self.target_size_kb.get(),
            "max_workers": int(self.max_workers.get()),
            "dark_mode": self.dark_mode.get(),
        }

    def save_current_profile(self) -> None:
        name = simpledialog.askstring(APP_NAME, "Nombre del perfil:")
        if not name:
            return
        self.profiles[name.strip()] = self._current_profile_data()
        self._save_profiles()
        self.profile_combo.configure(values=sorted(self.profiles.keys()))
        self.profile_name.set(name.strip())
        self.status.set(f"Perfil guardado: {name.strip()}")

    def load_selected_profile(self) -> None:
        name = self.profile_name.get()
        data = self.profiles.get(name)
        if not data:
            messagebox.showinfo(APP_NAME, "Selecciona un perfil guardado.")
            return
        self.output_format.set(data.get("output_format", "WEBP"))
        self.quality.set(data.get("quality", 85))
        self.resize_enabled.set(data.get("resize_enabled", False))
        self.resize_width.set(data.get("resize_width", ""))
        self.resize_height.set(data.get("resize_height", ""))
        self.keep_aspect.set(data.get("keep_aspect", True))
        self.background_hex.set(data.get("background_hex", "#ffffff"))
        self._refresh_color_swatch()
        self.naming_mode.set(data.get("naming_mode", "Conservar"))
        self.prefix.set(data.get("prefix", ""))
        self.suffix.set(data.get("suffix", ""))
        self.overwrite.set(data.get("overwrite", False))
        self.combine_pdf.set(data.get("combine_pdf", False))
        self.target_size_enabled.set(data.get("target_size_enabled", False))
        self.target_size_kb.set(data.get("target_size_kb", ""))
        self.max_workers.set(data.get("max_workers", min(4, max(1, os.cpu_count() or 1))))
        requested_dark_mode = data.get("dark_mode", self.dark_mode.get())
        if requested_dark_mode != self.dark_mode.get():
            self.dark_mode.set(requested_dark_mode)
            for child in self.winfo_children():
                child.destroy()
            self._build_ui()
            self._restore_file_tree()
            self._restore_history()
        self._refresh_quality_state()
        self.status.set(f"Perfil cargado: {name}")

    def check_for_updates(self) -> None:
        self.status.set("Buscando actualizaciones...")
        thread = threading.Thread(target=self._check_for_updates_worker, daemon=True)
        thread.start()

    def _check_for_updates_worker(self) -> None:
        try:
            request = urllib.request.Request(LATEST_RELEASE_API, headers={"User-Agent": f"Converter/{APP_VERSION}"})
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            latest = str(payload.get("tag_name", "")).lstrip("v")
            html_url = payload.get("html_url", LATEST_RELEASE_URL)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            self.after(0, lambda: messagebox.showwarning(APP_NAME, f"No se pudo revisar actualizaciones:\n{exc}"))
            self._set_status("No se pudo revisar actualizaciones.")
            return

        def notify() -> None:
            if latest and parse_version(latest) > parse_version(APP_VERSION):
                if messagebox.askyesno(APP_NAME, f"Hay una nueva version: v{latest}.\n\n¿Abrir pagina de descarga?"):
                    webbrowser.open(html_url)
                self.status.set(f"Actualizacion disponible: v{latest}")
            else:
                messagebox.showinfo(APP_NAME, "Ya tienes la version mas reciente.")
                self.status.set("Version actualizada.")

        self.after(0, notify)

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
            self._refresh_color_swatch()
        self._refresh_quality_state()

    def _refresh_quality_state(self) -> None:
        enabled = OUTPUT_FORMATS[self.output_format.get()]["quality"]
        state = tk.NORMAL if enabled else tk.DISABLED
        self.quality_scale.configure(state=state)
        self.quality_label.configure(foreground=self.colors["text"] if enabled else self.colors["muted"])

    def _read_options(self) -> ConversionOptions | None:
        try:
            background = ImageColor.getrgb(self.background_hex.get())
            width = int(self.resize_width.get()) if self.resize_width.get().strip() else None
            height = int(self.resize_height.get()) if self.resize_height.get().strip() else None
            target_size = int(self.target_size_kb.get()) if self.target_size_kb.get().strip() else None
            max_workers = int(self.max_workers.get())
            if width is not None and width <= 0 or height is not None and height <= 0:
                raise ValueError("El ancho y alto deben ser mayores a cero.")
            if target_size is not None and target_size <= 0:
                raise ValueError("El peso objetivo debe ser mayor a cero.")
            if max_workers <= 0:
                raise ValueError("La cantidad de procesos debe ser mayor a cero.")
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
            target_size_enabled=self.target_size_enabled.get(),
            target_size_kb=target_size,
            max_workers=max(1, max_workers),
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
        self.cancel_event.clear()
        self.conversion_running = True
        self.convert_button.configure(state=tk.DISABLED)
        self.cancel_button.configure(state=tk.NORMAL)
        self.progress.set(0)
        thread = threading.Thread(target=self._convert_worker, args=(files, options), daemon=True)
        thread.start()

    def _convert_worker(self, files: list[Path], options: ConversionOptions) -> None:
        converted = 0
        errors: list[str] = []
        outputs: list[Path] = []
        cancelled = False

        try:
            if options.combine_pdf and options.output_format == "PDF":
                destination = options.output_dir / "imagenes_convertidas.pdf"
                if not options.overwrite:
                    counter = 1
                    while destination.exists():
                        destination = options.output_dir / f"imagenes_convertidas_{counter}.pdf"
                        counter += 1
                self._set_status("Creando PDF unico...")
                if self.cancel_event.is_set():
                    cancelled = True
                else:
                    combine_images_to_pdf(files, destination, options)
                    outputs.append(destination)
                    converted = len(files)
                self._set_progress(100)
            else:
                total = len(files)
                completed = 0
                reserved_outputs: set[Path] = set()
                job_iter = iter(enumerate(files, start=1))

                def convert_one(index: int, source: Path, destination: Path) -> tuple[bool, Path | None, str | None]:
                    if self.cancel_event.is_set():
                        return False, None, None
                    try:
                        convert_image_optimized(source, destination, options)
                        return True, destination, None
                    except (OSError, UnidentifiedImageError, ValueError) as exc:
                        return False, None, f"{source.name}: {exc}"

                max_workers = min(options.max_workers, total)
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map: dict[concurrent.futures.Future, tuple[int, Path]] = {}

                    def submit_next() -> bool:
                        try:
                            index, source = next(job_iter)
                        except StopIteration:
                            return False
                        destination = build_output_path(source, options.output_dir, options, index, reserved_outputs)
                        future_map[executor.submit(convert_one, index, source, destination)] = (index, source)
                        return True

                    for _ in range(max_workers):
                        submit_next()

                    while future_map:
                        done, _pending = concurrent.futures.wait(
                            future_map,
                            return_when=concurrent.futures.FIRST_COMPLETED,
                        )
                        future = done.pop()
                        index, source = future_map.pop(future)
                        if self.cancel_event.is_set():
                            cancelled = True
                        self._set_status(f"Procesando {min(completed + 1, total)}/{total}: {source.name}")
                        ok, output, error = future.result()
                        if ok and output is not None:
                            outputs.append(output)
                            converted += 1
                        if error:
                            errors.append(error)
                        completed += 1
                        self._set_progress(completed / total * 100)
                        if self.cancel_event.is_set():
                            for pending in future_map:
                                pending.cancel()
                            cancelled = True
                            break
                        submit_next()
        finally:
            self.after(0, lambda: self.convert_button.configure(state=tk.NORMAL))
            self.after(0, lambda: self.cancel_button.configure(state=tk.DISABLED))
            self.after(0, lambda: setattr(self, "conversion_running", False))

        self.after(0, lambda: self._finish_conversion(converted, errors, outputs, cancelled))

    def _finish_conversion(self, converted: int, errors: list[str], outputs: list[Path], cancelled: bool = False) -> None:
        for output in outputs:
            entry = f"OK  {output.name} -> {output.parent}"
            self.history_entries.append(entry)
            self.history_list.insert(tk.END, entry)
        for error in errors[:25]:
            entry = f"ERR {error}"
            self.history_entries.append(entry)
            self.history_list.insert(tk.END, entry)
        self.history_list.yview_moveto(1)

        if cancelled:
            self.status.set(f"Cancelado. Convertidas: {converted}. Errores: {len(errors)}.")
            messagebox.showinfo(APP_NAME, f"Conversion cancelada.\nImagenes convertidas: {converted}")
        elif errors:
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
