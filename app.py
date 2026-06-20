from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime
from html import escape
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog
import tkinter as tk
from tkinter import ttk

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageSequence, ImageTk, UnidentifiedImageError

try:
    import rawpy

    RAWPY_AVAILABLE = True
except Exception:
    rawpy = None
    RAWPY_AVAILABLE = False

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
APP_VERSION = "1.3.8"
GITHUB_REPO = "Enryuuh/Converter"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
LATEST_RELEASE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
BASE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
LOGO_PNG = BASE_DIR / "assets" / "converter-logo.png"
LOGO_ICO = BASE_DIR / "assets" / "converter-logo.ico"
PORTABLE_FLAG = APP_DIR / "portable.flag"
CONFIG_DIR = APP_DIR / "data" if PORTABLE_FLAG.exists() else Path(os.getenv("APPDATA", str(Path.home()))) / "Converter"
PROFILES_PATH = CONFIG_DIR / "profiles.json"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
LOG_PATH = CONFIG_DIR / "converter.log"
SESSION_PATH = CONFIG_DIR / "session.json"
CONTEXT_MENU_KEYS = (
    r"Software\Classes\*\shell\Converter",
    r"Software\Classes\Directory\shell\Converter",
)

STANDARD_INPUT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".jpe",
    ".jfif",
    ".png",
    ".webp",
    ".bmp",
    ".dib",
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

RAW_INPUT_EXTENSIONS = {
    ".3fr",
    ".ari",
    ".arw",
    ".bay",
    ".cr2",
    ".cr3",
    ".crw",
    ".dcr",
    ".dng",
    ".erf",
    ".fff",
    ".gpr",
    ".iiq",
    ".k25",
    ".kdc",
    ".mef",
    ".mos",
    ".mrw",
    ".nef",
    ".nrw",
    ".orf",
    ".pef",
    ".raf",
    ".raw",
    ".rw2",
    ".rwl",
    ".sr2",
    ".srf",
    ".srw",
    ".x3f",
}

SUPPORTED_INPUT_EXTENSIONS = STANDARD_INPUT_EXTENSIONS | RAW_INPUT_EXTENSIONS

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
    "SVG": {"ext": ".svg", "save_format": "SVG", "supports_alpha": True, "quality": False, "vector": True},
}

INPUT_FILE_TYPES = [
    (
        "Imagenes y RAW",
        "*.jpg *.jpeg *.jpe *.jfif *.png *.webp *.bmp *.dib *.gif *.tif *.tiff *.ico *.heic *.heif *.ppm *.pgm *.pbm *.avif *.3fr *.ari *.arw *.bay *.cr2 *.cr3 *.crw *.dcr *.dng *.erf *.fff *.gpr *.iiq *.k25 *.kdc *.mef *.mos *.mrw *.nef *.nrw *.orf *.pef *.raf *.raw *.rw2 *.rwl *.sr2 *.srf *.srw *.x3f",
    ),
    (
        "RAW de camara",
        "*.3fr *.ari *.arw *.bay *.cr2 *.cr3 *.crw *.dcr *.dng *.erf *.fff *.gpr *.iiq *.k25 *.kdc *.mef *.mos *.mrw *.nef *.nrw *.orf *.pef *.raf *.raw *.rw2 *.rwl *.sr2 *.srf *.srw *.x3f",
    ),
    ("Todos los archivos", "*.*"),
]


@dataclass(frozen=True)
class ConversionOptions:
    output_format: str
    output_formats: tuple[str, ...]
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
    naming_template: str
    overwrite: bool
    combine_pdf: bool
    target_size_enabled: bool
    target_size_kb: int | None
    max_workers: int
    strip_metadata: bool
    open_output_when_done: bool
    lossless: bool
    keep_folder_structure: bool
    use_output_subfolder: bool
    remove_background: bool
    remove_background_tolerance: int
    remove_background_feather: int
    rotate_degrees: int
    flip_horizontal: bool
    flip_vertical: bool
    crop_enabled: bool
    crop_left: int
    crop_top: int
    crop_right: int
    crop_bottom: int
    square_canvas: bool
    canvas_size: int | None
    canvas_transparent: bool
    brightness: int
    contrast: int
    saturation: int
    large_file_rule_enabled: bool
    large_file_threshold_kb: int | None
    large_file_quality: int
    pdf_page_size: str
    pdf_auto_orientation: bool
    create_zip: bool
    notify_on_done: bool


def is_supported_image(path: Path) -> bool:
    if path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS:
        return True
    return can_identify_image(path)


def is_raw_image(path: Path) -> bool:
    return path.suffix.lower() in RAW_INPUT_EXTENSIONS


def can_identify_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            return bool(image.format)
    except (OSError, SyntaxError, ValueError, UnidentifiedImageError):
        return False


def raw_format_name(path: Path) -> str:
    extension = path.suffix.replace(".", "").upper() or "RAW"
    return f"RAW ({extension})"


def parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.strip().lstrip("v").split("."):
        digits = "".join(char for char in part if char.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def parse_output_formats(primary: str, extra_formats: str = "") -> tuple[str, ...]:
    requested: list[str] = []
    tokens = [primary, *extra_formats.replace(";", ",").replace("|", ",").split(",")]
    for token in tokens:
        value = token.strip().upper().lstrip(".")
        if value == "JPG":
            value = "JPG"
        if not value:
            continue
        if value not in OUTPUT_FORMATS:
            raise ValueError(f"Formato no soportado: {token.strip()}")
        if value not in requested:
            requested.append(value)
    return tuple(requested or [primary.upper()])


def format_conversion_summary(input_bytes: int, output_bytes: int) -> str:
    if input_bytes <= 0 or output_bytes <= 0:
        return f"Salida generada: {format_size(output_bytes)}"
    difference = input_bytes - output_bytes
    percent = abs(difference) / input_bytes * 100
    if difference > 0:
        return f"{format_size(input_bytes)} -> {format_size(output_bytes)} ({percent:.1f}% menos)"
    if difference < 0:
        return f"{format_size(input_bytes)} -> {format_size(output_bytes)} ({percent:.1f}% mas)"
    return f"{format_size(input_bytes)} -> {format_size(output_bytes)} (sin cambio)"


def format_output_estimate_summary(input_bytes: int, estimates: list[tuple[str, int]]) -> str:
    if not estimates:
        return "Peso estimado de salida: sin formatos seleccionados."
    if len(estimates) == 1:
        output_format, output_bytes = estimates[0]
        return f"Peso estimado de salida: {output_format} {format_conversion_summary(input_bytes, output_bytes)}"

    parts = [f"{output_format} {format_size(output_bytes)}" for output_format, output_bytes in estimates]
    total_bytes = sum(output_bytes for _output_format, output_bytes in estimates)
    return f"Peso estimado de salida: {', '.join(parts)} | Total por foto {format_size(total_bytes)}"


def format_estimate_cell(estimates: list[tuple[str, int]]) -> str:
    if not estimates:
        return "-"
    total_bytes = sum(output_bytes for _output_format, output_bytes in estimates)
    if len(estimates) == 1:
        return format_size(total_bytes)
    return f"{format_size(total_bytes)} total"


def file_signature(path: Path) -> str:
    digest = hashlib.sha256()
    size = path.stat().st_size
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"{size}:{digest.hexdigest()}"


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {remaining_minutes}m"
    if remaining_minutes:
        return f"{remaining_minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def append_log(message: str) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        self.after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self.after_id = self.widget.after(450, self._show)

    def _cancel(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self) -> None:
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify="left",
            bg="#111827",
            fg="#f8fafc",
            relief="solid",
            bd=1,
            padx=10,
            pady=7,
            wraplength=330,
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


def load_raw_image(path: Path) -> Image.Image:
    if not RAWPY_AVAILABLE or rawpy is None:
        raise RuntimeError("Soporte RAW no disponible. Instala rawpy para revelar archivos RAW.")

    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
    return Image.fromarray(rgb)


def describe_raw_image(path: Path) -> tuple[str, str, str, str]:
    weight = format_size(path.stat().st_size) if path.exists() else "-"
    if not RAWPY_AVAILABLE or rawpy is None:
        return raw_format_name(path), "No detectado", "Soporte RAW no disponible", weight

    try:
        with rawpy.imread(str(path)) as raw:
            sizes = raw.sizes
            width = sizes.iwidth or sizes.width or sizes.raw_width
            height = sizes.iheight or sizes.height or sizes.raw_height
        return raw_format_name(path), f"{width} x {height}", "RAW de camara", weight
    except Exception as exc:
        return raw_format_name(path), "No detectado", f"RAW no soportado: {exc}", weight


def describe_image(path: Path) -> tuple[str, str, str, str]:
    if is_raw_image(path):
        return describe_raw_image(path)

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


class SafeFormatMap(dict):
    def __missing__(self, key: str) -> str:
        return ""


def render_output_stem(source: Path, options: ConversionOptions, index: int) -> str:
    if options.naming_mode == "Numerado":
        return f"{index:03d}_{source.stem}"
    if options.naming_mode == "Prefijo/sufijo":
        return f"{safe_name_part(options.prefix)}{source.stem}{safe_name_part(options.suffix)}"
    if options.naming_mode == "Plantilla":
        size_text = format_size(source.stat().st_size if source.exists() else 0).replace(" ", "")
        tokens = SafeFormatMap(
            name=source.stem,
            index=f"{index:03d}",
            format=options.output_format.lower(),
            date=datetime.now().strftime("%Y%m%d"),
            time=datetime.now().strftime("%H%M%S"),
            size=size_text,
            folder=source.parent.name,
        )
        try:
            stem = options.naming_template.format_map(tokens).strip()
        except (KeyError, ValueError):
            stem = f"{source.stem}_{index:03d}"
        return safe_name_part(stem or source.stem)
    return source.stem


def output_directory_for_source(source: Path, output_dir: Path, options: ConversionOptions, source_root: Path | None = None) -> Path:
    if not options.keep_folder_structure or source_root is None:
        return output_dir
    try:
        relative_parent = source.parent.resolve().relative_to(source_root.resolve())
    except (OSError, ValueError):
        return output_dir
    return output_dir / relative_parent


def build_output_path(
    source: Path,
    output_dir: Path,
    options: ConversionOptions,
    index: int,
    reserved: set[Path] | None = None,
    source_root: Path | None = None,
) -> Path:
    suffix = OUTPUT_FORMATS[options.output_format]["ext"]
    target_dir = output_directory_for_source(source, output_dir, options, source_root)
    stem = render_output_stem(source, options, index)

    candidate = target_dir / f"{stem}{suffix}"
    counter = 1
    if options.overwrite:
        if reserved is not None:
            while candidate in reserved:
                candidate = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            reserved.add(candidate)
        return candidate

    while candidate.exists() or (reserved is not None and candidate in reserved):
        candidate = target_dir / f"{stem}_{counter}{suffix}"
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


def apply_basic_edits(image: Image.Image, options: ConversionOptions) -> Image.Image:
    edited = image.copy()
    if options.crop_enabled:
        left = max(0, min(options.crop_left, edited.width - 1))
        top = max(0, min(options.crop_top, edited.height - 1))
        right_margin = max(0, min(options.crop_right, edited.width - left - 1))
        bottom_margin = max(0, min(options.crop_bottom, edited.height - top - 1))
        right = edited.width - right_margin
        bottom = edited.height - bottom_margin
        if right > left and bottom > top:
            edited = edited.crop((left, top, right, bottom))
    if options.rotate_degrees:
        edited = edited.rotate(-options.rotate_degrees, expand=True)
    if options.flip_horizontal:
        edited = ImageOps.mirror(edited)
    if options.flip_vertical:
        edited = ImageOps.flip(edited)
    if options.brightness != 0:
        edited = ImageEnhance.Brightness(edited).enhance(max(0.0, 1 + options.brightness / 100))
    if options.contrast != 0:
        edited = ImageEnhance.Contrast(edited).enhance(max(0.0, 1 + options.contrast / 100))
    if options.saturation != 0:
        edited = ImageEnhance.Color(edited).enhance(max(0.0, 1 + options.saturation / 100))
    return edited


def apply_square_canvas(image: Image.Image, options: ConversionOptions) -> Image.Image:
    if not options.square_canvas:
        return image
    supports_alpha = OUTPUT_FORMATS[options.output_format]["supports_alpha"]
    use_alpha = options.canvas_transparent and supports_alpha
    side = options.canvas_size or max(image.size)
    side = max(1, side)
    content = image.convert("RGBA")
    if content.width > side or content.height > side:
        content.thumbnail((side, side), Image.Resampling.LANCZOS)
    background = (*options.background, 0 if use_alpha else 255)
    canvas = Image.new("RGBA", (side, side), background)
    canvas.alpha_composite(content, ((side - content.width) // 2, (side - content.height) // 2))
    return canvas if use_alpha else canvas.convert("RGB")


def flatten_alpha(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (*background, 255))
        canvas.alpha_composite(rgba)
        return canvas.convert("RGB")

    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def remove_background_from_image(image: Image.Image, tolerance: int = 32, feather: int = 1) -> Image.Image:
    rgba = image.convert("RGBA")
    if rgba.width <= 1 or rgba.height <= 1:
        return rgba

    work = rgba.convert("RGB")
    corner_colors = {work.getpixel((0, 0)), work.getpixel((work.width - 1, 0)), work.getpixel((0, work.height - 1)), work.getpixel((work.width - 1, work.height - 1))}
    marker = (255, 0, 255)
    for candidate in ((255, 0, 255), (0, 255, 0), (0, 0, 255), (255, 255, 0), (1, 2, 3)):
        if candidate not in corner_colors:
            marker = candidate
            break
    seeds: set[tuple[int, int]] = set()
    samples = 12
    for index in range(samples + 1):
        x = round(index * (work.width - 1) / samples)
        y = round(index * (work.height - 1) / samples)
        seeds.add((x, 0))
        seeds.add((x, work.height - 1))
        seeds.add((0, y))
        seeds.add((work.width - 1, y))

    background_distance = max(18, min(128, tolerance * 2))
    for seed in seeds:
        seed_color = work.getpixel(seed)
        near_background = any(
            max(abs(seed_color[channel] - background[channel]) for channel in range(3)) <= background_distance
            for background in corner_colors
        )
        if seed_color != marker and near_background:
            ImageDraw.floodfill(work, seed, marker, thresh=max(0, min(96, tolerance)))

    marker_mask = Image.new("L", work.size, 0)
    marker_pixels = np.all(np.asarray(work, dtype=np.uint8) == np.array(marker, dtype=np.uint8), axis=2)
    marker_mask = Image.fromarray((marker_pixels.astype(np.uint8) * 255), "L")
    marker_mask = marker_mask.filter(ImageFilter.MaxFilter(3))
    if feather > 0:
        marker_mask = marker_mask.filter(ImageFilter.GaussianBlur(max(0.2, min(4.0, feather / 2))))

    alpha = rgba.getchannel("A")
    foreground_alpha = Image.eval(marker_mask, lambda value: 255 - value)
    alpha = multiply_alpha(alpha, foreground_alpha)
    rgba.putalpha(alpha)
    return rgba


def multiply_alpha(left: Image.Image, right: Image.Image) -> Image.Image:
    left_arr = np.asarray(left, dtype=np.uint16)
    right_arr = np.asarray(right, dtype=np.uint16)
    return Image.fromarray(((left_arr * right_arr) // 255).astype(np.uint8), "L")


def prepare_frame(image: Image.Image, options: ConversionOptions) -> Image.Image:
    output_format = options.output_format
    supports_alpha = OUTPUT_FORMATS[output_format]["supports_alpha"]
    edited = apply_basic_edits(image, options)
    resized = resize_image(edited, options)

    if options.remove_background:
        resized = remove_background_from_image(resized, options.remove_background_tolerance, options.remove_background_feather)
    resized = apply_square_canvas(resized, options)

    if output_format == "SVG":
        return resized.convert("RGBA")
    if not supports_alpha:
        return flatten_alpha(resized, options.background)
    if output_format == "GIF":
        return resized.convert("P", palette=Image.Palette.ADAPTIVE)
    if output_format == "ICO":
        return resized.convert("RGBA")
    return resized.copy()


def build_save_kwargs(options: ConversionOptions, quality_override: int | None = None) -> dict:
    save_kwargs = {}
    if options.lossless and options.output_format == "WEBP":
        save_kwargs["lossless"] = True
        save_kwargs["quality"] = 100
        save_kwargs["method"] = 6
    elif OUTPUT_FORMATS[options.output_format]["quality"]:
        save_kwargs["quality"] = quality_override if quality_override is not None else options.quality
        save_kwargs["optimize"] = True
    if options.output_format == "PNG":
        save_kwargs["optimize"] = True
    if options.output_format == "TIFF":
        save_kwargs["compression"] = "tiff_deflate"
    return save_kwargs


def image_to_svg_bytes(image: Image.Image, max_edge: int = 360, colors: int = 14) -> bytes:
    rgba = image.convert("RGBA")
    original_width, original_height = rgba.size
    if max(original_width, original_height) > max_edge:
        ratio = max_edge / max(original_width, original_height)
        svg_width = max(1, round(original_width * ratio))
        svg_height = max(1, round(original_height * ratio))
        rgba = rgba.resize((svg_width, svg_height), Image.Resampling.LANCZOS)
    else:
        svg_width, svg_height = rgba.size

    alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    rgb = rgba.convert("RGB").quantize(colors=max(2, min(64, colors)), method=Image.Quantize.MEDIANCUT).convert("RGB")
    rgb_arr = np.asarray(rgb, dtype=np.uint8)
    alpha_arr = alpha
    paths: dict[str, list[str]] = {}
    active_rects: dict[tuple[str, int, int], tuple[int, int, int, int]] = {}

    def flush_rect(rect_key: tuple[str, int, int], rect: tuple[int, int, int, int]) -> None:
        key, _start, _width = rect_key
        x0, y0, rect_width, rect_height = rect
        paths.setdefault(key, []).append(f"M{x0} {y0}h{rect_width}v{rect_height}H{x0}z")

    for y in range(svg_height):
        row_rects: dict[tuple[str, int, int], tuple[int, int, int, int]] = {}
        x = 0
        while x < svg_width:
            if alpha_arr[y, x] < 32:
                x += 1
                continue
            color = tuple(int(value) for value in rgb_arr[y, x])
            start = x
            opacity_values = [int(alpha_arr[y, x])]
            x += 1
            while x < svg_width and alpha_arr[y, x] >= 32 and tuple(int(value) for value in rgb_arr[y, x]) == color:
                opacity_values.append(int(alpha_arr[y, x]))
                x += 1
            opacity = round(sum(opacity_values) / (255 * len(opacity_values)), 3)
            key = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}|{opacity}"
            rect_key = (key, start, x - start)
            previous = active_rects.pop(rect_key, None)
            if previous is None:
                row_rects[rect_key] = (start, y, x - start, 1)
            else:
                x0, y0, rect_width, rect_height = previous
                row_rects[rect_key] = (x0, y0, rect_width, rect_height + 1)

        for rect_key, rect in active_rects.items():
            flush_rect(rect_key, rect)
        active_rects = row_rects

    for rect_key, rect in active_rects.items():
        flush_rect(rect_key, rect)

    body: list[str] = []
    for key, commands in paths.items():
        fill, opacity = key.split("|", 1)
        opacity_attr = "" if opacity == "1.0" or opacity == "1" else f' fill-opacity="{escape(opacity)}"'
        body.append(f'<path fill="{fill}"{opacity_attr} d="{"".join(commands)}"/>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{original_width}" height="{original_height}" '
        f'viewBox="0 0 {svg_width} {svg_height}" shape-rendering="geometricPrecision">'
        f'{"".join(body)}</svg>'
    )
    return svg.encode("utf-8")


def save_svg_vector(frames: list[Image.Image], destination: Path | io.BytesIO) -> Path | io.BytesIO:
    payload = image_to_svg_bytes(frames[0])
    if isinstance(destination, io.BytesIO):
        destination.write(payload)
    else:
        destination.write_bytes(payload)
    return destination


def prepared_frames_from_source(source: Path, options: ConversionOptions) -> tuple[list[Image.Image], bool, dict]:
    if is_raw_image(source):
        image = load_raw_image(source)
        return [prepare_frame(image, options)], False, {}

    with Image.open(source) as image:
        preserve_frames = getattr(image, "is_animated", False) and options.output_format in {"GIF", "WEBP", "TIFF", "PDF"}
        source_info = {
            "duration": image.info.get("duration", 100),
            "loop": image.info.get("loop", 0),
        }
        if not options.strip_metadata and options.output_format in {"JPG", "JPEG", "WEBP", "TIFF"} and image.info.get("exif"):
            source_info["exif"] = image.info["exif"]
        if preserve_frames:
            durations: list[int] = []
            disposals: list[int] = []
            frames = []
            for frame in ImageSequence.Iterator(image):
                durations.append(int(frame.info.get("duration", image.info.get("duration", 100)) or 100))
                if frame.info.get("disposal") is not None:
                    disposals.append(int(frame.info["disposal"]))
                frames.append(prepare_frame(frame, options))
            if durations:
                source_info["duration"] = durations
            if len(disposals) == len(frames):
                source_info["disposal"] = disposals
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
    if options.output_format == "SVG":
        return save_svg_vector(frames, destination)

    save_format = OUTPUT_FORMATS[options.output_format]["save_format"]
    save_kwargs = build_save_kwargs(options, quality_override)
    first = frames[0]

    if preserve_frames and len(frames) > 1:
        save_kwargs["save_all"] = True
        save_kwargs["append_images"] = frames[1:]
        if options.output_format in {"GIF", "WEBP"}:
            save_kwargs["duration"] = source_info.get("duration", 100)
            save_kwargs["loop"] = source_info.get("loop", 0)
            if options.output_format == "GIF" and source_info.get("disposal"):
                save_kwargs["disposal"] = source_info["disposal"]
    if not options.strip_metadata and source_info.get("exif") and options.output_format in {"JPG", "JPEG", "WEBP", "TIFF"}:
        save_kwargs["exif"] = source_info["exif"]

    first.save(destination, save_format, **save_kwargs)
    return destination


def converted_first_frame(source: Path, options: ConversionOptions) -> Image.Image:
    if is_raw_image(source):
        return prepare_frame(load_raw_image(source), options)

    with Image.open(source) as image:
        return prepare_frame(ImageOps.exif_transpose(image), options)


def estimate_output_size(source: Path, options: ConversionOptions) -> int:
    frames, preserve_frames, source_info = prepared_frames_from_source(source, options)
    buffer = io.BytesIO()
    save_prepared_frames(frames, buffer, options, preserve_frames, source_info)
    return len(buffer.getvalue())


def estimate_final_output_size(source: Path, options: ConversionOptions) -> int:
    if options.target_size_enabled and options.target_size_kb and OUTPUT_FORMATS[options.output_format]["quality"]:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / f"estimate{OUTPUT_FORMATS[options.output_format]['ext']}"
            convert_image_optimized(source, destination, options)
            return destination.stat().st_size
    return estimate_output_size(source, options)


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


def pdf_page_dimensions(image: Image.Image, options: ConversionOptions) -> tuple[int, int] | None:
    sizes = {"A4": (2480, 3508), "Carta": (2550, 3300)}
    page_size = sizes.get(options.pdf_page_size)
    if page_size is None:
        return None
    width, height = page_size
    if options.pdf_auto_orientation and image.width > image.height:
        return height, width
    return width, height


def fit_image_to_pdf_page(image: Image.Image, page_size: tuple[int, int] | None, background: tuple[int, int, int]) -> Image.Image:
    flattened = flatten_alpha(image, background)
    if page_size is None:
        return flattened
    page = Image.new("RGB", page_size, background)
    content = flattened.copy()
    content.thumbnail(page_size, Image.Resampling.LANCZOS)
    page.paste(content, ((page.width - content.width) // 2, (page.height - content.height) // 2))
    return page


def combine_images_to_pdf(files: list[Path], destination: Path, options: ConversionOptions) -> Path:
    pages: list[Image.Image] = []
    for source in files:
        if is_raw_image(source):
            first_frame = load_raw_image(source)
        else:
            with Image.open(source) as image:
                first_frame = ImageOps.exif_transpose(next(ImageSequence.Iterator(image)))
        prepared = prepare_frame(first_frame, replace(options, output_format="PNG", output_formats=("PNG",)))
        pages.append(fit_image_to_pdf_page(prepared, pdf_page_dimensions(prepared, options), options.background))

    if not pages:
        raise ValueError("No hay imagenes para PDF.")

    first = pages[0]
    first.save(destination, "PDF", save_all=True, append_images=pages[1:])
    return destination


def create_outputs_zip(outputs: list[Path], destination: Path) -> Path:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        used_names: set[str] = set()
        for output in outputs:
            if not output.exists() or output == destination:
                continue
            arcname = output.name
            counter = 1
            while arcname in used_names:
                arcname = f"{output.stem}_{counter}{output.suffix}"
                counter += 1
            used_names.add(arcname)
            archive.write(output, arcname)
    return destination


def write_conversion_reports(
    output_dir: Path,
    outputs: list[Path],
    errors: list[str],
    converted: int,
    cancelled: bool,
    input_bytes: int,
    output_bytes: int,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"converter_report_{timestamp}.csv"
    txt_path = output_dir / f"converter_report_{timestamp}.txt"
    html_path = output_dir / f"converter_report_{timestamp}.html"
    summary = format_conversion_summary(input_bytes, output_bytes)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["tipo", "archivo", "ruta", "peso_bytes", "detalle"])
        for output in outputs:
            writer.writerow(["OK", output.name, str(output.parent), output.stat().st_size if output.exists() else 0, ""])
        for error in errors:
            writer.writerow(["ERROR", "", "", "", error])

    lines = [
        f"Converter report {timestamp}",
        f"Estado: {'cancelado' if cancelled else 'terminado'}",
        f"Generados: {converted}",
        f"Errores: {len(errors)}",
        f"Resumen: {summary}",
        "",
        "Archivos generados:",
    ]
    lines.extend(f"- {output.name} ({format_size(output.stat().st_size) if output.exists() else '-'}) -> {output.parent}" for output in outputs)
    if errors:
        lines.extend(["", "Errores:"])
        lines.extend(f"- {error}" for error in errors)
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows = "".join(
        f"<tr><td>{escape(output.name)}</td><td>{escape(format_size(output.stat().st_size) if output.exists() else '-')}</td><td>{escape(str(output.parent))}</td></tr>"
        for output in outputs
    )
    error_rows = "".join(f"<li>{escape(error)}</li>" for error in errors)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Reporte Converter</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:28px;color:#0f172a}"
        "table{border-collapse:collapse;width:100%;margin-top:16px}td,th{border:1px solid #dbe3ef;padding:8px;text-align:left}"
        "th{background:#f1f5f9}.err{color:#b91c1c}</style></head><body>"
        f"<h1>Reporte Converter</h1><p><strong>Estado:</strong> {'cancelado' if cancelled else 'terminado'}</p>"
        f"<p><strong>Generados:</strong> {converted} &nbsp; <strong>Errores:</strong> {len(errors)} &nbsp; <strong>Resumen:</strong> {escape(summary)}</p>"
        "<h2>Archivos generados</h2><table><tr><th>Archivo</th><th>Peso</th><th>Carpeta</th></tr>"
        f"{rows}</table><h2>Errores</h2><ul class='err'>{error_rows or '<li>Sin errores</li>'}</ul></body></html>"
    )
    html_path.write_text(html, encoding="utf-8")
    return txt_path, csv_path, html_path


def iter_input_images(paths: list[Path]) -> list[tuple[Path, Path]]:
    entries: list[tuple[Path, Path]] = []
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_dir():
            for child in resolved.rglob("*"):
                if child.is_file() and is_supported_image(child):
                    entries.append((child.resolve(), resolved))
        elif resolved.is_file() and is_supported_image(resolved):
            entries.append((resolved, resolved.parent))
    return entries


def parse_resize_arg(value: str) -> tuple[int | None, int | None]:
    value = value.lower().strip()
    if not value:
        return None, None
    if "x" in value:
        left, right = value.split("x", 1)
        return (int(left) if left else None, int(right) if right else None)
    return int(value), None


def run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Convertir imagenes por lote sin abrir la interfaz.")
    parser.add_argument("paths", nargs="+", help="Archivos o carpetas de imagenes.")
    parser.add_argument("--to", default="WEBP", help="Formato principal de salida, por ejemplo WEBP, PNG o JPG.")
    parser.add_argument("--extra", default="", help="Formatos extra separados por coma.")
    parser.add_argument("--output", default=str(Path.cwd() / "Converter_Output"), help="Carpeta de salida.")
    parser.add_argument("--quality", type=int, default=85, help="Calidad 1-100 para formatos con compresion.")
    parser.add_argument("--resize", default="", help="Tamano: 1200, 1200x800, 1200x o x800.")
    parser.add_argument("--background", default="#ffffff", help="Color de fondo para formatos sin transparencia.")
    parser.add_argument("--lossless", action="store_true", help="WEBP sin perdida.")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribir si existe.")
    parser.add_argument("--keep-structure", action="store_true", help="Mantener estructura de carpetas.")
    parser.add_argument("--subfolder", action="store_true", help="Crear subcarpeta Converter_Output dentro de --output.")
    parser.add_argument("--remove-background", action="store_true", help="Quitar fondo ligero desde bordes.")
    parser.add_argument("--strip-metadata", action="store_true", default=True, help="Quitar metadatos EXIF.")
    args = parser.parse_args(argv)

    output_format = args.to.upper().lstrip(".")
    output_formats = parse_output_formats(output_format, args.extra)
    width, height = parse_resize_arg(args.resize)
    output_dir = Path(args.output).expanduser()
    if args.subfolder:
        output_dir = output_dir / "Converter_Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = iter_input_images([Path(path) for path in args.paths])
    if not entries:
        return 2

    options = ConversionOptions(
        output_format=output_format,
        output_formats=output_formats,
        quality=max(1, min(100, args.quality)),
        output_dir=output_dir,
        resize_enabled=bool(width or height),
        width=width,
        height=height,
        keep_aspect=True,
        background=ImageColor.getrgb(args.background),
        naming_mode="Conservar",
        prefix="",
        suffix="",
        naming_template="{name}_{format}",
        overwrite=args.overwrite,
        combine_pdf=False,
        target_size_enabled=False,
        target_size_kb=None,
        max_workers=max(1, min(4, os.cpu_count() or 1)),
        strip_metadata=args.strip_metadata,
        open_output_when_done=False,
        lossless=args.lossless,
        keep_folder_structure=args.keep_structure,
        use_output_subfolder=args.subfolder,
        remove_background=args.remove_background,
        remove_background_tolerance=32,
        remove_background_feather=1,
        rotate_degrees=0,
        flip_horizontal=False,
        flip_vertical=False,
        crop_enabled=False,
        crop_left=0,
        crop_top=0,
        crop_right=0,
        crop_bottom=0,
        square_canvas=False,
        canvas_size=None,
        canvas_transparent=True,
        brightness=0,
        contrast=0,
        saturation=0,
        large_file_rule_enabled=False,
        large_file_threshold_kb=None,
        large_file_quality=72,
        pdf_page_size="Original",
        pdf_auto_orientation=True,
        create_zip=False,
        notify_on_done=False,
    )
    reserved: set[Path] = set()
    for index, (source, root) in enumerate(entries, start=1):
        for output_format in output_formats:
            format_options = replace(options, output_format=output_format, output_formats=(output_format,))
            destination = build_output_path(source, output_dir, format_options, index, reserved, root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            convert_image_optimized(source, destination, format_options)
    return 0


class ImageConverterApp(TkBase):
    def __init__(self, restore_session: bool = False) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1240x780")
        self.minsize(1080, 700)
        if LOGO_ICO.exists():
            self.iconbitmap(LOGO_ICO)

        self.files: list[Path] = []
        self.metadata_cache: dict[Path, tuple[str, str, str, str]] = {}
        self.file_status: dict[Path, str] = {}
        self.file_signatures: dict[Path, str] = {}
        self.file_estimates: dict[Path, str] = {}
        self.file_estimate_cache: dict[tuple, str] = {}
        self.file_roots: dict[Path, Path] = {}
        self.duplicate_signatures: set[str] = set()
        self.thumbnail_images: dict[Path, ImageTk.PhotoImage] = {}
        self.logo_image: ImageTk.PhotoImage | None = None
        self.preview_image: ImageTk.PhotoImage | None = None
        self.preview_images: list[ImageTk.PhotoImage] = []
        self.preview_compare_payload: tuple[Path, Image.Image, Image.Image, int, int, str] | None = None
        self.preview_request_id = 0
        self.preview_estimate_request_id = 0
        self.preview_estimate_after_id: str | None = None
        self.file_estimate_request_id = 0
        self.file_estimate_after_id: str | None = None
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()
        self.profiles: dict[str, dict] = self._load_profiles()
        self.history_entries: list[str] = []
        self.last_failed_files: list[Path] = []
        self.last_conversion_files: list[Path] = []
        self.conversion_running = False

        self.output_dir = tk.StringVar(value=str(Path.home() / "Pictures"))
        self.output_format = tk.StringVar(value="WEBP")
        self.extra_formats = tk.StringVar(value="")
        self.quality = tk.IntVar(value=85)
        self.status = tk.StringVar(value="Listo para convertir. Agrega imagenes para empezar.")
        self.preview_info = tk.StringVar(value="Selecciona una imagen para ver detalles y vista previa.")
        self.preview_estimate_info = tk.StringVar(value="Peso estimado de salida: selecciona una imagen.")
        self.batch_summary_info = tk.StringVar(value="Ahorro total: usa Estimar lote para calcular el lote completo.")
        self.conversion_stats_info = tk.StringVar(value="Estadisticas: sin conversion ejecutada.")
        self.filter_status = tk.StringVar(value="Todos")
        self.filter_format = tk.StringVar(value="Todos")
        self.filter_min_kb = tk.StringVar(value="")
        self.filter_max_kb = tk.StringVar(value="")
        self.queue_search = tk.StringVar(value="")
        self.queue_sort = tk.StringVar(value="Orden agregado")
        self.resize_enabled = tk.BooleanVar(value=False)
        self.resize_width = tk.StringVar(value="")
        self.resize_height = tk.StringVar(value="")
        self.keep_aspect = tk.BooleanVar(value=True)
        self.background_hex = tk.StringVar(value="#ffffff")
        self.naming_mode = tk.StringVar(value="Conservar")
        self.prefix = tk.StringVar(value="")
        self.suffix = tk.StringVar(value="")
        self.naming_template = tk.StringVar(value="{name}_{format}")
        self.overwrite = tk.BooleanVar(value=False)
        self.combine_pdf = tk.BooleanVar(value=False)
        self.target_size_enabled = tk.BooleanVar(value=False)
        self.target_size_kb = tk.StringVar(value="")
        self.max_workers = tk.IntVar(value=min(4, max(1, os.cpu_count() or 1)))
        self.strip_metadata = tk.BooleanVar(value=True)
        self.open_output_when_done = tk.BooleanVar(value=True)
        self.lossless = tk.BooleanVar(value=False)
        self.keep_folder_structure = tk.BooleanVar(value=False)
        self.use_output_subfolder = tk.BooleanVar(value=False)
        self.remove_background = tk.BooleanVar(value=False)
        self.remove_background_tolerance = tk.IntVar(value=32)
        self.remove_background_feather = tk.IntVar(value=1)
        self.rotate_degrees = tk.IntVar(value=0)
        self.flip_horizontal = tk.BooleanVar(value=False)
        self.flip_vertical = tk.BooleanVar(value=False)
        self.crop_enabled = tk.BooleanVar(value=False)
        self.crop_left = tk.StringVar(value="0")
        self.crop_top = tk.StringVar(value="0")
        self.crop_right = tk.StringVar(value="0")
        self.crop_bottom = tk.StringVar(value="0")
        self.square_canvas = tk.BooleanVar(value=False)
        self.canvas_size = tk.StringVar(value="")
        self.canvas_transparent = tk.BooleanVar(value=True)
        self.brightness = tk.IntVar(value=0)
        self.contrast = tk.IntVar(value=0)
        self.saturation = tk.IntVar(value=0)
        self.large_file_rule_enabled = tk.BooleanVar(value=False)
        self.large_file_threshold_kb = tk.StringVar(value="2048")
        self.large_file_quality = tk.IntVar(value=72)
        self.pdf_page_size = tk.StringVar(value="Original")
        self.pdf_auto_orientation = tk.BooleanVar(value=True)
        self.create_zip = tk.BooleanVar(value=False)
        self.notify_on_done = tk.BooleanVar(value=True)
        self.profile_name = tk.StringVar(value="")
        self.dark_mode = tk.BooleanVar(value=False)
        self.preview_zoom = tk.DoubleVar(value=1.0)
        self.progress = tk.DoubleVar(value=0)
        self.throughput_info = tk.StringVar(value="Sin conversion activa.")
        self.output_name_preview = tk.StringVar(value="Salida: selecciona una imagen.")

        self._apply_settings(self._load_settings())
        self._build_ui()
        self._bind_output_option_traces()
        self._refresh_option_states()
        if restore_session:
            self.after(300, lambda: self.restore_session(silent=True))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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
        left_panel.rowconfigure(4, weight=1)

        left_header = tk.Frame(left_panel, bg=self.colors["surface"])
        left_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        left_header.columnconfigure(0, weight=1)
        tk.Label(left_header, text="Cola de imagenes", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        queue_actions = tk.Frame(left_header, bg=self.colors["surface"])
        queue_actions.grid(row=0, column=1, sticky="e")
        self._button(queue_actions, "Subir", lambda: self.move_selected(-1), "ghost").grid(row=0, column=0, padx=(0, 8))
        self._button(queue_actions, "Bajar", lambda: self.move_selected(1), "ghost").grid(row=0, column=1, padx=(0, 8))
        self._button(queue_actions, "Quitar", self.remove_selected, "ghost").grid(row=0, column=2, padx=(0, 8))
        self._button(queue_actions, "Limpiar", self.clear_files, "ghost").grid(row=0, column=3)

        filter_bar = tk.Frame(left_panel, bg=self.colors["surface"])
        filter_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        for column in range(12):
            filter_bar.columnconfigure(column, weight=1 if column in {1, 3, 5, 6, 8, 10} else 0)
        self._field_label(filter_bar, "Estado", "Filtra por estado de conversion.").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.filter_status_combo = ttk.Combobox(
            filter_bar,
            textvariable=self.filter_status,
            values=["Todos", "Pendiente", "Procesando", "OK", "Error", "Cancelado"],
            state="readonly",
            width=12,
        )
        self.filter_status_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.filter_status_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_filters())
        self._field_label(filter_bar, "Tipo", "Filtra por formato detectado.").grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.filter_format_combo = ttk.Combobox(filter_bar, textvariable=self.filter_format, values=["Todos"], state="readonly", width=12)
        self.filter_format_combo.grid(row=0, column=3, sticky="ew", padx=(0, 10))
        self.filter_format_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_filters())
        self._field_label(filter_bar, "KB min/max", "Filtra por peso original en KB.").grid(row=0, column=4, sticky="w", padx=(0, 8))
        self.filter_min_entry = ttk.Entry(filter_bar, textvariable=self.filter_min_kb, width=8)
        self.filter_min_entry.grid(row=0, column=5, sticky="ew", padx=(0, 6))
        self.filter_max_entry = ttk.Entry(filter_bar, textvariable=self.filter_max_kb, width=8)
        self.filter_max_entry.grid(row=0, column=6, sticky="ew", padx=(0, 10))
        self.filter_min_entry.bind("<KeyRelease>", lambda _event: self.apply_filters())
        self.filter_max_entry.bind("<KeyRelease>", lambda _event: self.apply_filters())
        self._field_label(filter_bar, "Buscar", "Filtra por nombre o ruta.").grid(row=0, column=7, sticky="w", padx=(0, 8))
        self.queue_search_entry = ttk.Entry(filter_bar, textvariable=self.queue_search, width=12)
        self.queue_search_entry.grid(row=0, column=8, sticky="ew", padx=(0, 10))
        self.queue_search_entry.bind("<KeyRelease>", lambda _event: self.apply_filters())
        self._field_label(filter_bar, "Orden", "Ordena la cola visible.").grid(row=0, column=9, sticky="w", padx=(0, 8))
        self.queue_sort_combo = ttk.Combobox(
            filter_bar,
            textvariable=self.queue_sort,
            values=["Orden agregado", "Nombre", "Peso", "Formato", "Estado", "Tamano"],
            state="readonly",
            width=12,
        )
        self.queue_sort_combo.grid(row=0, column=10, sticky="ew", padx=(0, 10))
        self.queue_sort_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_filters())
        self._button(filter_bar, "Todos", self.clear_filters, "ghost").grid(row=0, column=11, sticky="ew")

        queue_tools = tk.Frame(left_panel, bg=self.colors["surface"])
        queue_tools.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
        queue_tools.columnconfigure(0, weight=1)
        self._button(queue_tools, "Vista salidas", self.show_output_plan, "ghost").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._button(queue_tools, "Seleccionar errores", self.select_error_files, "ghost").grid(row=0, column=1, sticky="w", padx=(0, 8))
        self._button(queue_tools, "Quitar duplicados", self.remove_duplicate_files, "ghost").grid(row=0, column=2, sticky="w", padx=(0, 8))
        self._button(queue_tools, "Guardar sesion", self.save_session, "ghost").grid(row=0, column=3, sticky="w", padx=(0, 8))
        self._button(queue_tools, "Restaurar sesion", self.restore_session, "ghost").grid(row=0, column=4, sticky="w")

        self.drop_zone = tk.Canvas(left_panel, height=94, bg=self.colors["drop"], highlightthickness=0, bd=0)
        self.drop_zone.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.drop_zone.bind("<Configure>", self._draw_drop_zone)
        if DND_AVAILABLE:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self.handle_drop)
            self.drop_zone.bind("<Enter>", lambda _event: self._set_drop_active(True))
            self.drop_zone.bind("<Leave>", lambda _event: self._set_drop_active(False))
        else:
            self.drop_zone.create_text(20, 32, text="Arrastrar no esta disponible", anchor="w", fill=self.colors["primary"], font=("Segoe UI", 13, "bold"))

        table_frame = tk.Frame(left_panel, bg=self.colors["surface"])
        table_frame.grid(row=4, column=0, sticky="nsew", padx=16, pady=(0, 16))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("name", "status", "format", "dimensions", "weight", "estimate", "details", "path")
        self.file_tree = ttk.Treeview(table_frame, columns=columns, show="tree headings", selectmode="extended")
        self.file_tree.heading("#0", text="Vista")
        self.file_tree.column("#0", width=58, minwidth=58, stretch=False, anchor="center")
        headings = {
            "name": "Archivo",
            "status": "Estado",
            "format": "Tipo",
            "dimensions": "Tamano",
            "weight": "Peso",
            "estimate": "Est. salida",
            "details": "Detalle",
            "path": "Ruta",
        }
        widths = {"name": 178, "status": 84, "format": 68, "dimensions": 86, "weight": 72, "estimate": 86, "details": 118, "path": 140}
        for column, heading in headings.items():
            self.file_tree.heading(column, text=heading)
            self.file_tree.column(column, width=widths[column], minwidth=70, anchor="center" if column != "path" else "w")
        self.file_tree.grid(row=0, column=0, sticky="nsew")
        self.file_tree.bind("<<TreeviewSelect>>", self.update_preview)
        if DND_AVAILABLE:
            for target in (self, left_panel, table_frame, self.file_tree):
                target.drop_target_register(DND_FILES)
                target.dnd_bind("<<Drop>>", self.handle_drop)
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
        self._button(preview_head, "-", lambda: self.change_preview_zoom(-0.25), "ghost").grid(row=0, column=1, sticky="e", padx=(0, 6))
        self._button(preview_head, "+", lambda: self.change_preview_zoom(0.25), "ghost").grid(row=0, column=2, sticky="e", padx=(0, 8))
        self._button(preview_head, "Comparar", self.preview_output, "ghost").grid(row=0, column=3, sticky="e", padx=(0, 8))
        self._button(preview_head, "Estimar lote", self.estimate_batch_size, "ghost").grid(row=0, column=4, sticky="e")
        self.preview_canvas = tk.Canvas(preview_frame, height=270, bg=self.colors["surface_soft"], bd=0, highlightthickness=1, highlightbackground=self.colors["line"])
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
        tk.Label(
            preview_frame,
            textvariable=self.preview_estimate_info,
            bg=self.colors["surface"],
            fg=self.colors["primary"],
            font=("Segoe UI", 9, "bold"),
            wraplength=390,
            justify="left",
        ).grid(row=3, column=0, sticky="w", padx=16, pady=(0, 14))
        tk.Label(
            preview_frame,
            textvariable=self.batch_summary_info,
            bg=self.colors["surface"],
            fg=self.colors["success"],
            font=("Segoe UI", 9, "bold"),
            wraplength=390,
            justify="left",
        ).grid(row=4, column=0, sticky="w", padx=16, pady=(0, 14))
        tk.Label(
            preview_frame,
            textvariable=self.conversion_stats_info,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
            wraplength=390,
            justify="left",
        ).grid(row=5, column=0, sticky="w", padx=16, pady=(0, 14))

        history_frame = self._card(right_panel)
        history_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(1, weight=1)
        history_head = tk.Frame(history_frame, bg=self.colors["surface"])
        history_head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 10))
        history_head.columnconfigure(0, weight=1)
        tk.Label(history_head, text="Historial", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self._button(history_head, "Exportar", self.export_history, "ghost").grid(row=0, column=1, sticky="e", padx=(0, 8))
        self._button(history_head, "Limpiar", self.clear_history, "ghost").grid(row=0, column=2, sticky="e", padx=(0, 8))
        self._button(history_head, "Log", self.open_log_file, "ghost").grid(row=0, column=3, sticky="e")
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

        options_head = tk.Frame(options, bg=self.colors["surface"])
        options_head.grid(row=0, column=0, columnspan=10, sticky="ew", padx=16, pady=(14, 10))
        options_head.columnconfigure(0, weight=1)
        tk.Label(options_head, text="Salida y optimizacion", bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self._button(options_head, "Guia", self.show_options_guide, "ghost").grid(row=0, column=1, sticky="e")
        tk.Label(
            options_head,
            text="Elige un ajuste rapido o modifica solo lo necesario. Pasa el cursor por una opcion para ver para que sirve.",
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self._build_options_sections(options)

        footer = tk.Frame(self, bg=self.colors["bg"])
        footer.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 16))
        footer.columnconfigure(0, weight=1)
        footer_status = tk.Frame(footer, bg=self.colors["bg"])
        footer_status.grid(row=0, column=0, sticky="ew")
        tk.Label(footer_status, textvariable=self.status, bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        tk.Label(footer_status, textvariable=self.throughput_info, bg=self.colors["bg"], fg=self.colors["success"], font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(footer, variable=self.progress, maximum=100, style="Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=(14, 12), ipady=3)
        footer.columnconfigure(1, weight=1)
        self.retry_button = self._button(footer, "Reintentar", self.retry_failed, "ghost")
        self.retry_button.grid(row=0, column=2, sticky="e")
        self.repeat_button = self._button(footer, "Repetir", self.repeat_last_conversion, "ghost")
        self.repeat_button.grid(row=0, column=3, sticky="e", padx=(8, 0))
        self.pause_button = self._button(footer, "Pausar", self.toggle_pause_conversion, "ghost")
        self.pause_button.grid(row=0, column=4, sticky="e", padx=(8, 0))
        self.pause_button.configure(state=tk.DISABLED)
        self.convert_button = self._button(footer, "Convertir", self.start_conversion, "primary")
        self.convert_button.grid(row=0, column=5, sticky="e", padx=(8, 0))
        self.cancel_button = self._button(footer, "Cancelar", self.cancel_conversion, "ghost")
        self.cancel_button.grid(row=0, column=6, sticky="e", padx=(8, 0))
        self.cancel_button.configure(state=tk.DISABLED)

        self.bind_all("<Delete>", self._delete_shortcut)
        self.bind_all("<Control-o>", lambda _event: self.add_files())
        self.bind_all("<Control-Return>", lambda _event: self.start_conversion())
        self.bind_all("<Escape>", lambda _event: self.cancel_conversion() if self.conversion_running else None)
        self.bind_all("<Control-a>", self._select_all_files)

    def _build_options_sections(self, options: tk.Frame) -> None:
        notebook = ttk.Notebook(options)
        notebook.grid(row=1, column=0, columnspan=10, sticky="ew", padx=16, pady=(0, 14))

        salida = self._option_tab(notebook)
        tamano = self._option_tab(notebook)
        edicion = self._option_tab(notebook)
        nombres = self._option_tab(notebook)
        avanzado = self._option_tab(notebook)
        notebook.add(salida, text="Salida")
        notebook.add(tamano, text="Tamano y fondo")
        notebook.add(edicion, text="Edicion")
        notebook.add(nombres, text="Nombre y perfiles")
        notebook.add(avanzado, text="Avanzado")

        for tab in (salida, tamano, edicion, nombres, avanzado):
            for column in range(8):
                tab.columnconfigure(column, weight=1 if column in {1, 3, 5, 7} else 0)

        self._field_label(salida, "Ajuste rapido", "Atajo que rellena opciones segun el tipo de resultado.").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(12, 10))
        self.preset_combo = ttk.Combobox(
            salida,
            values=[
                "Personalizado",
                "Para web",
                "Instagram",
                "WhatsApp",
                "Impresion",
                "Maxima calidad",
                "Reducir peso",
                "Maximo ahorro",
                "Sin perdida",
                "Icono .ico",
                "PDF desde imagenes",
                "SVG vector",
                "Fondo transparente",
                "Producto tienda",
            ],
            state="readonly",
            width=18,
        )
        self._tooltip(self.preset_combo, "Presets para web, redes, producto, SVG, fondo transparente, PDF y ahorro.")
        self.preset_combo.set("Personalizado")
        self.preset_combo.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(12, 10))
        self.preset_combo.bind("<<ComboboxSelected>>", self.apply_preset)

        self._field_label(salida, "Formato", "Formato principal que se generara.").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(12, 10))
        self.format_combo = ttk.Combobox(salida, textvariable=self.output_format, values=list(OUTPUT_FORMATS.keys()), state="readonly", width=12)
        self._tooltip(self.format_combo, "WEBP para web, JPG para compatibilidad, PNG para transparencia, PDF para documentos.")
        self.format_combo.grid(row=0, column=3, sticky="ew", padx=(0, 14), pady=(12, 10))
        self.format_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_option_states())

        self._field_label(salida, "Extras", "Crea copias adicionales aparte del formato principal.").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(12, 10))
        self.extra_formats_entry = ttk.Entry(salida, textvariable=self.extra_formats, width=16)
        self._tooltip(self.extra_formats_entry, "Opcional. Formatos separados por coma: PNG,JPG,AVIF.")
        self.extra_formats_entry.grid(row=0, column=5, sticky="ew", padx=(0, 14), pady=(12, 10))

        self._field_label(salida, "Calidad", "Afecta JPG, JPEG, WEBP y AVIF.").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 10))
        self.quality_scale = ttk.Scale(salida, from_=1, to=100, variable=self.quality, orient="horizontal")
        self._tooltip(self.quality_scale, "85 es buen balance. Con peso maximo, Converter ajusta calidad automaticamente.")
        self.quality_scale.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.quality_label = tk.Label(salida, text=str(self.quality.get()), width=8, bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 10))
        self.quality_label.grid(row=1, column=4, sticky="w", pady=(0, 10))
        self.lossless_check = self._check(salida, "Sin perdida", self.lossless, self._refresh_option_states, "Usa WebP sin perdida cuando el formato lo permite.")
        self.lossless_check.grid(row=1, column=5, sticky="w", padx=(0, 10), pady=(0, 10))
        self._check(salida, "Un solo PDF", self.combine_pdf, self._refresh_option_states, "Une todas las imagenes en un unico PDF.").grid(row=1, column=6, sticky="w", pady=(0, 10))

        self._field_label(salida, "Carpeta salida", "Donde se guardan los archivos convertidos.").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 12))
        output_entry = ttk.Entry(salida, textvariable=self.output_dir)
        self._tooltip(output_entry, "Puedes escribir una ruta o usar Elegir. Si no existe, Converter intenta crearla.")
        output_entry.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(salida, "Elegir...", self.choose_output_dir, "ghost").grid(row=2, column=4, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(salida, "Abrir", self.open_output_dir, "ghost").grid(row=2, column=5, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._check(salida, "Subcarpeta Converter_Output", self.use_output_subfolder, self._handle_output_option_change, "Guarda todo dentro de una subcarpeta limpia.").grid(row=2, column=6, sticky="w", pady=(0, 12))
        self._check(salida, "Mantener carpetas", self.keep_folder_structure, self._handle_output_option_change, "Conserva la estructura relativa al agregar carpetas.").grid(row=2, column=7, sticky="w", pady=(0, 12))

        tk.Label(salida, textvariable=self.output_name_preview, bg=self.colors["surface"], fg=self.colors["primary"], font=("Segoe UI", 9, "bold")).grid(
            row=3, column=0, columnspan=8, sticky="w", pady=(0, 12)
        )

        self._check(tamano, "Cambiar tamano", self.resize_enabled, self._refresh_option_states, "Activa Ancho/Alto para redimensionar.").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(12, 10))
        self._field_label(tamano, "Ancho px", "Ancho final. Puedes dejarlo vacio.").grid(row=0, column=1, sticky="e", padx=(0, 8), pady=(12, 10))
        self.resize_width_entry = ttk.Entry(tamano, textvariable=self.resize_width, width=9)
        self.resize_width_entry.grid(row=0, column=2, sticky="ew", padx=(0, 14), pady=(12, 10))
        self._field_label(tamano, "Alto px", "Alto final. Puedes dejarlo vacio.").grid(row=0, column=3, sticky="e", padx=(0, 8), pady=(12, 10))
        self.resize_height_entry = ttk.Entry(tamano, textvariable=self.resize_height, width=9)
        self.resize_height_entry.grid(row=0, column=4, sticky="ew", padx=(0, 14), pady=(12, 10))
        self.keep_aspect_check = self._check(tamano, "Proporcion", self.keep_aspect, tooltip="Evita deformar la imagen.")
        self.keep_aspect_check.grid(row=0, column=5, sticky="w", pady=(12, 10))

        self._check(tamano, "Lienzo cuadrado", self.square_canvas, self._refresh_option_states, "Centra la imagen en un lienzo cuadrado.").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 10))
        self._field_label(tamano, "Lado px", "Opcional. Si queda vacio usa el lado mayor.").grid(row=1, column=1, sticky="e", padx=(0, 8), pady=(0, 10))
        self.canvas_size_entry = ttk.Entry(tamano, textvariable=self.canvas_size, width=9)
        self.canvas_size_entry.grid(row=1, column=2, sticky="ew", padx=(0, 14), pady=(0, 10))
        self._check(tamano, "Lienzo transparente", self.canvas_transparent, self._refresh_option_states, "Usa transparencia si el formato de salida la soporta.").grid(row=1, column=3, sticky="w", padx=(0, 8), pady=(0, 10))
        self.background_button = self._button(tamano, "Color fondo", self.choose_background, "ghost")
        self._tooltip(self.background_button, "Color usado en JPG, BMP, PDF o lienzos no transparentes.")
        self.background_button.grid(row=1, column=4, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.color_swatch = tk.Label(tamano, textvariable=self.background_hex, bg=self.background_hex.get(), fg=self._text_color_for_background(self.background_hex.get()), width=10, relief="solid", bd=1, font=("Segoe UI", 9))
        self.color_swatch.grid(row=1, column=5, sticky="ew", pady=(0, 10))

        self.remove_background_check = self._check(tamano, "Quitar fondo", self.remove_background, self._refresh_option_states, "Elimina fondos conectados a los bordes, sin IA pesada.")
        self.remove_background_check.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 12))
        self._field_label(tamano, "Fuerza", "Sube si quedan bordes; baja si borra partes del objeto.").grid(row=2, column=1, sticky="e", padx=(0, 8), pady=(0, 12))
        self.remove_background_scale = ttk.Scale(tamano, from_=8, to=96, variable=self.remove_background_tolerance, orient="horizontal")
        self.remove_background_scale.grid(row=2, column=2, columnspan=2, sticky="ew", padx=(0, 8), pady=(0, 12))
        self.remove_background_label = tk.Label(tamano, text=str(self.remove_background_tolerance.get()), width=5, bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 10))
        self.remove_background_label.grid(row=2, column=4, sticky="w", pady=(0, 12))
        self._field_label(tamano, "Borde suave", "Suaviza halos del recorte de fondo.").grid(row=2, column=5, sticky="e", padx=(0, 8), pady=(0, 12))
        self.remove_background_feather_spinbox = tk.Spinbox(tamano, from_=0, to=8, textvariable=self.remove_background_feather, width=5, **self._spinbox_style())
        self.remove_background_feather_spinbox.grid(row=2, column=6, sticky="w", pady=(0, 12))

        self._field_label(tamano, "Brillo", "Ajuste global de brillo, de -100 a 100.").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(0, 10))
        self.brightness_scale = ttk.Scale(tamano, from_=-100, to=100, variable=self.brightness, orient="horizontal")
        self.brightness_scale.grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=(0, 10))
        tk.Label(tamano, textvariable=self.brightness, width=5, bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 9)).grid(row=3, column=2, sticky="w", padx=(0, 12), pady=(0, 10))
        self._field_label(tamano, "Contraste", "Ajuste global de contraste.").grid(row=3, column=3, sticky="w", padx=(0, 8), pady=(0, 10))
        self.contrast_scale = ttk.Scale(tamano, from_=-100, to=100, variable=self.contrast, orient="horizontal")
        self.contrast_scale.grid(row=3, column=4, sticky="ew", padx=(0, 8), pady=(0, 10))
        tk.Label(tamano, textvariable=self.contrast, width=5, bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 9)).grid(row=3, column=5, sticky="w", padx=(0, 12), pady=(0, 10))
        self._field_label(tamano, "Saturacion", "Ajuste global de color.").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=(0, 12))
        self.saturation_scale = ttk.Scale(tamano, from_=-100, to=100, variable=self.saturation, orient="horizontal")
        self.saturation_scale.grid(row=4, column=1, sticky="ew", padx=(0, 8), pady=(0, 12))
        tk.Label(tamano, textvariable=self.saturation, width=5, bg=self.colors["surface"], fg=self.colors["text"], font=("Segoe UI", 9)).grid(row=4, column=2, sticky="w", padx=(0, 12), pady=(0, 12))

        self._field_label(edicion, "Rotar", "Rotacion aplicada antes de convertir.").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(12, 10))
        self.rotate_combo = ttk.Combobox(edicion, textvariable=self.rotate_degrees, values=[0, 90, 180, 270], state="readonly", width=8)
        self.rotate_combo.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(12, 10))
        self._check(edicion, "Voltear horizontal", self.flip_horizontal, self._handle_output_option_change, "Invierte izquierda/derecha.").grid(row=0, column=2, sticky="w", padx=(0, 12), pady=(12, 10))
        self._check(edicion, "Voltear vertical", self.flip_vertical, self._handle_output_option_change, "Invierte arriba/abajo.").grid(row=0, column=3, sticky="w", pady=(12, 10))
        self._check(edicion, "Recortar bordes", self.crop_enabled, self._refresh_option_states, "Recorta pixeles desde cada borde.").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 12))
        for column, (label, variable) in enumerate((("Izq", self.crop_left), ("Arriba", self.crop_top), ("Der", self.crop_right), ("Abajo", self.crop_bottom)), start=1):
            self._field_label(edicion, label, "Pixeles a recortar desde este borde.").grid(row=1, column=column * 2 - 1, sticky="e", padx=(0, 6), pady=(0, 12))
            entry = ttk.Entry(edicion, textvariable=variable, width=7)
            entry.grid(row=1, column=column * 2, sticky="ew", padx=(0, 10), pady=(0, 12))
            setattr(self, f"crop_{label.lower()}_entry", entry)

        self._field_label(nombres, "Modo nombre", "Controla nombres nuevos.").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(12, 10))
        self.naming_combo = ttk.Combobox(nombres, textvariable=self.naming_mode, values=["Conservar", "Numerado", "Prefijo/sufijo", "Plantilla"], state="readonly", width=16)
        self.naming_combo.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(12, 10))
        self.naming_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_option_states())
        self._field_label(nombres, "Plantilla", "{name}, {index}, {format}, {date}, {time}, {size}, {folder}.").grid(row=0, column=2, sticky="e", padx=(0, 8), pady=(12, 10))
        self.naming_template_entry = ttk.Entry(nombres, textvariable=self.naming_template, width=26)
        self.naming_template_entry.grid(row=0, column=3, columnspan=3, sticky="ew", padx=(0, 14), pady=(12, 10))
        self._check(nombres, "Reemplazar existentes", self.overwrite, tooltip="Si existe el nombre, lo reemplaza. Apagado crea nombres nuevos.").grid(row=0, column=6, sticky="w", pady=(12, 10))

        self._field_label(nombres, "Prefijo", "Texto antes del nombre original.").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 10))
        self.prefix_entry = ttk.Entry(nombres, textvariable=self.prefix, width=14)
        self.prefix_entry.grid(row=1, column=1, sticky="ew", padx=(0, 14), pady=(0, 10))
        self._field_label(nombres, "Sufijo", "Texto despues del nombre original.").grid(row=1, column=2, sticky="e", padx=(0, 8), pady=(0, 10))
        self.suffix_entry = ttk.Entry(nombres, textvariable=self.suffix, width=14)
        self.suffix_entry.grid(row=1, column=3, sticky="ew", padx=(0, 14), pady=(0, 10))

        self._field_label(nombres, "Perfil", "Guarda y carga combinaciones de opciones.").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 12))
        self.profile_combo = ttk.Combobox(nombres, textvariable=self.profile_name, values=sorted(self.profiles.keys()), state="readonly", width=18)
        self.profile_combo.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(nombres, "Cargar", self.load_selected_profile, "ghost").grid(row=2, column=2, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(nombres, "Guardar", self.save_current_profile, "ghost").grid(row=2, column=3, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(nombres, "Importar", self.import_profiles, "ghost").grid(row=2, column=4, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(nombres, "Exportar", self.export_profiles, "ghost").grid(row=2, column=5, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(nombres, "Exportar uno", self.export_selected_profile, "ghost").grid(row=2, column=6, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(nombres, "Defaults", self.install_builtin_profiles, "ghost").grid(row=2, column=7, sticky="ew", pady=(0, 12))
        self._button(nombres, "Restaurar ajustes", self.reset_current_settings, "ghost").grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(nombres, "Menu Windows", self.configure_context_menu, "ghost").grid(row=3, column=2, sticky="ew", padx=(0, 8), pady=(0, 12))

        self._check(avanzado, "Peso maximo (KB)", self.target_size_enabled, self._refresh_option_states, "Intenta limitar el peso por archivo.").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(12, 10))
        self.target_size_entry = ttk.Entry(avanzado, textvariable=self.target_size_kb, width=9)
        self.target_size_entry.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(12, 10))
        self._field_label(avanzado, "En paralelo", "Conversiones simultaneas.").grid(row=0, column=2, sticky="e", padx=(0, 8), pady=(12, 10))
        self.max_workers_spinbox = tk.Spinbox(avanzado, from_=1, to=max(1, min(16, os.cpu_count() or 1)), textvariable=self.max_workers, width=5, **self._spinbox_style())
        self.max_workers_spinbox.grid(row=0, column=3, sticky="w", padx=(0, 14), pady=(12, 10))
        self._check(avanzado, "Quitar datos EXIF", self.strip_metadata, tooltip="Elimina datos privados como camara, fecha o GPS.").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(12, 10))
        self._check(avanzado, "Abrir al final", self.open_output_when_done, tooltip="Abre la carpeta al terminar.").grid(row=0, column=5, sticky="w", pady=(12, 10))

        self._check(avanzado, "Regla archivos pesados", self.large_file_rule_enabled, self._refresh_option_states, "Si el archivo supera el limite, usa calidad especial para ahorrar peso.").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 12))
        self._field_label(avanzado, "Mayor a KB", "Umbral para aplicar la regla.").grid(row=1, column=1, sticky="e", padx=(0, 8), pady=(0, 12))
        self.large_file_threshold_entry = ttk.Entry(avanzado, textvariable=self.large_file_threshold_kb, width=9)
        self.large_file_threshold_entry.grid(row=1, column=2, sticky="ew", padx=(0, 14), pady=(0, 12))
        self._field_label(avanzado, "Calidad regla", "Calidad usada cuando el archivo supera el umbral.").grid(row=1, column=3, sticky="e", padx=(0, 8), pady=(0, 12))
        self.large_file_quality_spinbox = tk.Spinbox(avanzado, from_=15, to=95, textvariable=self.large_file_quality, width=5, **self._spinbox_style())
        self.large_file_quality_spinbox.grid(row=1, column=4, sticky="w", padx=(0, 14), pady=(0, 12))
        self._button(avanzado, "Exportar ajustes", self.export_settings, "ghost").grid(row=1, column=5, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(avanzado, "Importar ajustes", self.import_settings, "ghost").grid(row=1, column=6, sticky="ew", padx=(0, 8), pady=(0, 12))
        self._button(avanzado, "Guia", self.show_options_guide, "ghost").grid(row=1, column=7, sticky="ew", pady=(0, 12))

        self._field_label(avanzado, "PDF pagina", "Original conserva tamano de imagen; A4/Carta centran cada imagen.").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 12))
        self.pdf_page_combo = ttk.Combobox(avanzado, textvariable=self.pdf_page_size, values=["Original", "A4", "Carta"], state="readonly", width=12)
        self.pdf_page_combo.grid(row=2, column=1, sticky="ew", padx=(0, 14), pady=(0, 12))
        self._check(avanzado, "PDF auto orientacion", self.pdf_auto_orientation, tooltip="Gira pagina A4/Carta a horizontal si la imagen es horizontal.").grid(row=2, column=2, sticky="w", padx=(0, 8), pady=(0, 12))
        self._check(avanzado, "Crear ZIP final", self.create_zip, tooltip="Crea un ZIP con todos los archivos generados.").grid(row=2, column=3, sticky="w", padx=(0, 8), pady=(0, 12))
        self._check(avanzado, "Notificar al terminar", self.notify_on_done, tooltip="Muestra aviso basico de Windows al terminar.").grid(row=2, column=4, sticky="w", pady=(0, 12))

    def _option_tab(self, notebook: ttk.Notebook) -> tk.Frame:
        frame = tk.Frame(notebook, bg=self.colors["surface"], padx=12, pady=2)
        return frame

    def _spinbox_style(self) -> dict:
        return {
            "bg": self.colors["input"],
            "fg": self.colors["text"],
            "disabledbackground": self.colors["surface_soft"],
            "disabledforeground": self.colors["muted"],
            "insertbackground": self.colors["text"],
            "buttonbackground": self.colors["ghost"],
            "highlightbackground": self.colors["line"],
            "highlightcolor": self.colors["primary"],
            "highlightthickness": 1,
            "relief": "solid",
            "bd": 1,
            "font": ("Segoe UI", 9),
        }

    def _card(self, parent) -> tk.Frame:
        return tk.Frame(parent, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["line"])

    def _tooltip(self, widget: tk.Widget, text: str) -> None:
        ToolTip(widget, text)

    def _field_label(self, parent, text: str, tooltip: str | None = None) -> tk.Label:
        label = tk.Label(parent, text=text, bg=self.colors["surface"], fg=self.colors["muted"], font=("Segoe UI", 9, "bold"))
        if tooltip:
            self._tooltip(label, tooltip)
        return label

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

    def _check(self, parent, text: str, variable: tk.BooleanVar, command=None, tooltip: str | None = None) -> tk.Checkbutton:
        check = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            activebackground=self.colors["surface"],
            activeforeground=self.colors["text"],
            selectcolor=self.colors["input"],
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=0,
        )
        if tooltip:
            self._tooltip(check, tooltip)
        return check

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
        self.drop_zone.create_rectangle(10, 10, width - 10, height - 10, outline=self.colors["primary"], width=2, dash=(8, 6))
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
        self._refresh_file_tree(selected)

    def _refresh_file_tree(self, selected: list[Path] | None = None) -> None:
        selected = selected or []
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        for resolved in self._filtered_files():
            metadata = self.metadata_cache.get(resolved)
            if metadata is None:
                metadata = describe_image(resolved)
                self.metadata_cache[resolved] = metadata
            image_format, dimensions, details, weight = metadata
            details = self._details_with_flags(resolved, image_format, details)
            thumbnail = self._thumbnail_for_path(resolved)
            self.file_tree.insert(
                "",
                tk.END,
                iid=str(resolved),
                text="",
                image=thumbnail,
                values=(
                    resolved.name,
                    self.file_status.get(resolved, "Pendiente"),
                    image_format,
                    dimensions,
                    weight,
                    self.file_estimates.get(resolved, "Pendiente"),
                    details,
                    str(resolved.parent),
                ),
            )
        self._refresh_filter_values()
        visible = {Path(item) for item in self.file_tree.get_children()}
        valid_selection = [str(path) for path in selected if path in visible]
        if valid_selection:
            self.file_tree.selection_set(valid_selection)
            self.file_tree.focus(valid_selection[0])
            self.update_preview()
        elif self.file_tree.get_children():
            first = self.file_tree.get_children()[0]
            self.file_tree.selection_set(first)
            self.file_tree.focus(first)
            self.update_preview()

    def _details_with_flags(self, path: Path, image_format: str, details: str) -> str:
        flags: list[str] = []
        if image_format.startswith("RAW"):
            flags.append("RAW")
        if "transparencia" in details:
            flags.append("Transp.")
        if "frames" in details:
            flags.append("Animada")
        if path.exists() and path.stat().st_size >= 5 * 1024 * 1024:
            flags.append("Pesado")
        if "No se pudo" in details or "no soportado" in details.lower():
            flags.append("Revisar")
        return f"{details} | {', '.join(flags)}" if flags else details

    def _filtered_files(self) -> list[Path]:
        status_filter = self.filter_status.get()
        format_filter = self.filter_format.get()
        min_kb = self._filter_number(self.filter_min_kb.get())
        max_kb = self._filter_number(self.filter_max_kb.get())
        search = self.queue_search.get().strip().lower()
        visible: list[Path] = []
        for path in self.files:
            metadata = self.metadata_cache.get(path)
            image_format = metadata[0] if metadata else path.suffix.replace(".", "").upper()
            status = self.file_status.get(path, "Pendiente")
            size_kb = path.stat().st_size / 1024 if path.exists() else 0
            if search and search not in path.name.lower() and search not in str(path.parent).lower():
                continue
            if status_filter != "Todos" and not self._status_matches_filter(status, status_filter):
                continue
            if format_filter != "Todos" and format_filter.upper() not in image_format.upper():
                continue
            if min_kb is not None and size_kb < min_kb:
                continue
            if max_kb is not None and size_kb > max_kb:
                continue
            visible.append(path)
        return self._sort_files(visible)

    def _sort_files(self, files: list[Path]) -> list[Path]:
        mode = self.queue_sort.get()
        if mode == "Nombre":
            return sorted(files, key=lambda path: path.name.lower())
        if mode == "Peso":
            return sorted(files, key=lambda path: path.stat().st_size if path.exists() else 0, reverse=True)
        if mode == "Formato":
            return sorted(files, key=lambda path: (self.metadata_cache.get(path) or ("", "", "", ""))[0])
        if mode == "Estado":
            return sorted(files, key=lambda path: self.file_status.get(path, "Pendiente"))
        if mode == "Tamano":
            def dimensions_key(path: Path) -> int:
                metadata = self.metadata_cache.get(path)
                if not metadata:
                    return 0
                parts = metadata[1].replace(" ", "").split("x")
                try:
                    return int(parts[0]) * int(parts[1])
                except (ValueError, IndexError):
                    return 0

            return sorted(files, key=dimensions_key, reverse=True)
        return files

    def _filter_number(self, value: str) -> float | None:
        value = value.strip().replace(",", ".")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    def _status_matches_filter(self, status: str, status_filter: str) -> bool:
        if status_filter == "Procesando":
            return status.endswith("...") or status in {"PDF"}
        if status_filter == "OK":
            return status in {"OK", "PDF OK"}
        return status.startswith(status_filter)

    def _refresh_filter_values(self) -> None:
        if not hasattr(self, "filter_format_combo"):
            return
        formats = sorted({(self.metadata_cache.get(path) or ("", "", "", ""))[0] for path in self.files if self.metadata_cache.get(path)})
        values = ["Todos", *formats]
        self.filter_format_combo.configure(values=values)
        if self.filter_format.get() not in values:
            self.filter_format.set("Todos")

    def apply_filters(self) -> None:
        selected = [Path(item) for item in self.file_tree.selection()] if hasattr(self, "file_tree") else []
        self._refresh_file_tree(selected)
        self.status.set(f"{len(self._filtered_files())} de {len(self.files)} imagen(es) visibles.")

    def clear_filters(self) -> None:
        self.filter_status.set("Todos")
        self.filter_format.set("Todos")
        self.filter_min_kb.set("")
        self.filter_max_kb.set("")
        self.queue_search.set("")
        self.queue_sort.set("Orden agregado")
        self.apply_filters()

    def _thumbnail_for_path(self, path: Path) -> ImageTk.PhotoImage:
        thumbnail = self.thumbnail_images.get(path)
        if thumbnail is not None:
            return thumbnail

        canvas = Image.new("RGBA", (46, 46), (0, 0, 0, 0))
        try:
            if is_raw_image(path):
                image = load_raw_image(path)
            else:
                with Image.open(path) as opened:
                    opened.draft("RGB", (46, 46))
                    image = ImageOps.exif_transpose(opened).convert("RGBA")
            image.thumbnail((42, 42), Image.Resampling.LANCZOS)
            canvas.alpha_composite(image.convert("RGBA"), ((46 - image.width) // 2, (46 - image.height) // 2))
        except Exception:
            draw = ImageDraw.Draw(canvas)
            draw.rounded_rectangle((3, 3, 43, 43), radius=8, fill=self.colors["surface_soft"], outline=self.colors["line"])
            label = path.suffix.replace(".", "").upper()[:3] or "IMG"
            draw.text((23, 23), label, anchor="mm", fill=self.colors["muted"])

        thumbnail = ImageTk.PhotoImage(canvas)
        self.thumbnail_images[path] = thumbnail
        return thumbnail

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
        self.status.set("Escaneando y autodetectando imagenes...")
        thread = threading.Thread(target=self._expand_and_add_paths_worker, args=(paths,), daemon=True)
        thread.start()

    def _expand_and_add_paths_worker(self, paths: list[Path]) -> None:
        expanded_paths: list[tuple[Path, Path | None]] = []
        for path in paths:
            if path.is_dir():
                try:
                    root = path.resolve()
                except OSError:
                    root = path
                expanded_paths.extend((image_path, root) for image_path in self._iter_images(path))
            else:
                expanded_paths.append((path, None))
        self._scan_paths(expanded_paths)

    def _add_paths(self, paths) -> None:
        self.status.set("Leyendo y autodetectando metadatos...")
        thread = threading.Thread(target=self._scan_paths, args=([(Path(path), None) for path in paths],), daemon=True)
        thread.start()

    def _scan_paths(self, paths: list[tuple[Path, Path | None]]) -> None:
        existing = {path.resolve() for path in self.files}
        existing_signatures: set[str] = set()
        for current in list(self.files):
            try:
                signature = self.file_signatures.get(current) or file_signature(current)
            except OSError:
                continue
            self.file_signatures[current] = signature
            existing_signatures.add(signature)
        entries: list[tuple[Path, tuple[str, str, str, str], str, Path | None]] = []
        added = 0
        rejected = 0
        duplicates = 0

        for path, root in paths:
            try:
                resolved = path.resolve()
            except OSError:
                rejected += 1
                continue
            if not resolved.is_file() or not is_supported_image(resolved):
                rejected += 1
                continue
            if resolved in existing:
                duplicates += 1
                continue
            try:
                signature = file_signature(resolved)
            except OSError:
                rejected += 1
                continue
            if signature in existing_signatures:
                self.duplicate_signatures.add(signature)
                duplicates += 1
                continue

            metadata = self.metadata_cache.get(resolved)
            if metadata is None:
                metadata = describe_image(resolved)
                self.metadata_cache[resolved] = metadata
            existing.add(resolved)
            existing_signatures.add(signature)
            entries.append((resolved, metadata, signature, root.resolve() if root is not None else resolved.parent))
            added += 1

        self.after(0, lambda: self._insert_scanned_paths(entries, added, rejected, duplicates))

    def _insert_scanned_paths(
        self,
        entries: list[tuple[Path, tuple[str, str, str, str], str, Path | None]],
        added: int,
        rejected: int,
        duplicates: int,
    ) -> None:
        existing = set(self.files)
        for resolved, metadata, signature, root in entries:
            if resolved in existing:
                continue
            self.files.append(resolved)
            self.file_status[resolved] = "Pendiente"
            self.file_estimates[resolved] = "Pendiente"
            self.file_signatures[resolved] = signature
            if root is not None:
                self.file_roots[resolved] = root
            existing.add(resolved)
        self._refresh_file_tree()
        self._queue_file_estimates(250)

        self.status.set(f"{len(self.files)} imagen(es) listas. Agregadas: {added}. Duplicadas: {duplicates}. Rechazadas: {rejected}.")
        if added and self.file_tree.get_children() and not self.file_tree.selection():
            first = self.file_tree.get_children()[0]
            self.file_tree.selection_set(first)
            self.file_tree.focus(first)
            self.update_preview()

    def remove_selected(self) -> None:
        if self.conversion_running:
            messagebox.showinfo(APP_NAME, "Espera a que termine la conversion antes de modificar la cola.")
            return
        selected = list(self.file_tree.selection())
        selected_paths = {Path(item) for item in selected}
        for item in selected:
            self.file_tree.delete(item)
        self.files = [path for path in self.files if path not in selected_paths]
        for path in selected_paths:
            self.file_status.pop(path, None)
            self.file_estimates.pop(path, None)
            self.file_signatures.pop(path, None)
            self.file_roots.pop(path, None)
            self.thumbnail_images.pop(path, None)
            self.metadata_cache.pop(path, None)
        self._refresh_file_tree()
        if not self.file_tree.selection():
            self.preview_canvas.delete("all")
            self.preview_compare_payload = None
            self.preview_info.set("Selecciona una imagen para ver la vista previa.")
            self.preview_estimate_request_id += 1
            self.file_estimate_request_id += 1
            self.preview_estimate_info.set("Peso estimado de salida: selecciona una imagen.")
            self.output_name_preview.set("Salida: selecciona una imagen.")
        if not self.files:
            self.batch_summary_info.set("Ahorro total: usa Estimar lote para calcular el lote completo.")
        self.status.set(f"{len(self.files)} imagen(es) listas.")

    def select_error_files(self) -> None:
        matches = [
            str(path)
            for path in self.files
            if hasattr(self, "file_tree")
            and self.file_tree.exists(str(path))
            and ("Error" in self.file_status.get(path, "") or path in self.last_failed_files)
        ]
        if matches:
            self.file_tree.selection_set(matches)
            self.file_tree.focus(matches[0])
            self.status.set(f"{len(matches)} archivo(s) con error seleccionados.")
        else:
            self.status.set("No hay archivos con error visibles.")

    def remove_duplicate_files(self) -> None:
        seen: set[str] = set()
        duplicate_paths: set[Path] = set()
        for path in self.files:
            signature = self.file_signatures.get(path)
            if signature is None:
                try:
                    signature = file_signature(path)
                except OSError:
                    continue
                self.file_signatures[path] = signature
            if signature in seen:
                duplicate_paths.add(path)
            else:
                seen.add(signature)
        if not duplicate_paths:
            self.status.set("No hay duplicados en la cola.")
            return
        self.files = [path for path in self.files if path not in duplicate_paths]
        for path in duplicate_paths:
            self.file_status.pop(path, None)
            self.file_estimates.pop(path, None)
            self.file_signatures.pop(path, None)
            self.file_roots.pop(path, None)
            self.thumbnail_images.pop(path, None)
            self.metadata_cache.pop(path, None)
        self._refresh_file_tree()
        self.status.set(f"Duplicados quitados: {len(duplicate_paths)}.")

    def show_output_plan(self) -> None:
        if not self.files:
            messagebox.showinfo(APP_NAME, "Agrega imagenes para ver las salidas previstas.")
            return
        options = self._read_options()
        if options is None:
            return
        files = self._filtered_files() or list(self.files)
        formats = list(options.output_formats)
        reserved_outputs: set[Path] = set()
        lines = [
            f"Archivos visibles: {len(files)}",
            f"Carpeta: {options.output_dir}",
            f"Formatos: {', '.join(options.output_formats)}",
            "",
        ]
        if options.combine_pdf and "PDF" in formats:
            destination = options.output_dir / "imagenes_convertidas.pdf"
            if not options.overwrite:
                counter = 1
                while destination.exists() or destination in reserved_outputs:
                    destination = options.output_dir / f"imagenes_convertidas_{counter}.pdf"
                    counter += 1
            reserved_outputs.add(destination)
            state = "reemplaza" if destination.exists() and options.overwrite else "nuevo"
            lines.append(f"PDF unico -> {destination} [{state}]")
            formats = [fmt for fmt in formats if fmt != "PDF"]

        limit = 220
        total_lines = 0
        for index, source in enumerate(files, start=1):
            for output_format in formats:
                format_options = self._effective_format_options(options, source, output_format)
                destination = build_output_path(source, options.output_dir, format_options, index, reserved_outputs, self.file_roots.get(source))
                state = "reemplaza" if destination.exists() and options.overwrite else "nuevo"
                if total_lines < limit:
                    lines.append(f"{source.name} -> {destination} [{state}]")
                total_lines += 1
        if total_lines > limit:
            lines.append("")
            lines.append(f"... {total_lines - limit} salida(s) mas no mostradas.")
        self._show_text_window("Vista de salidas", "\n".join(lines))

    def _show_text_window(self, title: str, text: str) -> None:
        window = tk.Toplevel(self)
        window.title(title)
        window.geometry("900x560")
        window.configure(bg=self.colors["surface"])
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        text_widget = tk.Text(
            window,
            wrap="none",
            bg=self.colors["surface_soft"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            relief="flat",
            padx=12,
            pady=12,
            font=("Consolas", 10),
        )
        text_widget.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        text_widget.insert("1.0", text)
        text_widget.configure(state="disabled")
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=text_widget.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=14)
        text_widget.configure(yscrollcommand=scrollbar.set)

    def save_session(self, silent: bool = False) -> None:
        payload = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "files": [
                {"path": str(path), "root": str(self.file_roots.get(path)) if self.file_roots.get(path) else None}
                for path in self.files
                if path.exists()
            ],
        }
        try:
            self._write_json_atomic(SESSION_PATH, payload)
            if not silent:
                self.status.set(f"Sesion guardada: {len(payload['files'])} archivo(s).")
        except OSError as exc:
            if not silent:
                messagebox.showerror(APP_NAME, f"No se pudo guardar la sesion:\n{exc}")
            append_log(f"No se pudo guardar session.json: {exc}")

    def restore_session(self, silent: bool = False) -> None:
        if self.conversion_running:
            messagebox.showinfo(APP_NAME, "Espera a que termine la conversion antes de restaurar la sesion.")
            return
        if not SESSION_PATH.exists():
            if not silent:
                self.status.set("No hay sesion guardada.")
            return
        try:
            payload = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror(APP_NAME, f"No se pudo leer la sesion:\n{exc}")
            return

        entries: list[tuple[Path, Path | None]] = []
        for item in payload.get("files", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            path = Path(str(item.get("path", ""))).expanduser()
            if not path.exists():
                continue
            root_value = item.get("root")
            root = Path(str(root_value)).expanduser() if root_value else path.parent
            entries.append((path, root))
        if not entries:
            if not silent:
                self.status.set("La sesion guardada no tiene archivos disponibles.")
            return

        self._clear_queue_state()
        self.status.set("Restaurando sesion...")
        thread = threading.Thread(target=self._scan_paths, args=(entries,), daemon=True)
        thread.start()

    def _clear_queue_state(self) -> None:
        self.files.clear()
        self.file_status.clear()
        self.file_estimates.clear()
        self.file_signatures.clear()
        self.file_roots.clear()
        self.thumbnail_images.clear()
        self.metadata_cache.clear()
        self.duplicate_signatures.clear()
        if hasattr(self, "file_tree"):
            for item in self.file_tree.get_children():
                self.file_tree.delete(item)
        if hasattr(self, "preview_canvas"):
            self.preview_canvas.delete("all")
        self.preview_compare_payload = None
        self.preview_info.set("Selecciona una imagen para ver la vista previa.")
        self.preview_estimate_request_id += 1
        self.file_estimate_request_id += 1
        self.preview_estimate_info.set("Peso estimado de salida: selecciona una imagen.")
        self.output_name_preview.set("Salida: selecciona una imagen.")
        self.batch_summary_info.set("Ahorro total: usa Estimar lote para calcular el lote completo.")

    def clear_files(self) -> None:
        if self.conversion_running:
            messagebox.showinfo(APP_NAME, "Espera a que termine la conversion antes de limpiar la cola.")
            return
        self._clear_queue_state()
        self.status.set("Lista limpia.")

    def _focus_is_text_input(self) -> bool:
        focus = self.focus_get()
        return bool(focus and focus.winfo_class() in {"Entry", "TEntry", "Spinbox", "TSpinbox", "Text"})

    def _delete_shortcut(self, _event=None):
        if self._focus_is_text_input():
            return None
        self.remove_selected()
        return "break"

    def _select_all_files(self, _event=None):
        if self._focus_is_text_input():
            return None
        if hasattr(self, "file_tree"):
            self.file_tree.selection_set(self.file_tree.get_children())
        return "break"

    def move_selected(self, direction: int) -> None:
        if self.conversion_running:
            messagebox.showinfo(APP_NAME, "Espera a que termine la conversion antes de reordenar.")
            return
        selected = [Path(item) for item in self.file_tree.selection()]
        if not selected:
            return
        ordered = list(self.files)
        if direction > 0:
            indexes = range(len(ordered) - 2, -1, -1)
        else:
            indexes = range(1, len(ordered))
        selected_set = set(selected)
        for index in indexes:
            swap_with = index + direction
            if ordered[index] in selected_set and ordered[swap_with] not in selected_set:
                ordered[index], ordered[swap_with] = ordered[swap_with], ordered[index]
        self.files = ordered
        self._restore_file_tree(selected)
        self.status.set("Orden de cola actualizado.")

    def _set_file_status(self, path: Path, status: str) -> None:
        self.file_status[path] = status
        item = str(path)
        if hasattr(self, "file_tree") and self.file_tree.exists(item):
            self.file_tree.set(item, "status", status)

    def _set_file_estimate(self, request_id: int, path: Path, estimate: str) -> None:
        if request_id >= 0 and request_id != self.file_estimate_request_id:
            return
        self.file_estimates[path] = estimate
        item = str(path)
        if hasattr(self, "file_tree") and self.file_tree.exists(item):
            self.file_tree.set(item, "estimate", estimate)

    def _reset_file_statuses(self) -> None:
        for path in self.files:
            self._set_file_status(path, "Pendiente")

    def export_history(self) -> None:
        if not self.history_entries:
            messagebox.showinfo(APP_NAME, "No hay historial para exportar.")
            return
        destination = filedialog.asksaveasfilename(
            title="Exportar historial",
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Todos los archivos", "*.*")],
        )
        if not destination:
            return
        try:
            Path(destination).write_text("\n".join(self.history_entries) + "\n", encoding="utf-8")
            self.status.set(f"Historial exportado: {destination}")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudo exportar el historial:\n{exc}")

    def clear_history(self) -> None:
        self.history_entries.clear()
        if hasattr(self, "history_list"):
            self.history_list.delete(0, tk.END)
        self.status.set("Historial limpio.")

    def open_log_file(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            LOG_PATH.touch(exist_ok=True)
            os.startfile(LOG_PATH)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudo abrir el log:\n{exc}")

    def _context_menu_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}" "%1"'
        return f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}" "%1"'

    def _context_menu_icon(self) -> str:
        if getattr(sys, "frozen", False):
            return str(Path(sys.executable).resolve())
        return str(LOGO_ICO if LOGO_ICO.exists() else Path(__file__).resolve())

    def _delete_registry_tree(self, winreg_module, root, key_path: str) -> None:
        try:
            with winreg_module.OpenKey(root, key_path, 0, winreg_module.KEY_READ | winreg_module.KEY_WRITE) as key:
                while True:
                    try:
                        child = winreg_module.EnumKey(key, 0)
                    except OSError:
                        break
                    self._delete_registry_tree(winreg_module, root, f"{key_path}\\{child}")
            winreg_module.DeleteKey(root, key_path)
        except FileNotFoundError:
            pass

    def is_context_menu_installed(self) -> bool:
        if os.name != "nt":
            return False
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONTEXT_MENU_KEYS[0] + r"\command") as key:
                command, _kind = winreg.QueryValueEx(key, "")
            return bool(command)
        except (OSError, ImportError):
            return False

    def install_context_menu(self) -> None:
        if os.name != "nt":
            messagebox.showinfo(APP_NAME, "El menu contextual solo esta disponible en Windows.")
            return
        try:
            import winreg

            command = self._context_menu_command()
            icon = self._context_menu_icon()
            for key_path in CONTEXT_MENU_KEYS:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as menu_key:
                    winreg.SetValueEx(menu_key, "", 0, winreg.REG_SZ, f"Convertir con {APP_NAME}")
                    winreg.SetValueEx(menu_key, "Icon", 0, winreg.REG_SZ, icon)
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\command") as command_key:
                    winreg.SetValueEx(command_key, "", 0, winreg.REG_SZ, command)
            self.status.set("Menu contextual instalado.")
            messagebox.showinfo(APP_NAME, "Menu contextual instalado. Ahora puedes usar clic derecho > Convertir con Converter.")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudo instalar el menu contextual:\n{exc}")

    def remove_context_menu(self) -> None:
        if os.name != "nt":
            return
        try:
            import winreg

            for key_path in CONTEXT_MENU_KEYS:
                self._delete_registry_tree(winreg, winreg.HKEY_CURRENT_USER, key_path)
            self.status.set("Menu contextual quitado.")
            messagebox.showinfo(APP_NAME, "Menu contextual quitado.")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudo quitar el menu contextual:\n{exc}")

    def configure_context_menu(self) -> None:
        if self.is_context_menu_installed():
            if messagebox.askyesno(APP_NAME, "El menu contextual ya esta instalado.\n\nQuieres quitarlo?"):
                self.remove_context_menu()
            return
        if messagebox.askyesno(APP_NAME, "Instalar clic derecho > Convertir con Converter para archivos y carpetas?"):
            self.install_context_menu()

    def show_options_guide(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            "Guia rapida de salida\n\n"
            "Formato: tipo principal que se va a generar.\n"
            "RAW: se importa como entrada de camara y se exporta a formatos normales; no aparece como salida.\n"
            "SVG: salida vectorial simplificada, mejor para logos e ilustraciones que para fotos complejas.\n"
            "Otros formatos: salidas adicionales, por ejemplo PNG,JPG.\n"
            "Est. salida: calcula el peso aproximado por archivo en la cola. Para PDF unico se muestra como lote.\n"
            "Peso estimado: aparece en la vista previa y cambia al ajustar formato, calidad o tamano.\n"
            "Vista salidas: muestra donde quedaria cada archivo antes de convertir.\n"
            "Buscar/Orden: encuentra archivos en la cola y reordena por nombre, peso, formato, estado o tamano.\n"
            "Guardar sesion: recuerda la cola actual para continuar despues.\n"
            "Quitar fondo: elimina fondos conectados a los bordes; ajusta Fuerza fondo si quedan halos o borra de mas.\n"
            "Brillo/Contraste/Saturacion: ajustes visuales ligeros aplicados a todo el lote.\n"
            "Producto tienda: genera PNG, WEBP y JPG a 1200 px, con fondo blanco para formatos sin transparencia.\n"
            "Un solo PDF: une todas las imagenes en un PDF; usa el orden de la cola.\n"
            "PDF pagina: Original conserva tamano; A4/Carta centra cada imagen en una hoja.\n"
            "Crear ZIP final: empaqueta los archivos generados al terminar.\n"
            "Cambiar tamano: activa Ancho/Alto en pixeles.\n"
            "Color fondo: rellena transparencias cuando el formato no las soporta.\n"
            "Nombrado: controla nombres nuevos, numerados o con prefijo/sufijo.\n"
            "Peso max KB: intenta limitar el peso final por archivo.\n"
            "Tareas: conversiones paralelas; 2 a 4 suele ser buen valor.\n"
            "Quitar EXIF: elimina metadatos privados como camara, fecha o GPS.\n"
            "Menu Windows: agrega o quita la opcion de clic derecho para abrir archivos/carpetas en Converter.\n"
            "Importar/Exportar perfil: mueve tus presets entre equipos.",
        )

    def _bind_output_option_traces(self) -> None:
        variables = (
            self.output_format,
            self.extra_formats,
            self.quality,
            self.resize_enabled,
            self.resize_width,
            self.resize_height,
            self.keep_aspect,
            self.background_hex,
            self.lossless,
            self.keep_folder_structure,
            self.use_output_subfolder,
            self.combine_pdf,
            self.target_size_enabled,
            self.target_size_kb,
            self.strip_metadata,
            self.remove_background,
            self.remove_background_tolerance,
            self.remove_background_feather,
            self.rotate_degrees,
            self.flip_horizontal,
            self.flip_vertical,
            self.crop_enabled,
            self.crop_left,
            self.crop_top,
            self.crop_right,
            self.crop_bottom,
            self.square_canvas,
            self.canvas_size,
            self.canvas_transparent,
            self.brightness,
            self.contrast,
            self.saturation,
            self.naming_mode,
            self.naming_template,
            self.prefix,
            self.suffix,
            self.large_file_rule_enabled,
            self.large_file_threshold_kb,
            self.large_file_quality,
            self.pdf_page_size,
            self.pdf_auto_orientation,
            self.create_zip,
            self.notify_on_done,
        )
        for variable in variables:
            variable.trace_add("write", self._handle_output_option_change)

    def _handle_output_option_change(self, *_args) -> None:
        if hasattr(self, "quality_label"):
            self._refresh_option_states()
        self._queue_selected_output_estimate()
        self._queue_file_estimates()
        self._update_output_name_preview()

    def _queue_selected_output_estimate(self, delay_ms: int = 300) -> None:
        if not hasattr(self, "preview_estimate_info"):
            return
        if self.preview_estimate_after_id is not None:
            try:
                self.after_cancel(self.preview_estimate_after_id)
            except tk.TclError:
                pass
            self.preview_estimate_after_id = None
        self.preview_estimate_after_id = self.after(delay_ms, self._start_selected_output_estimate)

    def _start_selected_output_estimate(self) -> None:
        self.preview_estimate_after_id = None
        selected = self.file_tree.selection() if hasattr(self, "file_tree") else ()
        if not selected:
            self.preview_estimate_info.set("Peso estimado de salida: selecciona una imagen.")
            return

        options = self._read_options(show_errors=False)
        if options is None:
            self.preview_estimate_request_id += 1
            self.preview_estimate_info.set("Peso estimado de salida: completa opciones validas para calcular.")
            return

        path = Path(selected[0])
        self.preview_estimate_request_id += 1
        request_id = self.preview_estimate_request_id
        self.preview_estimate_info.set("Peso estimado de salida: calculando...")
        thread = threading.Thread(target=self._selected_output_estimate_worker, args=(request_id, path, options), daemon=True)
        thread.start()

    def _selected_output_estimate_worker(self, request_id: int, path: Path, options: ConversionOptions) -> None:
        try:
            input_bytes = path.stat().st_size
            estimates: list[tuple[str, int]] = []
            for output_format in options.output_formats:
                format_options = self._effective_format_options(options, path, output_format)
                estimates.append((output_format, estimate_final_output_size(path, format_options)))
            text = format_output_estimate_summary(input_bytes, estimates)
            if options.combine_pdf and "PDF" in options.output_formats:
                text += " | PDF unico: usa Estimar lote para el total real."
        except Exception as exc:
            text = f"Peso estimado de salida: no se pudo calcular ({exc})."
        self.after(0, lambda: self._finish_selected_output_estimate(request_id, path, text))

    def _finish_selected_output_estimate(self, request_id: int, path: Path, text: str) -> None:
        if request_id != self.preview_estimate_request_id:
            return
        selected = self.file_tree.selection()
        if not selected or Path(selected[0]) != path:
            return
        self.preview_estimate_info.set(text)

    def _update_output_name_preview(self) -> None:
        if not hasattr(self, "output_name_preview") or not hasattr(self, "file_tree"):
            return
        selected = self.file_tree.selection()
        if not selected:
            self.output_name_preview.set("Salida: selecciona una imagen.")
            return
        options = self._read_options(show_errors=False)
        if options is None:
            self.output_name_preview.set("Salida: completa opciones validas.")
            return
        path = Path(selected[0])
        try:
            output_path = build_output_path(path, options.output_dir, options, 1, source_root=self.file_roots.get(path))
            suffix = " + extras" if len(options.output_formats) > 1 else ""
            self.output_name_preview.set(f"Salida prevista: {output_path}{suffix}")
        except Exception:
            self.output_name_preview.set("Salida: no disponible.")

    def _queue_file_estimates(self, delay_ms: int = 650) -> None:
        if not hasattr(self, "file_tree") or not self.files:
            return
        if self.file_estimate_after_id is not None:
            try:
                self.after_cancel(self.file_estimate_after_id)
            except tk.TclError:
                pass
            self.file_estimate_after_id = None
        self.file_estimate_after_id = self.after(delay_ms, self._start_file_estimates)

    def _estimate_cache_key(self, path: Path, options: ConversionOptions) -> tuple:
        stat = path.stat()
        return (
            path,
            stat.st_size,
            stat.st_mtime_ns,
            options.output_formats,
            options.quality,
            options.resize_enabled,
            options.width,
            options.height,
            options.keep_aspect,
            options.background,
            options.combine_pdf,
            options.target_size_enabled,
            options.target_size_kb,
            options.strip_metadata,
            options.lossless,
            options.remove_background,
            options.remove_background_tolerance,
            options.remove_background_feather,
            options.rotate_degrees,
            options.flip_horizontal,
            options.flip_vertical,
            options.crop_enabled,
            options.crop_left,
            options.crop_top,
            options.crop_right,
            options.crop_bottom,
            options.square_canvas,
            options.canvas_size,
            options.canvas_transparent,
            options.brightness,
            options.contrast,
            options.saturation,
            options.large_file_rule_enabled,
            options.large_file_threshold_kb,
            options.large_file_quality,
            options.pdf_page_size,
            options.pdf_auto_orientation,
        )

    def _start_file_estimates(self) -> None:
        self.file_estimate_after_id = None
        files = list(self.files)
        if not files:
            return

        self.file_estimate_request_id += 1
        request_id = self.file_estimate_request_id
        options = self._read_options(show_errors=False)
        if options is None:
            for path in files:
                self._set_file_estimate(request_id, path, "Opciones")
            return

        for path in files:
            self._set_file_estimate(request_id, path, "Calculando...")
        thread = threading.Thread(target=self._file_estimates_worker, args=(request_id, files, options), daemon=True)
        thread.start()

    def _file_estimates_worker(self, request_id: int, files: list[Path], options: ConversionOptions) -> None:
        for path in files:
            if request_id != self.file_estimate_request_id:
                return
            try:
                key = self._estimate_cache_key(path, options)
                estimate = self.file_estimate_cache.get(key)
                if estimate is None:
                    formats = [fmt for fmt in options.output_formats if not (options.combine_pdf and fmt == "PDF")]
                    if not formats:
                        estimate = "PDF lote"
                    else:
                        estimates: list[tuple[str, int]] = []
                        for output_format in formats:
                            format_options = self._effective_format_options(options, path, output_format)
                            estimates.append((output_format, estimate_final_output_size(path, format_options)))
                        estimate = format_estimate_cell(estimates)
                        if options.combine_pdf and "PDF" in options.output_formats:
                            estimate = f"{estimate} + PDF"
                    self.file_estimate_cache[key] = estimate
            except Exception:
                estimate = "No disp."
            self.after(0, lambda path=path, estimate=estimate: self._set_file_estimate(request_id, path, estimate))

    def change_preview_zoom(self, delta: float) -> None:
        zoom = max(0.5, min(2.0, round(float(self.preview_zoom.get()) + delta, 2)))
        self.preview_zoom.set(zoom)
        if self.preview_compare_payload is not None:
            self._draw_comparison(*self.preview_compare_payload)

    def _draw_checkerboard(self, x: int, y: int, width: int, height: int, square: int = 10) -> None:
        light = "#f8fafc" if not self.dark_mode.get() else "#1f2937"
        dark = "#dbe4ef" if not self.dark_mode.get() else "#334155"
        for row in range(y, y + height, square):
            for column in range(x, x + width, square):
                color = light if ((row - y) // square + (column - x) // square) % 2 == 0 else dark
                self.preview_canvas.create_rectangle(
                    column,
                    row,
                    min(column + square, x + width),
                    min(row + square, y + height),
                    outline=color,
                    fill=color,
                )
        self.preview_canvas.create_rectangle(x, y, x + width, y + height, outline=self.colors["line"])

    def _draw_single_preview_image(self, image: Image.Image) -> None:
        self.preview_canvas.delete("all")
        width = max(self.preview_canvas.winfo_width(), 410)
        height = int(self.preview_canvas.cget("height"))
        x = max(0, (width - image.width) // 2)
        y = max(0, (height - image.height) // 2)
        self._draw_checkerboard(x, y, image.width, image.height)
        self.preview_image = ImageTk.PhotoImage(image)
        self.preview_canvas.create_image(width // 2, height // 2, image=self.preview_image, anchor="center")

    def _scaled_preview_image(self, image: Image.Image, max_size: int) -> Image.Image:
        scaled = image.copy()
        scaled.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return scaled

    def _draw_comparison(
        self,
        path: Path,
        original: Image.Image,
        output: Image.Image,
        original_size: int,
        estimated_size: int,
        output_format: str,
    ) -> None:
        self.preview_canvas.delete("all")
        width = max(self.preview_canvas.winfo_width(), 410)
        height = int(self.preview_canvas.cget("height"))
        left_x = width // 4
        right_x = width * 3 // 4
        max_size = int(min(width / 2 - 28, height - 72) * float(self.preview_zoom.get()))
        max_size = max(64, min(max_size, height - 56))
        original_scaled = self._scaled_preview_image(original, max_size)
        output_scaled = self._scaled_preview_image(output, max_size)
        top = 46
        available_height = max(1, height - top - 14)

        self.preview_canvas.create_text(left_x, 18, text="Original", fill=self.colors["muted"], font=("Segoe UI", 9, "bold"))
        self.preview_canvas.create_text(right_x, 18, text=f"Salida x{self.preview_zoom.get():.2g}", fill=self.colors["primary"], font=("Segoe UI", 9, "bold"))

        self.preview_images = []
        for center_x, image in ((left_x, original_scaled), (right_x, output_scaled)):
            x = int(center_x - image.width / 2)
            y = int(top + (available_height - image.height) / 2)
            self._draw_checkerboard(x, y, image.width, image.height)
            photo = ImageTk.PhotoImage(image)
            self.preview_images.append(photo)
            self.preview_canvas.create_image(center_x, y + image.height // 2, image=photo, anchor="center")

        self.preview_info.set(f"{path.name} | {format_conversion_summary(original_size, estimated_size)} | {output_format}")

    def update_preview(self, _event=None) -> None:
        selected = self.file_tree.selection()
        if not selected:
            return
        path = Path(selected[0])
        self.preview_compare_payload = None
        self.preview_canvas.delete("all")
        try:
            if is_raw_image(path):
                image = load_raw_image(path)
            else:
                with Image.open(path) as opened:
                    opened.draft("RGB", (410, 270))
                    image = ImageOps.exif_transpose(opened)
            image.thumbnail((410, 270), Image.Resampling.LANCZOS)
            preview = image.convert("RGBA")
            self._draw_single_preview_image(preview)
            metadata = self.metadata_cache.get(path)
            if metadata is None:
                metadata = describe_image(path)
                self.metadata_cache[path] = metadata
            image_format, dimensions, details, weight = metadata
            details = self._details_with_flags(path, image_format, details)
            self.preview_info.set(f"{path.name} | {image_format} | {dimensions} | {weight} | {details}")
            self._queue_selected_output_estimate(120)
            self._update_output_name_preview()
        except Exception as exc:
            self.preview_info.set(f"No se pudo previsualizar: {exc}")
            self.preview_estimate_info.set("Peso estimado de salida: no disponible para esta imagen.")

    def choose_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona carpeta de salida")
        if folder:
            self.output_dir.set(folder)

    def open_output_dir(self) -> None:
        options = self._read_options(show_errors=False)
        output_dir = options.output_dir if options is not None else Path(self.output_dir.get()).expanduser()
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
        self.preview_request_id += 1
        request_id = self.preview_request_id
        self.preview_info.set("Generando comparacion...")
        thread = threading.Thread(target=self._preview_output_worker, args=(request_id, path, options), daemon=True)
        thread.start()

    def _preview_output_worker(self, request_id: int, path: Path, options: ConversionOptions) -> None:
        try:
            if is_raw_image(path):
                original = load_raw_image(path)
            else:
                with Image.open(path) as image:
                    image.draft("RGB", (360, 360))
                    original = ImageOps.exif_transpose(image)
            original.thumbnail((360, 360), Image.Resampling.LANCZOS)
            original = original.convert("RGBA")
            output = converted_first_frame(path, options).convert("RGBA")
            output.thumbnail((360, 360), Image.Resampling.LANCZOS)
            original_size = path.stat().st_size
            estimated_size = estimate_final_output_size(path, options)
            self.after(0, lambda: self._finish_preview_output(request_id, path, original, output, original_size, estimated_size, options.output_format))
        except Exception as exc:
            error = str(exc)
            self.after(0, lambda: messagebox.showerror(APP_NAME, f"No se pudo generar la comparacion:\n{error}"))
            self._set_status("No se pudo generar la comparacion.")

    def _finish_preview_output(
        self,
        request_id: int,
        path: Path,
        original: Image.Image,
        output: Image.Image,
        original_size: int,
        estimated_size: int,
        output_format: str,
    ) -> None:
        if request_id != self.preview_request_id:
            return
        if not self.file_tree.selection() or Path(self.file_tree.selection()[0]) != path:
            return

        self.preview_compare_payload = (path, original, output, original_size, estimated_size, output_format)
        self._draw_comparison(path, original, output, original_size, estimated_size, output_format)

    def estimate_batch_size(self) -> None:
        if self.conversion_running:
            messagebox.showinfo(APP_NAME, "Espera a que termine la conversion antes de estimar.")
            return
        if not self.files:
            messagebox.showinfo(APP_NAME, "Agrega imagenes para estimar el lote.")
            return
        options = self._read_options()
        if options is None:
            return
        files = list(self.files)
        self.status.set("Estimando peso de salida...")
        self.progress.set(0)
        thread = threading.Thread(target=self._estimate_batch_worker, args=(files, options), daemon=True)
        thread.start()

    def _estimate_batch_worker(self, files: list[Path], options: ConversionOptions) -> None:
        input_bytes = sum(path.stat().st_size for path in files if path.exists())
        output_bytes = 0
        errors: list[str] = []
        formats = list(options.output_formats)
        total_jobs = len(files) * len(formats)
        completed = 0

        try:
            if options.combine_pdf and "PDF" in formats:
                with tempfile.TemporaryDirectory() as tmp:
                    destination = Path(tmp) / "estimate.pdf"
                    combine_images_to_pdf(files, destination, replace(options, output_format="PDF", output_formats=("PDF",)))
                    output_bytes += destination.stat().st_size
                completed += len(files)
                formats = [fmt for fmt in formats if fmt != "PDF"]
                total_jobs = max(1, len(files) * len(formats) + completed)
                self._set_progress(completed / total_jobs * 100)

            for source in files:
                for output_format in formats:
                    try:
                        format_options = self._effective_format_options(options, source, output_format)
                        output_bytes += estimate_final_output_size(source, format_options)
                    except Exception as exc:
                        errors.append(f"{source.name} ({output_format}): {exc}")
                    completed += 1
                    if total_jobs:
                        self._set_progress(completed / total_jobs * 100)
        except Exception as exc:
            errors.append(str(exc))

        summary = format_conversion_summary(input_bytes, output_bytes)

        def notify() -> None:
            self.progress.set(0)
            if errors:
                self.status.set(f"Estimacion lista con {len(errors)} error(es). {summary}")
                self.batch_summary_info.set(f"Ahorro total estimado: {summary}")
                messagebox.showwarning(APP_NAME, "Estimacion terminada con errores:\n\n" + "\n".join(errors[:10]))
            else:
                self.status.set(f"Estimacion lista. {summary}")
                self.batch_summary_info.set(f"Ahorro total estimado: {summary}")
                messagebox.showinfo(APP_NAME, f"Estimacion del lote:\n{summary}")

        self.after(0, notify)

    def cancel_conversion(self) -> None:
        if not self.conversion_running:
            return
        if not messagebox.askyesno(APP_NAME, "Cancelar la conversion actual?"):
            return
        self.cancel_event.set()
        self.pause_event.clear()
        self.status.set("Cancelando conversion...")

    def _load_settings(self) -> dict:
        try:
            if SETTINGS_PATH.exists():
                payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            append_log("No se pudo cargar settings.json")
        return {}

    def _write_json_atomic(self, path: Path, payload: dict) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _apply_settings(self, data: dict) -> None:
        if not data:
            return
        self.output_dir.set(data.get("output_dir", self.output_dir.get()))
        self.output_format.set(data.get("output_format", self.output_format.get()))
        self.extra_formats.set(data.get("extra_formats", self.extra_formats.get()))
        self.quality.set(data.get("quality", self.quality.get()))
        self.resize_enabled.set(data.get("resize_enabled", self.resize_enabled.get()))
        self.resize_width.set(data.get("resize_width", self.resize_width.get()))
        self.resize_height.set(data.get("resize_height", self.resize_height.get()))
        self.keep_aspect.set(data.get("keep_aspect", self.keep_aspect.get()))
        self.background_hex.set(data.get("background_hex", self.background_hex.get()))
        self.naming_mode.set(data.get("naming_mode", self.naming_mode.get()))
        self.prefix.set(data.get("prefix", self.prefix.get()))
        self.suffix.set(data.get("suffix", self.suffix.get()))
        self.naming_template.set(data.get("naming_template", self.naming_template.get()))
        self.overwrite.set(data.get("overwrite", self.overwrite.get()))
        self.combine_pdf.set(data.get("combine_pdf", self.combine_pdf.get()))
        self.target_size_enabled.set(data.get("target_size_enabled", self.target_size_enabled.get()))
        self.target_size_kb.set(data.get("target_size_kb", self.target_size_kb.get()))
        self.max_workers.set(data.get("max_workers", self.max_workers.get()))
        self.strip_metadata.set(data.get("strip_metadata", self.strip_metadata.get()))
        self.open_output_when_done.set(data.get("open_output_when_done", self.open_output_when_done.get()))
        self.lossless.set(data.get("lossless", self.lossless.get()))
        self.keep_folder_structure.set(data.get("keep_folder_structure", self.keep_folder_structure.get()))
        self.use_output_subfolder.set(data.get("use_output_subfolder", self.use_output_subfolder.get()))
        self.remove_background.set(data.get("remove_background", self.remove_background.get()))
        self.remove_background_tolerance.set(data.get("remove_background_tolerance", self.remove_background_tolerance.get()))
        self.remove_background_feather.set(data.get("remove_background_feather", self.remove_background_feather.get()))
        self.rotate_degrees.set(data.get("rotate_degrees", self.rotate_degrees.get()))
        self.flip_horizontal.set(data.get("flip_horizontal", self.flip_horizontal.get()))
        self.flip_vertical.set(data.get("flip_vertical", self.flip_vertical.get()))
        self.crop_enabled.set(data.get("crop_enabled", self.crop_enabled.get()))
        self.crop_left.set(data.get("crop_left", self.crop_left.get()))
        self.crop_top.set(data.get("crop_top", self.crop_top.get()))
        self.crop_right.set(data.get("crop_right", self.crop_right.get()))
        self.crop_bottom.set(data.get("crop_bottom", self.crop_bottom.get()))
        self.square_canvas.set(data.get("square_canvas", self.square_canvas.get()))
        self.canvas_size.set(data.get("canvas_size", self.canvas_size.get()))
        self.canvas_transparent.set(data.get("canvas_transparent", self.canvas_transparent.get()))
        self.brightness.set(data.get("brightness", self.brightness.get()))
        self.contrast.set(data.get("contrast", self.contrast.get()))
        self.saturation.set(data.get("saturation", self.saturation.get()))
        self.large_file_rule_enabled.set(data.get("large_file_rule_enabled", self.large_file_rule_enabled.get()))
        self.large_file_threshold_kb.set(data.get("large_file_threshold_kb", self.large_file_threshold_kb.get()))
        self.large_file_quality.set(data.get("large_file_quality", self.large_file_quality.get()))
        self.pdf_page_size.set(data.get("pdf_page_size", self.pdf_page_size.get()))
        self.pdf_auto_orientation.set(data.get("pdf_auto_orientation", self.pdf_auto_orientation.get()))
        self.create_zip.set(data.get("create_zip", self.create_zip.get()))
        self.notify_on_done.set(data.get("notify_on_done", self.notify_on_done.get()))
        self.dark_mode.set(data.get("dark_mode", self.dark_mode.get()))

    def _save_settings(self) -> None:
        payload = {
            "schemaVersion": 1,
            "output_dir": self.output_dir.get(),
            **self._current_profile_data(),
            "extra_formats": self.extra_formats.get(),
            "strip_metadata": self.strip_metadata.get(),
            "open_output_when_done": self.open_output_when_done.get(),
        }
        try:
            self._write_json_atomic(SETTINGS_PATH, payload)
        except OSError as exc:
            append_log(f"No se pudo guardar settings.json: {exc}")

    def _on_close(self) -> None:
        self.save_session(silent=True)
        self._save_settings()
        self.destroy()

    def _load_profiles(self) -> dict[str, dict]:
        try:
            if PROFILES_PATH.exists():
                return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _save_profiles(self) -> None:
        self._write_json_atomic(PROFILES_PATH, self.profiles)

    def _current_profile_data(self) -> dict:
        return {
            "output_format": self.output_format.get(),
            "extra_formats": self.extra_formats.get(),
            "quality": int(self.quality.get()),
            "resize_enabled": self.resize_enabled.get(),
            "resize_width": self.resize_width.get(),
            "resize_height": self.resize_height.get(),
            "keep_aspect": self.keep_aspect.get(),
            "background_hex": self.background_hex.get(),
            "naming_mode": self.naming_mode.get(),
            "prefix": self.prefix.get(),
            "suffix": self.suffix.get(),
            "naming_template": self.naming_template.get(),
            "overwrite": self.overwrite.get(),
            "combine_pdf": self.combine_pdf.get(),
            "target_size_enabled": self.target_size_enabled.get(),
            "target_size_kb": self.target_size_kb.get(),
            "max_workers": int(self.max_workers.get()),
            "strip_metadata": self.strip_metadata.get(),
            "open_output_when_done": self.open_output_when_done.get(),
            "lossless": self.lossless.get(),
            "keep_folder_structure": self.keep_folder_structure.get(),
            "use_output_subfolder": self.use_output_subfolder.get(),
            "remove_background": self.remove_background.get(),
            "remove_background_tolerance": int(self.remove_background_tolerance.get()),
            "remove_background_feather": int(self.remove_background_feather.get()),
            "rotate_degrees": int(self.rotate_degrees.get()),
            "flip_horizontal": self.flip_horizontal.get(),
            "flip_vertical": self.flip_vertical.get(),
            "crop_enabled": self.crop_enabled.get(),
            "crop_left": self.crop_left.get(),
            "crop_top": self.crop_top.get(),
            "crop_right": self.crop_right.get(),
            "crop_bottom": self.crop_bottom.get(),
            "square_canvas": self.square_canvas.get(),
            "canvas_size": self.canvas_size.get(),
            "canvas_transparent": self.canvas_transparent.get(),
            "brightness": int(float(self.brightness.get())),
            "contrast": int(float(self.contrast.get())),
            "saturation": int(float(self.saturation.get())),
            "large_file_rule_enabled": self.large_file_rule_enabled.get(),
            "large_file_threshold_kb": self.large_file_threshold_kb.get(),
            "large_file_quality": int(self.large_file_quality.get()),
            "pdf_page_size": self.pdf_page_size.get(),
            "pdf_auto_orientation": self.pdf_auto_orientation.get(),
            "create_zip": self.create_zip.get(),
            "notify_on_done": self.notify_on_done.get(),
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

    def _unique_profile_name(self, name: str) -> str:
        clean_name = name.strip() or "Perfil"
        if clean_name not in self.profiles:
            return clean_name
        counter = 2
        while f"{clean_name} {counter}" in self.profiles:
            counter += 1
        return f"{clean_name} {counter}"

    def _validated_profile_data(self, data: dict) -> dict | None:
        if not isinstance(data, dict):
            return None
        def int_or_default(value, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        profile = self._current_profile_data()
        for key in profile:
            if key in data:
                profile[key] = data[key]

        output_format = str(profile.get("output_format", "WEBP")).upper().lstrip(".")
        if output_format not in OUTPUT_FORMATS:
            return None
        profile["output_format"] = output_format
        profile["extra_formats"] = str(profile.get("extra_formats", ""))
        try:
            parse_output_formats(output_format, profile["extra_formats"])
        except ValueError:
            profile["extra_formats"] = ""

        profile["quality"] = max(1, min(100, int_or_default(profile.get("quality"), 85)))
        profile["resize_width"] = str(profile.get("resize_width", ""))
        profile["resize_height"] = str(profile.get("resize_height", ""))
        profile["target_size_kb"] = str(profile.get("target_size_kb", ""))
        profile["prefix"] = str(profile.get("prefix", ""))
        profile["suffix"] = str(profile.get("suffix", ""))
        profile["naming_template"] = str(profile.get("naming_template", "{name}_{format}"))
        profile["crop_left"] = str(profile.get("crop_left", "0"))
        profile["crop_top"] = str(profile.get("crop_top", "0"))
        profile["crop_right"] = str(profile.get("crop_right", "0"))
        profile["crop_bottom"] = str(profile.get("crop_bottom", "0"))
        profile["canvas_size"] = str(profile.get("canvas_size", ""))
        profile["large_file_threshold_kb"] = str(profile.get("large_file_threshold_kb", "2048"))
        profile["background_hex"] = str(profile.get("background_hex", "#ffffff"))
        if profile["background_hex"].startswith("#"):
            try:
                ImageColor.getrgb(profile["background_hex"])
            except ValueError:
                profile["background_hex"] = "#ffffff"
        else:
            profile["background_hex"] = "#ffffff"
        if profile.get("naming_mode") not in {"Conservar", "Numerado", "Prefijo/sufijo", "Plantilla"}:
            profile["naming_mode"] = "Conservar"
        for key in (
            "resize_enabled",
            "keep_aspect",
            "overwrite",
            "combine_pdf",
            "target_size_enabled",
            "strip_metadata",
            "open_output_when_done",
            "lossless",
            "keep_folder_structure",
            "use_output_subfolder",
            "remove_background",
            "flip_horizontal",
            "flip_vertical",
            "crop_enabled",
            "square_canvas",
            "canvas_transparent",
            "large_file_rule_enabled",
            "pdf_auto_orientation",
            "create_zip",
            "notify_on_done",
            "dark_mode",
        ):
            profile[key] = bool(profile.get(key))
        profile["max_workers"] = max(1, min(16, int_or_default(profile.get("max_workers"), min(4, max(1, os.cpu_count() or 1)))))
        profile["remove_background_tolerance"] = max(0, min(128, int_or_default(profile.get("remove_background_tolerance"), 32)))
        profile["remove_background_feather"] = max(0, min(8, int_or_default(profile.get("remove_background_feather"), 1)))
        profile["rotate_degrees"] = int_or_default(profile.get("rotate_degrees"), 0)
        if profile["rotate_degrees"] not in {0, 90, 180, 270}:
            profile["rotate_degrees"] = 0
        profile["brightness"] = max(-100, min(100, int_or_default(profile.get("brightness"), 0)))
        profile["contrast"] = max(-100, min(100, int_or_default(profile.get("contrast"), 0)))
        profile["saturation"] = max(-100, min(100, int_or_default(profile.get("saturation"), 0)))
        profile["large_file_quality"] = max(15, min(95, int_or_default(profile.get("large_file_quality"), 72)))
        if profile.get("pdf_page_size") not in {"Original", "A4", "Carta"}:
            profile["pdf_page_size"] = "Original"
        return profile

    def _default_profile_data(self) -> dict:
        return {
            "output_format": "WEBP",
            "extra_formats": "",
            "quality": 85,
            "resize_enabled": False,
            "resize_width": "",
            "resize_height": "",
            "keep_aspect": True,
            "background_hex": "#ffffff",
            "naming_mode": "Conservar",
            "prefix": "",
            "suffix": "",
            "naming_template": "{name}_{format}",
            "overwrite": False,
            "combine_pdf": False,
            "target_size_enabled": False,
            "target_size_kb": "",
            "max_workers": min(4, max(1, os.cpu_count() or 1)),
            "strip_metadata": True,
            "open_output_when_done": True,
            "lossless": False,
            "keep_folder_structure": False,
            "use_output_subfolder": False,
            "remove_background": False,
            "remove_background_tolerance": 32,
            "remove_background_feather": 1,
            "rotate_degrees": 0,
            "flip_horizontal": False,
            "flip_vertical": False,
            "crop_enabled": False,
            "crop_left": "0",
            "crop_top": "0",
            "crop_right": "0",
            "crop_bottom": "0",
            "square_canvas": False,
            "canvas_size": "",
            "canvas_transparent": True,
            "brightness": 0,
            "contrast": 0,
            "saturation": 0,
            "large_file_rule_enabled": False,
            "large_file_threshold_kb": "2048",
            "large_file_quality": 72,
            "pdf_page_size": "Original",
            "pdf_auto_orientation": True,
            "create_zip": False,
            "notify_on_done": True,
            "dark_mode": self.dark_mode.get(),
        }

    def export_profiles(self) -> None:
        profiles = self.profiles or {"Actual": self._current_profile_data()}
        destination = filedialog.asksaveasfilename(
            title="Exportar perfiles",
            defaultextension=".json",
            filetypes=[("Perfiles JSON", "*.json"), ("Todos los archivos", "*.*")],
        )
        if not destination:
            return
        payload = {"app": APP_NAME, "version": APP_VERSION, "profiles": profiles}
        try:
            Path(destination).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.status.set(f"Perfiles exportados: {destination}")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudieron exportar los perfiles:\n{exc}")

    def export_selected_profile(self) -> None:
        name = self.profile_name.get().strip()
        profile = self.profiles.get(name)
        if profile is None:
            name = "Actual"
            profile = self._current_profile_data()
        destination = filedialog.asksaveasfilename(
            title="Exportar perfil",
            initialfile=f"{safe_name_part(name) or 'perfil'}.json",
            defaultextension=".json",
            filetypes=[("Perfil JSON", "*.json"), ("Todos los archivos", "*.*")],
        )
        if not destination:
            return
        payload = {"app": APP_NAME, "version": APP_VERSION, "profiles": {name: profile}}
        try:
            Path(destination).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.status.set(f"Perfil exportado: {name}")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudo exportar el perfil:\n{exc}")

    def install_builtin_profiles(self) -> None:
        base = self._default_profile_data()

        def profile(**changes) -> dict:
            data = dict(base)
            data.update(changes)
            return data

        builtin = {
            "Web ligero": profile(output_format="WEBP", quality=78, resize_enabled=True, resize_width="1600"),
            "Producto tienda 1200": profile(
                output_format="PNG",
                extra_formats="WEBP,JPG",
                quality=88,
                resize_enabled=True,
                resize_width="1200",
                resize_height="1200",
                remove_background=True,
                square_canvas=True,
                canvas_size="1200",
                canvas_transparent=False,
            ),
            "WhatsApp rapido": profile(output_format="JPG", quality=74, resize_enabled=True, resize_width="1600"),
            "PDF A4": profile(output_format="PDF", combine_pdf=True, pdf_page_size="A4", pdf_auto_orientation=True),
            "Archivo sin perdida": profile(output_format="WEBP", quality=100, lossless=True, strip_metadata=False),
            "Iconos transparentes": profile(output_format="PNG", extra_formats="ICO", quality=100, resize_enabled=True, resize_width="512", resize_height="512"),
        }
        self.profiles.update(builtin)
        self._save_profiles()
        self.profile_combo.configure(values=sorted(self.profiles.keys()))
        self.status.set(f"Perfiles default instalados: {len(builtin)}.")

    def reset_current_settings(self) -> None:
        current_profile = self.profile_name.get()
        temp_name = "__converter_defaults__"
        self.profiles[temp_name] = self._default_profile_data()
        self.profile_name.set(temp_name)
        try:
            self.load_selected_profile()
        finally:
            self.profiles.pop(temp_name, None)
            self.profile_name.set(current_profile if current_profile in self.profiles else "")
            self.profile_combo.configure(values=sorted(self.profiles.keys()))
        self.status.set("Ajustes restaurados a valores recomendados.")

    def import_profiles(self) -> None:
        source = filedialog.askopenfilename(
            title="Importar perfiles",
            filetypes=[("Perfiles JSON", "*.json"), ("Todos los archivos", "*.*")],
        )
        if not source:
            return
        try:
            payload = json.loads(Path(source).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror(APP_NAME, f"No se pudo leer el archivo de perfiles:\n{exc}")
            return
        raw_profiles = payload.get("profiles", payload) if isinstance(payload, dict) else {}
        if not isinstance(raw_profiles, dict):
            messagebox.showerror(APP_NAME, "El archivo no contiene perfiles validos.")
            return

        imported = 0
        for name, data in raw_profiles.items():
            profile = self._validated_profile_data(data)
            if profile is None:
                continue
            self.profiles[self._unique_profile_name(str(name))] = profile
            imported += 1
        if not imported:
            messagebox.showwarning(APP_NAME, "No se encontro ningun perfil compatible.")
            return
        self._save_profiles()
        self.profile_combo.configure(values=sorted(self.profiles.keys()))
        self.status.set(f"Perfiles importados: {imported}.")

    def export_settings(self) -> None:
        destination = filedialog.asksaveasfilename(
            title="Exportar ajustes",
            defaultextension=".json",
            filetypes=[("Ajustes JSON", "*.json"), ("Todos los archivos", "*.*")],
        )
        if not destination:
            return
        payload = {"app": APP_NAME, "version": APP_VERSION, "settings": {"output_dir": self.output_dir.get(), **self._current_profile_data()}}
        try:
            Path(destination).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.status.set(f"Ajustes exportados: {destination}")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudieron exportar los ajustes:\n{exc}")

    def import_settings(self) -> None:
        source = filedialog.askopenfilename(
            title="Importar ajustes",
            filetypes=[("Ajustes JSON", "*.json"), ("Todos los archivos", "*.*")],
        )
        if not source:
            return
        try:
            payload = json.loads(Path(source).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror(APP_NAME, f"No se pudo leer el archivo de ajustes:\n{exc}")
            return
        data = payload.get("settings", payload) if isinstance(payload, dict) else {}
        profile = self._validated_profile_data(data)
        if profile is None:
            messagebox.showerror(APP_NAME, "El archivo no contiene ajustes compatibles.")
            return
        if isinstance(data, dict) and data.get("output_dir"):
            self.output_dir.set(str(data["output_dir"]))
        temp_name = "__imported_settings__"
        self.profiles[temp_name] = profile
        self.profile_name.set(temp_name)
        self.load_selected_profile()
        self.profiles.pop(temp_name, None)
        self.profile_name.set("")
        self.profile_combo.configure(values=sorted(self.profiles.keys()))
        self.status.set("Ajustes importados.")

    def load_selected_profile(self) -> None:
        name = self.profile_name.get()
        data = self.profiles.get(name)
        if not data:
            messagebox.showinfo(APP_NAME, "Selecciona un perfil guardado.")
            return
        self.output_format.set(data.get("output_format", "WEBP"))
        self.extra_formats.set(data.get("extra_formats", ""))
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
        self.naming_template.set(data.get("naming_template", "{name}_{format}"))
        self.overwrite.set(data.get("overwrite", False))
        self.combine_pdf.set(data.get("combine_pdf", False))
        self.target_size_enabled.set(data.get("target_size_enabled", False))
        self.target_size_kb.set(data.get("target_size_kb", ""))
        self.max_workers.set(data.get("max_workers", min(4, max(1, os.cpu_count() or 1))))
        self.strip_metadata.set(data.get("strip_metadata", True))
        self.open_output_when_done.set(data.get("open_output_when_done", True))
        self.lossless.set(data.get("lossless", False))
        self.keep_folder_structure.set(data.get("keep_folder_structure", False))
        self.use_output_subfolder.set(data.get("use_output_subfolder", False))
        self.remove_background.set(data.get("remove_background", False))
        self.remove_background_tolerance.set(data.get("remove_background_tolerance", 32))
        self.remove_background_feather.set(data.get("remove_background_feather", 1))
        self.rotate_degrees.set(data.get("rotate_degrees", 0))
        self.flip_horizontal.set(data.get("flip_horizontal", False))
        self.flip_vertical.set(data.get("flip_vertical", False))
        self.crop_enabled.set(data.get("crop_enabled", False))
        self.crop_left.set(data.get("crop_left", "0"))
        self.crop_top.set(data.get("crop_top", "0"))
        self.crop_right.set(data.get("crop_right", "0"))
        self.crop_bottom.set(data.get("crop_bottom", "0"))
        self.square_canvas.set(data.get("square_canvas", False))
        self.canvas_size.set(data.get("canvas_size", ""))
        self.canvas_transparent.set(data.get("canvas_transparent", True))
        self.brightness.set(data.get("brightness", 0))
        self.contrast.set(data.get("contrast", 0))
        self.saturation.set(data.get("saturation", 0))
        self.large_file_rule_enabled.set(data.get("large_file_rule_enabled", False))
        self.large_file_threshold_kb.set(data.get("large_file_threshold_kb", "2048"))
        self.large_file_quality.set(data.get("large_file_quality", 72))
        self.pdf_page_size.set(data.get("pdf_page_size", "Original"))
        self.pdf_auto_orientation.set(data.get("pdf_auto_orientation", True))
        self.create_zip.set(data.get("create_zip", False))
        self.notify_on_done.set(data.get("notify_on_done", True))
        requested_dark_mode = data.get("dark_mode", self.dark_mode.get())
        if requested_dark_mode != self.dark_mode.get():
            self.dark_mode.set(requested_dark_mode)
            for child in self.winfo_children():
                child.destroy()
            self._build_ui()
            self._restore_file_tree()
            self._restore_history()
        self._refresh_option_states()
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
        self.extra_formats.set("")
        self.lossless.set(False)
        self.target_size_enabled.set(False)
        self.large_file_rule_enabled.set(False)
        self.square_canvas.set(False)
        self.crop_enabled.set(False)
        self.brightness.set(0)
        self.contrast.set(0)
        self.saturation.set(0)
        self.pdf_page_size.set("Original")
        self.pdf_auto_orientation.set(True)
        self.create_zip.set(False)
        self.notify_on_done.set(True)
        if preset == "Para web":
            self.output_format.set("WEBP")
            self.quality.set(82)
            self.resize_enabled.set(True)
            self.resize_width.set("1600")
            self.resize_height.set("")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "Instagram":
            self.output_format.set("JPG")
            self.quality.set(88)
            self.resize_enabled.set(True)
            self.resize_width.set("1080")
            self.resize_height.set("1080")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "WhatsApp":
            self.output_format.set("JPG")
            self.quality.set(76)
            self.resize_enabled.set(True)
            self.resize_width.set("1600")
            self.resize_height.set("")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "Impresion":
            self.output_format.set("TIFF")
            self.quality.set(95)
            self.resize_enabled.set(False)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "Maxima calidad":
            self.output_format.set("PNG")
            self.quality.set(100)
            self.resize_enabled.set(False)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "Reducir peso":
            self.output_format.set("WEBP")
            self.quality.set(65)
            self.resize_enabled.set(True)
            self.resize_width.set("1200")
            self.resize_height.set("")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "Maximo ahorro":
            self.output_format.set("WEBP")
            self.quality.set(58)
            self.resize_enabled.set(True)
            self.resize_width.set("1200")
            self.resize_height.set("")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
            self.large_file_rule_enabled.set(True)
            self.large_file_threshold_kb.set("2048")
            self.large_file_quality.set(50)
            self.remove_background.set(False)
        elif preset == "Sin perdida":
            self.output_format.set("WEBP")
            self.quality.set(100)
            self.lossless.set(True)
            self.resize_enabled.set(False)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "Icono .ico":
            self.output_format.set("ICO")
            self.resize_enabled.set(True)
            self.resize_width.set("256")
            self.resize_height.set("256")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "PDF desde imagenes":
            self.output_format.set("PDF")
            self.combine_pdf.set(True)
            self.pdf_page_size.set("A4")
            self.resize_enabled.set(False)
            self.background_hex.set("#ffffff")
            self._refresh_color_swatch()
            self.remove_background.set(False)
        elif preset == "SVG vector":
            self.output_format.set("SVG")
            self.quality.set(100)
            self.resize_enabled.set(True)
            self.resize_width.set("1024")
            self.resize_height.set("")
            self.keep_aspect.set(True)
            self.combine_pdf.set(False)
            self.remove_background.set(False)
        elif preset == "Fondo transparente":
            self.output_format.set("PNG")
            self.quality.set(100)
            self.resize_enabled.set(False)
            self.combine_pdf.set(False)
            self.remove_background.set(True)
            self.remove_background_tolerance.set(36)
        elif preset == "Producto tienda":
            self.output_format.set("PNG")
            self.extra_formats.set("WEBP,JPG")
            self.quality.set(88)
            self.resize_enabled.set(True)
            self.resize_width.set("1200")
            self.resize_height.set("1200")
            self.keep_aspect.set(True)
            self.background_hex.set("#ffffff")
            self._refresh_color_swatch()
            self.combine_pdf.set(False)
            self.target_size_enabled.set(False)
            self.remove_background.set(True)
            self.remove_background_tolerance.set(34)
            self.square_canvas.set(True)
            self.canvas_size.set("1200")
            self.canvas_transparent.set(False)
        self._refresh_quality_state()

    def _selected_output_formats(self, strict: bool = False) -> tuple[str, ...]:
        try:
            output_formats = parse_output_formats(self.output_format.get(), self.extra_formats.get())
        except ValueError:
            if strict:
                raise
            output_formats = (self.output_format.get(),)
        if self.combine_pdf.get() and "PDF" not in output_formats:
            output_formats = ("PDF", *output_formats)
        return output_formats

    def _set_widget_state(self, widget_name: str, enabled: bool) -> None:
        if not hasattr(self, widget_name):
            return
        widget = getattr(self, widget_name)
        state = tk.NORMAL if enabled else tk.DISABLED
        try:
            widget.configure(state=state)
        except tk.TclError:
            pass

    def _refresh_quality_state(self) -> None:
        self._refresh_option_states()

    def _refresh_option_states(self) -> None:
        if not hasattr(self, "quality_scale"):
            return
        output_formats = self._selected_output_formats()
        quality_enabled = any(OUTPUT_FORMATS.get(fmt, {}).get("quality", False) for fmt in output_formats)
        resize_enabled = self.resize_enabled.get()
        target_enabled = self.target_size_enabled.get() and quality_enabled
        prefix_enabled = self.naming_mode.get() == "Prefijo/sufijo"
        template_enabled = self.naming_mode.get() == "Plantilla"
        background_enabled = any(not OUTPUT_FORMATS.get(fmt, {}).get("supports_alpha", False) for fmt in output_formats)
        lossless_enabled = "WEBP" in output_formats
        remove_background_enabled = self.remove_background.get()
        crop_enabled = self.crop_enabled.get()
        square_enabled = self.square_canvas.get()
        large_rule_enabled = self.large_file_rule_enabled.get() and quality_enabled

        self.quality_scale.configure(state=tk.NORMAL if quality_enabled else tk.DISABLED)
        self.quality_label.configure(text=str(self.quality.get()) if quality_enabled else "No aplica", foreground=self.colors["text"] if quality_enabled else self.colors["muted"])
        self._set_widget_state("extra_formats_entry", True)
        self._set_widget_state("resize_width_entry", resize_enabled)
        self._set_widget_state("resize_height_entry", resize_enabled)
        self._set_widget_state("keep_aspect_check", resize_enabled)
        self._set_widget_state("target_size_entry", target_enabled)
        self._set_widget_state("prefix_entry", prefix_enabled)
        self._set_widget_state("suffix_entry", prefix_enabled)
        self._set_widget_state("naming_template_entry", template_enabled)
        self._set_widget_state("canvas_size_entry", square_enabled)
        self._set_widget_state("background_button", background_enabled)
        self._set_widget_state("large_file_threshold_entry", large_rule_enabled)
        self._set_widget_state("large_file_quality_spinbox", large_rule_enabled)
        self._set_widget_state("remove_background_feather_spinbox", remove_background_enabled)
        self._set_widget_state("lossless_check", lossless_enabled)
        for widget_name in ("crop_izq_entry", "crop_arriba_entry", "crop_der_entry", "crop_abajo_entry"):
            self._set_widget_state(widget_name, crop_enabled)
        self.remove_background_scale.configure(state=tk.NORMAL if remove_background_enabled else tk.DISABLED)
        self.remove_background_label.configure(
            text=str(int(float(self.remove_background_tolerance.get()))),
            foreground=self.colors["text"] if remove_background_enabled else self.colors["muted"],
        )
        if not lossless_enabled and self.lossless.get():
            self.lossless.set(False)
        if hasattr(self, "color_swatch"):
            self.color_swatch.configure(fg=self._text_color_for_background(self.background_hex.get()))
        self._update_output_name_preview()

    def _read_options(self, show_errors: bool = True) -> ConversionOptions | None:
        try:
            output_formats = self._selected_output_formats(strict=True)
            background = ImageColor.getrgb(self.background_hex.get())
            width = int(self.resize_width.get()) if self.resize_enabled.get() and self.resize_width.get().strip() else None
            height = int(self.resize_height.get()) if self.resize_enabled.get() and self.resize_height.get().strip() else None
            target_size = int(self.target_size_kb.get()) if self.target_size_enabled.get() and self.target_size_kb.get().strip() else None
            max_workers = int(self.max_workers.get())
            remove_background_tolerance = int(float(self.remove_background_tolerance.get()))
            remove_background_feather = int(float(self.remove_background_feather.get()))
            rotate_degrees = int(self.rotate_degrees.get())
            crop_left = int(self.crop_left.get()) if self.crop_enabled.get() and self.crop_left.get().strip() else 0
            crop_top = int(self.crop_top.get()) if self.crop_enabled.get() and self.crop_top.get().strip() else 0
            crop_right = int(self.crop_right.get()) if self.crop_enabled.get() and self.crop_right.get().strip() else 0
            crop_bottom = int(self.crop_bottom.get()) if self.crop_enabled.get() and self.crop_bottom.get().strip() else 0
            canvas_size = int(self.canvas_size.get()) if self.square_canvas.get() and self.canvas_size.get().strip() else None
            large_file_threshold = (
                int(self.large_file_threshold_kb.get())
                if self.large_file_rule_enabled.get() and self.large_file_threshold_kb.get().strip()
                else None
            )
            large_file_quality = int(self.large_file_quality.get())
            brightness = int(float(self.brightness.get()))
            contrast = int(float(self.contrast.get()))
            saturation = int(float(self.saturation.get()))
            pdf_page_size = self.pdf_page_size.get()
            if width is not None and width <= 0 or height is not None and height <= 0:
                raise ValueError("El ancho y alto deben ser mayores a cero.")
            if target_size is not None and target_size <= 0:
                raise ValueError("Peso maximo (KB) debe ser mayor que cero.")
            if max_workers <= 0:
                raise ValueError("La cantidad de procesos debe ser mayor a cero.")
            if remove_background_tolerance < 0:
                raise ValueError("Fuerza fondo debe ser mayor o igual a cero.")
            if remove_background_feather < 0:
                raise ValueError("Borde suave debe ser mayor o igual a cero.")
            if rotate_degrees not in {0, 90, 180, 270}:
                raise ValueError("Rotar debe ser 0, 90, 180 o 270.")
            if min(crop_left, crop_top, crop_right, crop_bottom) < 0:
                raise ValueError("El recorte debe ser mayor o igual a cero.")
            if canvas_size is not None and canvas_size <= 0:
                raise ValueError("Lado de lienzo debe ser mayor a cero.")
            if large_file_threshold is not None and large_file_threshold <= 0:
                raise ValueError("Umbral de archivo pesado debe ser mayor a cero.")
            if large_file_quality < 15 or large_file_quality > 95:
                raise ValueError("Calidad de regla debe estar entre 15 y 95.")
            if min(brightness, contrast, saturation) < -100 or max(brightness, contrast, saturation) > 100:
                raise ValueError("Brillo, contraste y saturacion deben estar entre -100 y 100.")
            if pdf_page_size not in {"Original", "A4", "Carta"}:
                raise ValueError("Tamano de pagina PDF invalido.")
        except ValueError as exc:
            if show_errors:
                messagebox.showerror(APP_NAME, f"Opcion invalida:\n{exc}")
            return None

        output_dir = Path(self.output_dir.get()).expanduser()
        if self.use_output_subfolder.get():
            output_dir = output_dir / "Converter_Output"

        return ConversionOptions(
            output_format=self.output_format.get(),
            output_formats=output_formats,
            quality=int(self.quality.get()),
            output_dir=output_dir,
            resize_enabled=self.resize_enabled.get(),
            width=width,
            height=height,
            keep_aspect=self.keep_aspect.get(),
            background=background,
            naming_mode=self.naming_mode.get(),
            prefix=self.prefix.get(),
            suffix=self.suffix.get(),
            naming_template=self.naming_template.get(),
            overwrite=self.overwrite.get(),
            combine_pdf=self.combine_pdf.get(),
            target_size_enabled=self.target_size_enabled.get(),
            target_size_kb=target_size,
            max_workers=max(1, max_workers),
            strip_metadata=self.strip_metadata.get(),
            open_output_when_done=self.open_output_when_done.get(),
            lossless=self.lossless.get(),
            keep_folder_structure=self.keep_folder_structure.get(),
            use_output_subfolder=self.use_output_subfolder.get(),
            remove_background=self.remove_background.get(),
            remove_background_tolerance=max(0, min(128, remove_background_tolerance)),
            remove_background_feather=max(0, min(8, remove_background_feather)),
            rotate_degrees=rotate_degrees,
            flip_horizontal=self.flip_horizontal.get(),
            flip_vertical=self.flip_vertical.get(),
            crop_enabled=self.crop_enabled.get(),
            crop_left=crop_left,
            crop_top=crop_top,
            crop_right=crop_right,
            crop_bottom=crop_bottom,
            square_canvas=self.square_canvas.get(),
            canvas_size=canvas_size,
            canvas_transparent=self.canvas_transparent.get(),
            brightness=max(-100, min(100, brightness)),
            contrast=max(-100, min(100, contrast)),
            saturation=max(-100, min(100, saturation)),
            large_file_rule_enabled=self.large_file_rule_enabled.get(),
            large_file_threshold_kb=large_file_threshold,
            large_file_quality=max(15, min(95, large_file_quality)),
            pdf_page_size=pdf_page_size,
            pdf_auto_orientation=self.pdf_auto_orientation.get(),
            create_zip=self.create_zip.get(),
            notify_on_done=self.notify_on_done.get(),
        )

    def start_conversion(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_NAME, "Agrega al menos una imagen.")
            return
        self._start_conversion_for_files(list(self.files))

    def _start_conversion_for_files(self, files: list[Path]) -> None:
        if self.conversion_running:
            messagebox.showinfo(APP_NAME, "Ya hay una conversion en curso.")
            return
        if not files:
            messagebox.showwarning(APP_NAME, "No hay imagenes para convertir.")
            return

        options = self._read_options()
        if options is None:
            return

        try:
            options.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"No se pudo crear la carpeta de salida:\n{exc}")
            return

        self._save_settings()
        self.last_conversion_files = list(files)
        append_log(f"Inicio conversion: {len(files)} archivo(s), formatos={','.join(options.output_formats)}, salida={options.output_dir}")
        self.cancel_event.clear()
        self.pause_event.clear()
        self.conversion_running = True
        self.convert_button.configure(state=tk.DISABLED)
        self.pause_button.configure(state=tk.NORMAL, text="Pausar")
        self.cancel_button.configure(state=tk.NORMAL)
        self.retry_button.configure(state=tk.DISABLED)
        self.repeat_button.configure(state=tk.DISABLED)
        self.progress.set(0)
        self.throughput_info.set("Preparando conversion...")
        thread = threading.Thread(target=self._convert_worker, args=(files, options), daemon=True)
        thread.start()

    def retry_failed(self) -> None:
        files = [path for path in self.last_failed_files if path.exists()]
        if not files:
            messagebox.showinfo(APP_NAME, "No hay archivos con error para reintentar.")
            return
        self._start_conversion_for_files(files)

    def repeat_last_conversion(self) -> None:
        files = [path for path in self.last_conversion_files if path.exists()]
        if not files:
            messagebox.showinfo(APP_NAME, "No hay una conversion anterior para repetir.")
            return
        self._start_conversion_for_files(files)

    def toggle_pause_conversion(self) -> None:
        if not self.conversion_running:
            return
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.configure(text="Pausar")
            self.status.set("Conversion reanudada.")
        else:
            self.pause_event.set()
            self.pause_button.configure(text="Reanudar")
            self.status.set("Conversion pausada. Las tareas activas terminan y no se envian nuevas.")

    def _wait_if_paused(self) -> None:
        while self.pause_event.is_set() and not self.cancel_event.is_set():
            time.sleep(0.15)

    def _effective_format_options(self, options: ConversionOptions, source: Path, output_format: str) -> ConversionOptions:
        quality = options.quality
        if (
            options.large_file_rule_enabled
            and options.large_file_threshold_kb
            and source.exists()
            and source.stat().st_size > options.large_file_threshold_kb * 1024
            and OUTPUT_FORMATS[output_format]["quality"]
        ):
            quality = min(quality, options.large_file_quality)
        return replace(options, output_format=output_format, output_formats=(output_format,), combine_pdf=False, quality=quality)

    def _convert_worker(self, files: list[Path], options: ConversionOptions) -> None:
        converted = 0
        errors: list[str] = []
        failed_paths: list[Path] = []
        outputs: list[Path] = []
        cancelled = False
        started_at = time.monotonic()
        input_bytes = sum(path.stat().st_size for path in files if path.exists())
        self.after(0, self._reset_file_statuses)

        try:
            formats = list(options.output_formats)
            total_jobs = max(1, len(files) * len(formats))
            completed = 0
            reserved_outputs: set[Path] = set()

            if options.combine_pdf and "PDF" in formats:
                destination = options.output_dir / "imagenes_convertidas.pdf"
                if not options.overwrite:
                    counter = 1
                    while destination.exists() or destination in reserved_outputs:
                        destination = options.output_dir / f"imagenes_convertidas_{counter}.pdf"
                        counter += 1
                reserved_outputs.add(destination)
                self._set_status("Creando PDF unico...")
                for source in files:
                    self.after(0, lambda path=source: self._set_file_status(path, "PDF"))
                if self.cancel_event.is_set():
                    cancelled = True
                else:
                    try:
                        self._wait_if_paused()
                        pdf_options = replace(options, output_format="PDF", output_formats=("PDF",))
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        combine_images_to_pdf(files, destination, pdf_options)
                        outputs.append(destination)
                        converted += 1
                        pdf_size = format_size(destination.stat().st_size)
                        for source in files:
                            self.after(0, lambda path=source: self._set_file_status(path, "PDF OK"))
                            self.after(0, lambda path=source, text=f"{pdf_size} PDF": self._set_file_estimate(-1, path, text))
                    except Exception as exc:
                        errors.append(f"PDF unico: {exc}")
                        failed_paths.extend(files)
                completed += 1
                total_jobs = max(1, len(files) * (len(formats) - 1) + 1)
                self._set_progress(completed / total_jobs * 100)
                formats = [fmt for fmt in formats if fmt != "PDF"]

            if formats and not cancelled:
                job_iter = iter((index, source, output_format) for index, source in enumerate(files, start=1) for output_format in formats)
                source_pending = {source: len(formats) for source in files}
                source_failed: set[Path] = set()
                actual_bytes_by_source: dict[Path, int] = {}

                def convert_one(index: int, source: Path, output_format: str, destination: Path) -> tuple[bool, Path | None, str | None]:
                    if self.cancel_event.is_set():
                        return False, None, None
                    self._wait_if_paused()
                    self.after(0, lambda path=source, fmt=output_format: self._set_file_status(path, f"{fmt}..."))
                    try:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        format_options = self._effective_format_options(options, source, output_format)
                        convert_image_optimized(source, destination, format_options)
                        warning = None
                        if (
                            format_options.target_size_enabled
                            and format_options.target_size_kb
                            and OUTPUT_FORMATS[output_format]["quality"]
                            and destination.stat().st_size > format_options.target_size_kb * 1024
                        ):
                            warning = (
                                f"{source.name} ({output_format}): objetivo {format_options.target_size_kb} KB no alcanzable, "
                                f"salida {format_size(destination.stat().st_size)}"
                            )
                        return True, destination, warning
                    except Exception as exc:
                        return False, None, f"{source.name} ({output_format}): {exc}"

                max_workers = min(options.max_workers, max(1, len(files) * len(formats)))
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map: dict[concurrent.futures.Future, tuple[int, Path, str]] = {}

                    def submit_next() -> bool:
                        self._wait_if_paused()
                        if self.cancel_event.is_set():
                            return False
                        try:
                            index, source, output_format = next(job_iter)
                        except StopIteration:
                            return False
                        format_options = self._effective_format_options(options, source, output_format)
                        destination = build_output_path(source, options.output_dir, format_options, index, reserved_outputs, self.file_roots.get(source))
                        future_map[executor.submit(convert_one, index, source, output_format, destination)] = (index, source, output_format)
                        return True

                    for _ in range(max_workers):
                        submit_next()

                    while future_map:
                        done, _pending = concurrent.futures.wait(
                            future_map,
                            return_when=concurrent.futures.FIRST_COMPLETED,
                        )
                        future = done.pop()
                        _index, source, output_format = future_map.pop(future)
                        if self.cancel_event.is_set():
                            cancelled = True
                        ok, output, error = future.result()
                        if ok and output is not None:
                            outputs.append(output)
                            converted += 1
                            actual_bytes_by_source[source] = actual_bytes_by_source.get(source, 0) + output.stat().st_size
                        if error:
                            errors.append(error)
                            source_failed.add(source)
                            if source not in failed_paths:
                                failed_paths.append(source)
                        source_pending[source] = max(0, source_pending.get(source, 1) - 1)
                        if source_pending[source] == 0:
                            final_status = "Error" if source in source_failed else "OK"
                            self.after(0, lambda path=source, status=final_status: self._set_file_status(path, status))
                            if source in actual_bytes_by_source:
                                actual_text = f"{format_size(actual_bytes_by_source[source])} real"
                                self.after(0, lambda path=source, text=actual_text: self._set_file_estimate(-1, path, text))
                        elif source in source_failed:
                            self.after(0, lambda path=source: self._set_file_status(path, "Error parcial"))
                        completed += 1
                        elapsed = max(0.1, time.monotonic() - started_at)
                        speed = completed / elapsed * 60
                        remaining = (total_jobs - completed) / max(completed / elapsed, 0.001)
                        self._set_status(
                            f"Procesando {min(completed, total_jobs)}/{total_jobs}: {source.name} -> {output_format}"
                        )
                        self._set_throughput(f"{speed:.1f} img/min | ETA {format_duration(remaining)}")
                        self._set_progress(completed / total_jobs * 100)
                        if self.cancel_event.is_set():
                            for pending in future_map:
                                pending.cancel()
                            cancelled = True
                            break
                        submit_next()
            if cancelled:
                for source in files:
                    self.after(0, lambda path=source: self._set_file_status(path, "Cancelado"))
        except Exception as exc:
            errors.append(str(exc))
            append_log(f"Error general de conversion: {exc}")
        finally:
            self.after(0, lambda: self.convert_button.configure(state=tk.NORMAL))
            self.after(0, lambda: self.pause_button.configure(state=tk.DISABLED, text="Pausar"))
            self.after(0, lambda: self.cancel_button.configure(state=tk.DISABLED))
            self.after(0, lambda: self.retry_button.configure(state=tk.NORMAL))
            self.after(0, lambda: self.repeat_button.configure(state=tk.NORMAL))
            self.after(0, lambda: setattr(self, "conversion_running", False))

        output_bytes = sum(output.stat().st_size for output in outputs if output.exists())
        self.after(0, lambda: self._finish_conversion(converted, errors, outputs, options, cancelled, input_bytes, output_bytes, failed_paths))

    def _finish_conversion(
        self,
        converted: int,
        errors: list[str],
        outputs: list[Path],
        options: ConversionOptions,
        cancelled: bool = False,
        input_bytes: int = 0,
        output_bytes: int = 0,
        failed_paths: list[Path] | None = None,
    ) -> None:
        self.last_failed_files = list(dict.fromkeys(failed_paths or []))
        report_dir = outputs[0].parent if outputs else Path(self.output_dir.get()).expanduser()
        if not cancelled and outputs and options.create_zip:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_path = report_dir / f"converter_outputs_{timestamp}.zip"
                counter = 1
                while zip_path.exists():
                    zip_path = report_dir / f"converter_outputs_{timestamp}_{counter}.zip"
                    counter += 1
                create_outputs_zip(outputs, zip_path)
                outputs.append(zip_path)
                converted += 1
            except OSError as exc:
                errors.append(f"No se pudo crear ZIP: {exc}")
        summary = format_conversion_summary(input_bytes, output_bytes)
        report_paths: tuple[Path, ...] | None = None
        try:
            report_paths = write_conversion_reports(report_dir, outputs, errors, converted, cancelled, input_bytes, output_bytes)
        except OSError as exc:
            errors.append(f"No se pudo crear reporte: {exc}")

        for output in outputs:
            entry = f"OK  {output.name} -> {output.parent}"
            self.history_entries.append(entry)
            self.history_list.insert(tk.END, entry)
        if report_paths is not None:
            for report_path in report_paths:
                entry = f"REP {report_path.name} -> {report_path.parent}"
                self.history_entries.append(entry)
                self.history_list.insert(tk.END, entry)
        for error in errors[:25]:
            entry = f"ERR {error}"
            self.history_entries.append(entry)
            self.history_list.insert(tk.END, entry)
            append_log(entry)
        self.history_list.yview_moveto(1)
        self._save_settings()
        self.save_session(silent=True)
        self.conversion_stats_info.set(
            f"Estadisticas: entrada {format_size(input_bytes)} | salida {format_size(output_bytes)} | generados {converted} | errores {len(errors)}"
        )

        if cancelled:
            self.status.set(f"Cancelado. Generados: {converted}. Errores: {len(errors)}. {summary}")
            self.batch_summary_info.set(f"Ahorro total: {summary}")
            self.throughput_info.set("Conversion cancelada.")
            append_log(f"Conversion cancelada: generados={converted}, errores={len(errors)}, {summary}")
            messagebox.showinfo(APP_NAME, f"Conversion cancelada.\nArchivos generados: {converted}\n{summary}")
        elif errors:
            self.status.set(f"Generados: {converted}. Errores: {len(errors)}. {summary}")
            self.batch_summary_info.set(f"Ahorro total: {summary}")
            self.throughput_info.set(f"Errores reintentables: {len(self.last_failed_files)}")
            append_log(f"Conversion terminada con errores: generados={converted}, errores={len(errors)}, {summary}")
            if options.notify_on_done:
                self._notify_done("Converter", f"Termino con {len(errors)} error(es).")
            messagebox.showwarning(APP_NAME, "Algunas imagenes no se pudieron convertir:\n\n" + "\n".join(errors[:10]))
        else:
            self.status.set(f"Listo. Generados: {converted}. {summary}")
            self.batch_summary_info.set(f"Ahorro total: {summary}")
            self.throughput_info.set("Conversion terminada sin errores.")
            append_log(f"Conversion terminada: generados={converted}, {summary}")
            if options.notify_on_done:
                self._notify_done("Converter", f"Conversion terminada. Generados: {converted}.")
            messagebox.showinfo(APP_NAME, f"Conversion terminada.\nArchivos generados: {converted}\n{summary}")
        if not cancelled and outputs and self.open_output_when_done.get():
            self.open_output_dir()

    def _notify_done(self, title: str, body: str) -> None:
        try:
            if os.name == "nt":
                import ctypes

                ctypes.windll.user32.MessageBeep(0x40)
            self.bell()
            self.lift()
            self.attributes("-topmost", True)
            self.after(1000, lambda: self.attributes("-topmost", False))
        except Exception:
            pass
        append_log(f"Notificacion: {title} - {body}")

    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self.status.set(text))

    def _set_progress(self, value: float) -> None:
        self.after(0, lambda: self.progress.set(value))

    def _set_throughput(self, text: str) -> None:
        self.after(0, lambda: self.throughput_info.set(text))


if __name__ == "__main__":
    if any(argument.startswith("--") for argument in sys.argv[1:]):
        raise SystemExit(run_cli(sys.argv[1:]))
    app = ImageConverterApp(restore_session=True)
    startup_paths = [Path(argument) for argument in sys.argv[1:] if argument.strip()]
    if startup_paths:
        app.after(350, lambda: app._add_drop_paths(startup_paths))
    app.mainloop()
