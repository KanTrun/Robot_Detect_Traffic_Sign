"""
GTSRB Dataset Download Script
Downloads German Traffic Sign Recognition Benchmark dataset from Kaggle.
"""

import kagglehub
import os
import shutil
from pathlib import Path

def download_gtsrb():
    """Download GTSRB dataset using kagglehub."""
    print("Starting GTSRB dataset download...")
    print("This may take 10-15 minutes depending on your internet speed (1.2GB)")

    try:
        # Download dataset
        path = kagglehub.dataset_download("meowmeowmeowmeowmeow/gtsrb-german-traffic-sign")
        print(f"\n✓ Dataset downloaded to: {path}")

        # Get project root
        project_root = Path(__file__).parent.parent
        target_dir = project_root / "data" / "gtsrb_raw"

        # Copy to project directory
        print(f"\nCopying dataset to project directory: {target_dir}")
        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.copytree(path, target_dir)
        print(f"✓ Dataset copied to: {target_dir}")

        # Verify structure
        train_dir = target_dir / "Train"
        test_dir = target_dir / "Test"

        if train_dir.exists():
            num_classes = len(list(train_dir.iterdir()))
            print(f"\n✓ Verification successful:")
            print(f"  - Train directory: {num_classes} classes found")

        if test_dir.exists():
            print(f"  - Test directory: exists")

        print("\n✅ Download complete!")
        print(f"Next step: Run 'python scripts/filter_classes.py' to select 15 Vietnamese sign classes")

        return str(target_dir)

    except Exception as e:
        print(f"\n❌ Error downloading dataset: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure you have a Kaggle account")
        print("2. Download kaggle.json from Kaggle Account Settings → API")
        print("3. Place kaggle.json in ~/.kaggle/ (Linux/Mac) or C:\\Users\\<username>\\.kaggle\\ (Windows)")
        print("4. Install kagglehub: pip install kagglehub")
        raise

if __name__ == "__main__":
    download_gtsrb()
