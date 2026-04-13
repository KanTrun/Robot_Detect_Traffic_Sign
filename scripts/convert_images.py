"""
Image Conversion Script
Converts cropped sign images to JPEG 96x96 for downstream split/training.
"""

from pathlib import Path

from PIL import Image

TARGET_SIZE = (96, 96)
JPEG_QUALITY = 95
IMAGE_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.ppm", "*.JPG", "*.JPEG", "*.PNG", "*.PPM")


def _collect_images(root: Path):
    paths = []
    seen = set()
    for pattern in IMAGE_PATTERNS:
        for p in root.rglob(pattern):
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            paths.append(p)
    return sorted(paths)


def convert_images():
    """Convert images to 96x96 JPEG in-place."""
    project_root = Path(__file__).parent.parent
    filtered_dir = project_root / "data" / "gtsrb_filtered"

    if not filtered_dir.exists():
        print(f"[ERROR] Filtered directory not found: {filtered_dir}")
        print("Please run 'python scripts/filter_classes.py' first")
        return

    print(f"Converting images to JPEG {TARGET_SIZE[0]}x{TARGET_SIZE[1]}...")
    print(f"Quality: {JPEG_QUALITY}\n")

    converted_count = 0
    error_count = 0

    image_paths = _collect_images(filtered_dir)
    for src_path in image_paths:
        try:
            with Image.open(src_path) as img:
                rgb = img.convert("RGB")
                rgb = rgb.resize(TARGET_SIZE, Image.Resampling.LANCZOS)

            jpg_path = src_path.with_suffix(".jpg")
            rgb.save(jpg_path, "JPEG", quality=JPEG_QUALITY)

            if src_path.resolve() != jpg_path.resolve():
                src_path.unlink()

            converted_count += 1
            if converted_count % 200 == 0:
                print(f"  Converted {converted_count} images...")

        except Exception as e:
            print(f"[WARN] Error converting {src_path.name}: {e}")
            error_count += 1

    print("\n[OK] Conversion complete!")
    print(f"Successfully converted: {converted_count} images")
    if error_count > 0:
        print(f"[WARN] Errors: {error_count} images")

    print("\nNext step: Run 'python scripts/split_dataset.py' to create train/val/test split")


if __name__ == "__main__":
    convert_images()
