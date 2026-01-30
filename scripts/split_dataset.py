"""
Dataset Split Script
Splits filtered dataset into train (80%) and test (20%) sets.
"""

import shutil
from pathlib import Path
from sklearn.model_selection import train_test_split
import random

TRAIN_RATIO = 0.8
RANDOM_SEED = 42

def split_dataset():
    """Split dataset into train and test sets."""
    project_root = Path(__file__).parent.parent
    filtered_dir = project_root / "data" / "gtsrb_filtered"
    train_dir = project_root / "data" / "train"
    test_dir = project_root / "data" / "test"

    if not filtered_dir.exists():
        print(f"❌ Error: Filtered directory not found: {filtered_dir}")
        print("Please run the previous scripts first")
        return

    print(f"Splitting dataset into train ({TRAIN_RATIO*100:.0f}%) and test ({(1-TRAIN_RATIO)*100:.0f}%)...")
    print(f"Random seed: {RANDOM_SEED}\n")

    # Create train and test directories
    if train_dir.exists():
        shutil.rmtree(train_dir)
    if test_dir.exists():
        shutil.rmtree(test_dir)

    train_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    total_train = 0
    total_test = 0

    # Set random seed
    random.seed(RANDOM_SEED)

    # Process each class
    for class_dir in sorted(filtered_dir.iterdir()):
        if not class_dir.is_dir():
            continue

        class_name = class_dir.name

        # Get all images
        images = list(class_dir.glob("*.jpg"))

        if not images:
            print(f"⚠️  Warning: No JPEG images found in {class_name}")
            continue

        # Split images
        train_images, test_images = train_test_split(
            images,
            train_size=TRAIN_RATIO,
            random_state=RANDOM_SEED,
            shuffle=True
        )

        # Create class directories
        train_class_dir = train_dir / class_name
        test_class_dir = test_dir / class_name

        train_class_dir.mkdir(parents=True, exist_ok=True)
        test_class_dir.mkdir(parents=True, exist_ok=True)

        # Copy train images
        for img_path in train_images:
            shutil.copy2(img_path, train_class_dir / img_path.name)

        # Copy test images
        for img_path in test_images:
            shutil.copy2(img_path, test_class_dir / img_path.name)

        total_train += len(train_images)
        total_test += len(test_images)

        print(f"✓ {class_name:25s}: train={len(train_images):3d}, test={len(test_images):3d}")

    print(f"\n✅ Split complete!")
    print(f"Total train: {total_train} images")
    print(f"Total test:  {total_test} images")
    print(f"Total:       {total_train + total_test} images")
    print(f"\nDataset ready for Edge Impulse upload!")
    print(f"Next step: Run 'python scripts/validate_dataset.py' to verify")

if __name__ == "__main__":
    split_dataset()
