import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app import (
    ConversionOptions,
    build_output_path,
    combine_images_to_pdf,
    convert_image_optimized,
    flatten_alpha,
    resize_image,
)


def make_options(**overrides):
    values = {
        "output_format": "WEBP",
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
        "overwrite": False,
        "combine_pdf": False,
        "target_size_enabled": False,
        "target_size_kb": None,
        "max_workers": 1,
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


if __name__ == "__main__":
    unittest.main()
