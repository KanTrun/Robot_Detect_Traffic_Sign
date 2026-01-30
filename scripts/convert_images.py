"""
Image Conversion Script
Converts PPM images to JPEG and resizes to 96x96 for Edge Impulse.
"""

from PIL import Image
from pathlib import Path
import os

TARGET_SIZE = (96, 96)
JPEG_QUALITY = 95

def convert_images():
    """Convert PPM images to JPEG format and resize."""
    project_root = Path(__file__).parent.parent
    filtered_dir = project_root / "data" / "gtsrb_filtered"

    if not filtered_dir.exists():
        print(f"❌ Error: Filtered directory not found: {filtered_dir}")
        print("Please run 'python scripts/filter_classes.py' first")
        return

    print(f"Converting PPM images to JPEG {TARGET_SIZE[0]}x{TARGET_SIZE[1]}...")
    print(f"Quality: {JPEG_QUALITY}\n")

    converted_count = 0
    error_count = 0

    # Process all PPM files
    for ppm_path in filtered_dir.rglob("*.ppm"):
        try:
            # Open and convert image
            img = Image.open(ppm_path)
            img = img.convert("RGB")
            img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)

            # Save as JPEG
            jpg_path = ppm_path.with_suffix(".jpg")
            img.save(jpg_path, "JPEG", quality=JPEG_QUALITY)

            # Delete original PPM
            ppm_path.unlink()

            converted_count += 1

            if converted_count % 100 == 0:
                print(f"  Converted {converted_count} images...")

        except Exception as e:
            print(f"⚠️  Error converting {ppm_path.name}: {e}")
            error_count += 1

    print(f"\n✅ Conversion complete!")
    print(f"Successfully converted: {converted_count} images")

    if error_count > 0:
        print(f"⚠️  Errors: {error_count} images")

    print(f"\nNext step: Run 'python scripts/split_dataset.py' to create train/test split")

if __name__ == "__main__":
    convert_images()
