"""
Dataset Validation Script
Validates dataset integrity, checks for corrupted images, and generates statistics.
"""

from PIL import Image
from pathlib import Path
import pandas as pd

def validate_dataset():
    """Validate dataset and generate statistics."""
    project_root = Path(__file__).parent.parent
    train_dir = project_root / "data" / "train"
    test_dir = project_root / "data" / "test"

    if not train_dir.exists() or not test_dir.exists():
        print(f"❌ Error: Train or test directory not found")
        print("Please run 'python scripts/split_dataset.py' first")
        return

    print("Validating dataset...\n")

    # Validate both sets
    for dataset_name, dataset_dir in [("TRAIN", train_dir), ("TEST", test_dir)]:
        print(f"\n{'='*60}")
        print(f"{dataset_name} SET VALIDATION")
        print(f"{'='*60}\n")

        total_images = 0
        corrupted_images = 0
        class_stats = []

        for class_dir in sorted(dataset_dir.iterdir()):
            if not class_dir.is_dir():
                continue

            class_name = class_dir.name
            images = list(class_dir.glob("*.jpg"))
            valid_count = 0
            invalid_count = 0

            # Check each image
            for img_path in images:
                try:
                    with Image.open(img_path) as img:
                        img.verify()
                    valid_count += 1
                except Exception as e:
                    print(f"⚠️  Corrupted: {img_path.name} - {e}")
                    invalid_count += 1

            total_images += valid_count
            corrupted_images += invalid_count

            class_stats.append({
                'Class': class_name,
                'Valid': valid_count,
                'Corrupted': invalid_count,
                'Total': valid_count + invalid_count
            })

        # Create DataFrame
        df = pd.DataFrame(class_stats)

        print(df.to_string(index=False))
        print(f"\n{'-'*60}")
        print(f"Total valid images:     {total_images}")
        print(f"Total corrupted images: {corrupted_images}")
        print(f"Total classes:          {len(class_stats)}")
        print(f"Average per class:      {total_images / len(class_stats):.1f}")

        if corrupted_images == 0:
            print(f"\n✅ All {dataset_name.lower()} images are valid!")
        else:
            print(f"\n⚠️  Found {corrupted_images} corrupted images in {dataset_name.lower()} set")

    # Final summary
    print(f"\n{'='*60}")
    print(f"VALIDATION COMPLETE")
    print(f"{'='*60}\n")

    train_count = sum([len(list(d.glob("*.jpg"))) for d in train_dir.iterdir() if d.is_dir()])
    test_count = sum([len(list(d.glob("*.jpg"))) for d in test_dir.iterdir() if d.is_dir()])

    print(f"✓ Train images: {train_count}")
    print(f"✓ Test images:  {test_count}")
    print(f"✓ Total images: {train_count + test_count}")
    print(f"\n✅ Dataset is ready for Edge Impulse upload!")
    print(f"\nUpload instructions:")
    print(f"  1. Go to https://studio.edgeimpulse.com")
    print(f"  2. Create new project: 'Traffic Sign Recognition ESP32'")
    print(f"  3. Upload train folder: {train_dir}")
    print(f"  4. Upload test folder: {test_dir} (mark as 'Test data')")

if __name__ == "__main__":
    validate_dataset()
