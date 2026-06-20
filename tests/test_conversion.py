import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from PIL import Image
from PIL import ImageSequence

import app as converter_app
from app import (
    ConversionOptions,
    build_output_path,
    combine_images_to_pdf,
    create_outputs_zip,
    convert_image_optimized,
    describe_image,
    estimate_final_output_size,
    file_signature,
    format_estimate_cell,
    format_conversion_summary,
    format_output_estimate_summary,
    flatten_alpha,
    image_to_svg_bytes,
    is_raw_image,
    is_supported_image,
    parse_output_formats,
    parse_version,
    pdf_page_dimensions,
    remove_background_from_image,
    render_output_stem,
    run_cli,
    resize_image,
    write_conversion_reports,
    ImageConverterApp,
    apply_square_canvas,
)


def make_options(**overrides):
    values = {
        "output_format": "WEBP",
        "output_formats": ("WEBP",),
        "quality": 82,
        "output_dir": Path("."),
        "resize_enabled": False,
        "width": None,
        "height": None,
        "keep_aspect": True,
        "background": (255, 255, 255),
        "naming_mode": "Conservar",
        "prefix": "",
        "suffix": "",
        "naming_template": "{name}_{format}",
        "overwrite": False,
        "combine_pdf": False,
        "target_size_enabled": False,
        "target_size_kb": None,
        "max_workers": 1,
        "strip_metadata": True,
        "open_output_when_done": False,
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
        "crop_left": 0,
        "crop_top": 0,
        "crop_right": 0,
        "crop_bottom": 0,
        "square_canvas": False,
        "canvas_size": None,
        "canvas_transparent": True,
        "brightness": 0,
        "contrast": 0,
        "saturation": 0,
        "large_file_rule_enabled": False,
        "large_file_threshold_kb": None,
        "large_file_quality": 72,
        "pdf_page_size": "Original",
        "pdf_auto_orientation": True,
        "create_zip": False,
        "notify_on_done": False,
    }
    values.update(overrides)
    return ConversionOptions(**values)


