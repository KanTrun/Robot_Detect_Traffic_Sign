"""
Class Filter and Organization Script
Selects 15 Vietnamese traffic sign classes from GTSRB dataset.
"""

import shutil
import os
from pathlib import Path

# Selected classes based on Vietnamese traffic signs
SELECTED_CLASSES = {
    0: "speed_limit_20",
    1: "speed_limit_30",
    2: "speed_limit_50",
    14: "stop",
    17: "no_entry",
    25: "road_work",
    28: "children_crossing",
    31: "pedestrian_crossing",
    33: "turn_right_ahead",
    34: "turn_left_ahead",
    35: "ahead_only",
    38: "keep_right",
    39: "keep_left",
    40: "roundabout",
    41: "end_restriction"
}

IMAGES_PER_CLASS = 200

def filter_classes():
    """Filter and copy selected classes from GTSRB dataset."""
    project_root = Path(__file__).parent.parent
    source_dir = project_root / "data" / "gtsrb_raw" / "Train"
    target_dir = project_root / "data" / "gtsrb_filtered"

    if not source_dir.exists():
        print(f"❌ Error: Source directory not found: {source_dir}")
        print("Please run 'python scripts/download_gtsrb.py' first")
        return

    print(f"Filtering {len(SELECTED_CLASSES)} classes from GTSRB dataset...")
    print(f"Target: {IMAGES_PER_CLASS} images per class\n")

    # Create target directory
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    total_copied = 0

    for class_id, class_name in SELECTED_CLASSES.items():
        src_class_dir = source_dir / f"{class_id:05d}"
        dst_class_dir = target_dir / class_name

        if not src_class_dir.exists():
            print(f"⚠️  Warning: Class {class_id} not found in source")
            continue

        # Get all images in class
        images = sorted(src_class_dir.glob("*.ppm"))

        if len(images) < IMAGES_PER_CLASS:
            print(f"⚠️  Warning: Class {class_id} has only {len(images)} images (need {IMAGES_PER_CLASS})")
            images_to_copy = images
        else:
            images_to_copy = images[:IMAGES_PER_CLASS]

        # Create target class directory
        dst_class_dir.mkdir(parents=True, exist_ok=True)

        # Copy images
        for img_path in images_to_copy:
            shutil.copy2(img_path, dst_class_dir / img_path.name)

        copied_count = len(images_to_copy)
        total_copied += copied_count

        print(f"✓ Class {class_id:2d} ({class_name:25s}): {copied_count:3d} images")

    print(f"\n✅ Filtering complete!")
    print(f"Total images copied: {total_copied}")
    print(f"Classes: {len(SELECTED_CLASSES)}")
    print(f"Average per class: {total_copied / len(SELECTED_CLASSES):.1f}")
    print(f"\nNext step: Run 'python scripts/convert_images.py' to convert PPM to JPEG")

if __name__ == "__main__":
    filter_classes()
