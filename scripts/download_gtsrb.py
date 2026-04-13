"""
LISA Dataset Staging Script (LISA-only pipeline).

Backward-compatible filename: download_gtsrb.py
Usage:
  python scripts/download_gtsrb.py --source "D:/path/to/lisa_dataset_or_zip"
"""

import argparse
import shutil
import zipfile
from pathlib import Path

IMAGE_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.ppm", "*.JPG", "*.JPEG", "*.PNG", "*.PPM")


def _count_images(root: Path) -> int:
    total = 0
    for pattern in IMAGE_PATTERNS:
        total += len(list(root.rglob(pattern)))
    return total


def stage_lisa_dataset(source: Path, target_dir: Path) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if source.is_file():
        if source.suffix.lower() != ".zip":
            raise ValueError("Only .zip source files are supported. Use --source as folder or .zip")

        print(f"[INFO] Extracting ZIP: {source}")
        with zipfile.ZipFile(source, "r") as zf:
            zf.extractall(target_dir)
    else:
        print(f"[INFO] Copying directory: {source}")
        shutil.copytree(source, target_dir, dirs_exist_ok=True)

    image_count = _count_images(target_dir)
    csv_files = list(target_dir.rglob("*.csv"))

    print(f"[OK] LISA dataset staged at: {target_dir}")
    print(f"[OK] Images found: {image_count}")
    print(f"[OK] CSV files found: {len(csv_files)}")
    if csv_files:
        preview = "\n".join(f"  - {p}" for p in csv_files[:10])
        print("[INFO] CSV preview:\n" + preview)

    if image_count == 0:
        print("[WARN] No images found after staging. Check your source dataset structure.")

    print("\nNext step: run 'python scripts/filter_classes.py' to crop and map 4 classes")
    return target_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage LISA dataset into data/lisa_raw")
    parser.add_argument(
        "--source",
        required=True,
        help="Path to LISA dataset folder or .zip file",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    project_root = Path(__file__).parent.parent
    target_dir = project_root / "data" / "lisa_raw"

    try:
        stage_lisa_dataset(Path(args.source), target_dir)
    except Exception as e:
        print(f"[ERROR] {e}")
        raise


if __name__ == "__main__":
    main()