class ConversionTests(unittest.TestCase):
    def test_build_output_path_reserves_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "photo.png"
            source.touch()
            options = make_options(output_dir=output_dir)
            reserved = set()

            first = build_output_path(source, output_dir, options, 1, reserved)
            second = build_output_path(source, output_dir, options, 2, reserved)

            self.assertNotEqual(first, second)
            self.assertEqual(first.name, "photo.webp")
            self.assertEqual(second.name, "photo_1.webp")

    def test_build_output_path_reserves_duplicates_when_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "photo.png"
            source.touch()
            options = make_options(output_dir=output_dir, overwrite=True)
            reserved = set()

            first = build_output_path(source, output_dir, options, 1, reserved)
            second = build_output_path(source, output_dir, options, 2, reserved)

            self.assertNotEqual(first, second)
            self.assertEqual(first.name, "photo.webp")
            self.assertEqual(second.name, "photo_1.webp")

    def test_build_output_path_keeps_folder_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            source_dir = root / "nested"
            source_dir.mkdir(parents=True)
            source = source_dir / "photo.png"
            source.touch()
            output_dir = Path(tmp) / "out"
            options = make_options(output_dir=output_dir, keep_folder_structure=True)

            output = build_output_path(source, output_dir, options, 1, source_root=root)

            self.assertEqual(output, output_dir / "nested" / "photo.webp")

    def test_render_output_stem_uses_template_tokens(self):
        source = Path("folder/photo.png")
        options = make_options(output_format="JPG", naming_mode="Plantilla", naming_template="{folder}_{name}_{index}_{format}")

        stem = render_output_stem(source, options, 7)

        self.assertEqual(stem, "folder_photo_007_jpg")

    def test_parse_version_compares_semantic_versions(self):
        self.assertGreater(parse_version("v1.10.0"), parse_version("1.2.9"))

    def test_parse_output_formats_deduplicates_and_validates(self):
        self.assertEqual(parse_output_formats("WEBP", "png, jpg, WEBP"), ("WEBP", "PNG", "JPG"))
        with self.assertRaises(ValueError):
            parse_output_formats("WEBP", "not-real")

    def test_supported_image_detects_unknown_extension_by_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            png_source = folder / "camera_export.data"
            jpeg_source = folder / "camera_export"
            Image.new("RGB", (12, 10), "green").save(png_source, format="PNG")
            Image.new("RGB", (12, 10), "blue").save(jpeg_source, format="JPEG")

            self.assertTrue(is_supported_image(png_source))
            self.assertTrue(is_supported_image(jpeg_source))

    def test_supported_image_rejects_non_image_unknown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "notes.data"
            source.write_text("not an image", encoding="utf-8")

            self.assertFalse(is_supported_image(source))

    def test_raw_extension_is_supported_input(self):
        source = Path("camera.nef")

        self.assertTrue(is_raw_image(source))
        self.assertTrue(is_supported_image(source))

    def test_describe_raw_image_uses_rawpy_sizes(self):
        class FakeRaw:
            sizes = SimpleNamespace(
                iwidth=6048,
                width=6048,
                raw_width=6080,
                iheight=4024,
                height=4024,
                raw_height=4040,
            )

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class FakeRawpy:
            @staticmethod
            def imread(_path):
                return FakeRaw()

        original_rawpy = converter_app.rawpy
        original_available = converter_app.RAWPY_AVAILABLE
        converter_app.rawpy = FakeRawpy()
        converter_app.RAWPY_AVAILABLE = True
        try:
            with tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "camera.dng"
                source.write_bytes(b"fake raw payload")

                image_format, dimensions, details, weight = describe_image(source)

            self.assertEqual(image_format, "RAW (DNG)")
            self.assertEqual(dimensions, "6048 x 4024")
            self.assertEqual(details, "RAW de camara")
            self.assertNotEqual(weight, "-")
        finally:
            converter_app.rawpy = original_rawpy
            converter_app.RAWPY_AVAILABLE = original_available

    def test_format_conversion_summary_reports_savings(self):
        self.assertIn("50.0% menos", format_conversion_summary(2000, 1000))

    def test_format_output_estimate_summary_reports_single_format(self):
        summary = format_output_estimate_summary(2000, [("WEBP", 1000)])

        self.assertIn("Peso estimado de salida", summary)
        self.assertIn("WEBP", summary)
        self.assertIn("50.0% menos", summary)

    def test_format_output_estimate_summary_reports_multiple_formats(self):
        summary = format_output_estimate_summary(2000, [("WEBP", 1000), ("PNG", 2500)])

        self.assertIn("WEBP 1000 B", summary)
        self.assertIn("PNG 2.4 KB", summary)
        self.assertIn("Total por foto 3.4 KB", summary)

    def test_format_estimate_cell_reports_single_and_multiple_formats(self):
        self.assertEqual(format_estimate_cell([("WEBP", 1024)]), "1.0 KB")
        self.assertEqual(format_estimate_cell([("WEBP", 1024), ("JPG", 2048)]), "3.0 KB total")

    def test_file_signature_matches_duplicate_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            first = folder / "first.png"
            second = folder / "second.png"
            third = folder / "third.png"
            first.write_bytes(b"same image bytes")
            second.write_bytes(b"same image bytes")
            third.write_bytes(b"different image bytes")

            self.assertEqual(file_signature(first), file_signature(second))
            self.assertNotEqual(file_signature(first), file_signature(third))

    def test_estimate_final_output_size_returns_predicted_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            Image.new("RGB", (80, 60), "purple").save(source)
            options = make_options(output_format="WEBP", output_formats=("WEBP",), output_dir=Path(tmp))

            estimated_size = estimate_final_output_size(source, options)

            self.assertGreater(estimated_size, 0)

    def test_resize_keeps_aspect_ratio(self):
        image = Image.new("RGB", (200, 100), "blue")
        options = make_options(resize_enabled=True, width=100)

        resized = resize_image(image, options)

        self.assertEqual(resized.size, (100, 50))

    def test_flatten_alpha_uses_background(self):
        image = Image.new("RGBA", (10, 10), (255, 0, 0, 0))

        flattened = flatten_alpha(image, (10, 20, 30))

        self.assertEqual(flattened.mode, "RGB")
        self.assertEqual(flattened.getpixel((0, 0)), (10, 20, 30))

    def test_square_canvas_centers_image(self):
        image = Image.new("RGBA", (20, 10), (255, 0, 0, 255))
        options = make_options(square_canvas=True, canvas_size=32, canvas_transparent=True)

        squared = apply_square_canvas(image, options)

        self.assertEqual(squared.size, (32, 32))
        self.assertEqual(squared.getpixel((0, 0))[3], 0)

    def test_remove_background_makes_edge_background_transparent(self):
        image = Image.new("RGB", (24, 24), "white")
        for x in range(8, 16):
            for y in range(8, 16):
                image.putpixel((x, y), (200, 20, 20))

        removed = remove_background_from_image(image, tolerance=24)

        self.assertEqual(removed.mode, "RGBA")
        self.assertLess(removed.getpixel((0, 0))[3], 10)
        self.assertGreater(removed.getpixel((12, 12))[3], 240)

    def test_image_to_svg_bytes_creates_svg_paths(self):
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        for x in range(2, 6):
            for y in range(2, 6):
                image.putpixel((x, y), (10, 120, 220, 255))

        payload = image_to_svg_bytes(image)

        self.assertIn(b"<svg", payload)
        self.assertIn(b"<path", payload)
        self.assertIn(b"#0a78dc", payload)

    def test_convert_image_optimized_creates_svg_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "source.png"
            destination = output_dir / "source.svg"
            Image.new("RGB", (24, 24), "navy").save(source)
            options = make_options(output_format="SVG", output_formats=("SVG",), output_dir=output_dir)

            convert_image_optimized(source, destination, options)

            self.assertTrue(destination.exists())
            self.assertIn("<svg", destination.read_text(encoding="utf-8"))

    def test_convert_image_optimized_creates_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "source.png"
            destination = output_dir / "source.webp"
            Image.new("RGBA", (80, 60), (20, 100, 220, 180)).save(source)
            options = make_options(output_dir=output_dir, target_size_enabled=True, target_size_kb=20)

            convert_image_optimized(source, destination, options)

            self.assertTrue(destination.exists())
            self.assertGreater(destination.stat().st_size, 0)

    def test_convert_image_optimized_respects_target_size_when_possible(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "source.png"
            destination = output_dir / "source.webp"
            image = Image.effect_noise((256, 256), 80).convert("RGB")
            image.save(source)
            options = make_options(output_dir=output_dir, quality=90, target_size_enabled=True, target_size_kb=30)

            convert_image_optimized(source, destination, options)

            self.assertTrue(destination.exists())
            self.assertLessEqual(destination.stat().st_size, 30 * 1024)

    def test_combine_images_to_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "source.png"
            destination = output_dir / "bundle.pdf"
            Image.new("RGB", (40, 30), "white").save(source)
            options = make_options(output_format="PDF", output_dir=output_dir, combine_pdf=True)

            combine_images_to_pdf([source], destination, options)

            self.assertTrue(destination.exists())
            self.assertGreater(destination.stat().st_size, 0)

    def test_pdf_page_dimensions_uses_auto_landscape(self):
        image = Image.new("RGB", (400, 200), "white")
        options = make_options(output_format="PDF", output_formats=("PDF",), pdf_page_size="A4", pdf_auto_orientation=True)

        self.assertEqual(pdf_page_dimensions(image, options), (3508, 2480))

    def test_animated_gif_preserves_frame_durations(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            source = output_dir / "source.gif"
            destination = output_dir / "out.gif"
            frames = [Image.new("RGB", (16, 16), "red"), Image.new("RGB", (16, 16), "blue")]
            frames[0].save(source, save_all=True, append_images=[frames[1]], duration=[40, 220], loop=0)
            options = make_options(output_format="GIF", output_formats=("GIF",), output_dir=output_dir)

            convert_image_optimized(source, destination, options)

            with Image.open(destination) as image:
                durations = [frame.info.get("duration") for frame in ImageSequence.Iterator(image)]
            self.assertEqual(durations, [40, 220])

    def test_create_outputs_zip_adds_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            first = output_dir / "a.webp"
            second = output_dir / "b.webp"
            destination = output_dir / "bundle.zip"
            first.write_bytes(b"one")
            second.write_bytes(b"two")

            create_outputs_zip([first, second], destination)

            self.assertTrue(destination.exists())
            self.assertGreater(destination.stat().st_size, 0)

    def test_write_conversion_reports_creates_txt_csv_and_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            output = output_dir / "out.webp"
            output.write_bytes(b"123")

            txt_path, csv_path, html_path = write_conversion_reports(output_dir, [output], ["bad file"], 1, False, 1000, 3)

            self.assertTrue(txt_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertTrue(html_path.exists())
            self.assertIn("out.webp", txt_path.read_text(encoding="utf-8"))
            self.assertIn("bad file", csv_path.read_text(encoding="utf-8"))
            self.assertIn("Reporte Converter", html_path.read_text(encoding="utf-8"))

    def test_run_cli_converts_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.png"
            output_dir = folder / "out"
            Image.new("RGB", (20, 12), "orange").save(source)

            exit_code = run_cli([str(source), "--to", "webp", "--output", str(output_dir), "--quality", "80"])

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "source.webp").exists())

    def test_disabled_size_and_target_controls_are_ignored(self):
        app = ImageConverterApp()
        try:
            app.withdraw()
            app.output_format.set("WEBP")
            app.extra_formats.set("")
            app.background_hex.set("#ffffff")
            app.resize_enabled.set(False)
            app.resize_width.set("bad")
            app.target_size_enabled.set(False)
            app.target_size_kb.set("bad")

            options = app._read_options()

            self.assertIsNotNone(options)
            self.assertIsNone(options.width)
            self.assertIsNone(options.target_size_kb)
        finally:
            app.destroy()

    def test_file_tree_updates_status_and_estimate_columns_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            Image.new("RGB", (16, 16), "teal").save(source)
            source = source.resolve()
            app = ImageConverterApp()
            try:
                app.withdraw()
                app.files = [source]
                app.metadata_cache[source] = describe_image(source)
                app.file_status[source] = "Pendiente"
                app.file_estimates[source] = "Pendiente"
                app._refresh_file_tree()

                app._set_file_status(source, "OK")
                app._set_file_estimate(app.file_estimate_request_id, source, "1.0 KB")

                values = app.file_tree.item(str(source), "values")
                self.assertEqual(values[1], "OK")
                self.assertEqual(values[5], "1.0 KB")
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
