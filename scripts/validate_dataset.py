"""
Dataset Validation Script
Validates dataset integrity, class balance, and scene leakage across train/val/test.
"""

from pathlib import Path

import pandas as pd
from PIL import Image

IMAGE_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.ppm", "*.JPG", "*.JPEG", "*.PNG", "*.PPM")
TARGET_CLASSES = {"stop", "speed_limit", "warning", "other_reg", "zz_no_sign"}


def _scene_id_from_name(filename: str) -> str:
    stem = Path(filename).stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return stem


def _validate_image(img_path: Path) -> bool:
    try:
        with Image.open(img_path) as img:
            img.verify()
        return True
    except Exception:
        return False


def _scan_split(split_name: str, split_dir: Path):
    rows = []
    corrupted = []

    for class_dir in sorted(split_dir.iterdir()):
        if not class_dir.is_dir():
            continue

        class_name = class_dir.name
        images = []
        seen = set()
        for pattern in IMAGE_PATTERNS:
            for img_path in class_dir.glob(pattern):
                key = str(img_path.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                images.append(img_path)
        images = sorted(images)

        for img_path in images:
            valid = _validate_image(img_path)
            row = {
                "split": split_name,
                "class_name": class_name,
                "filename": img_path.name,
                "scene_id": _scene_id_from_name(img_path.name),
                "valid": valid,
            }
            rows.append(row)
            if not valid:
                corrupted.append(str(img_path))

    return rows, corrupted


def _print_split_overview(df: pd.DataFrame):
    print("\n" + "=" * 72)
    print("SPLIT/CLASS OVERVIEW")
    print("=" * 72)

    summary = (
        df.groupby(["split", "class_name"])["valid"]
        .agg(total="count", valid="sum")
        .reset_index()
    )
    summary["corrupted"] = summary["total"] - summary["valid"]
    print(summary.to_string(index=False))

    print("\n" + "-" * 72)
    split_totals = (
        summary.groupby("split")[["total", "valid", "corrupted"]].sum().reset_index()
    )
    print(split_totals.to_string(index=False))


def _print_balance_report(df: pd.DataFrame):
    print("\n" + "=" * 72)
    print("CLASS BALANCE CHECK")
    print("=" * 72)

    valid_df = df[df["valid"]]
    pivot = valid_df.pivot_table(
        index="class_name",
        columns="split",
        values="filename",
        aggfunc="count",
        fill_value=0,
    ).reset_index()

    for col in ["train", "val", "test"]:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot["total"] = pivot["train"] + pivot["val"] + pivot["test"]
    print(pivot[["class_name", "train", "val", "test", "total"]].to_string(index=False))

    observed = set(valid_df["class_name"].unique())
    missing = sorted(TARGET_CLASSES - observed)
    unexpected = sorted(observed - TARGET_CLASSES)

    if missing:
        print(f"\n[WARN] Missing expected classes: {missing}")
    else:
        print("\n[OK] All expected classes are present")

    if unexpected:
        print(f"[WARN] Unexpected classes found: {unexpected}")


def _print_scene_leakage(df: pd.DataFrame):
    print("\n" + "=" * 72)
    print("SCENE LEAKAGE CHECK")
    print("=" * 72)

    valid_df = df[df["valid"]]

    leakage_rows = []
    classes = sorted(valid_df["class_name"].unique())
    for class_name in classes:
        subset = valid_df[valid_df["class_name"] == class_name]

        scenes = {
            split: set(subset[subset["split"] == split]["scene_id"].tolist())
            for split in ["train", "val", "test"]
        }

        for a, b in [("train", "val"), ("train", "test"), ("val", "test")]:
            overlap = scenes[a].intersection(scenes[b])
            if overlap:
                leakage_rows.append(
                    {
                        "class_name": class_name,
                        "pair": f"{a}-{b}",
                        "overlap_count": len(overlap),
                    }
                )

    if not leakage_rows:
        print("[OK] No scene leakage detected across train/val/test")
        return

    leak_df = pd.DataFrame(leakage_rows)
    print("[WARN] Scene leakage detected:")
    print(leak_df.to_string(index=False))


def validate_dataset():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    train_dir = data_dir / "train"
    val_dir = data_dir / "val"
    test_dir = data_dir / "test"
    report_path = data_dir / "dataset_validation_report.csv"

    required = [train_dir, val_dir, test_dir]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("[ERROR] Error: Required split directories not found")
        for m in missing:
            print(f"  - {m}")
        print("Please run 'python scripts/split_dataset.py' first")
        return

    split_dirs = [("train", train_dir), ("val", val_dir), ("test", test_dir)]

    print("Validating dataset integrity, balance, and leakage...\n")

    all_rows = []
    all_corrupted = []

    for split_name, split_dir in split_dirs:
        rows, corrupted = _scan_split(split_name, split_dir)
        all_rows.extend(rows)
        all_corrupted.extend(corrupted)

    if not all_rows:
        print("[ERROR] No images found in dataset splits")
        return

    df = pd.DataFrame(all_rows)

    _print_split_overview(df)
    _print_balance_report(df)
    _print_scene_leakage(df)

    df.to_csv(report_path, index=False)

    print("\n" + "=" * 72)
    print("VALIDATION COMPLETE")
    print("=" * 72)
    print(f"Total images scanned: {len(df)}")
    print(f"Valid images: {int(df['valid'].sum())}")
    print(f"Corrupted images: {len(all_corrupted)}")
    print(f"Report CSV: {report_path}")

    if all_corrupted:
        print("\n[WARN] Corrupted files:")
        for p in all_corrupted[:20]:
            print(f"  - {p}")
        if len(all_corrupted) > 20:
            print(f"  ... and {len(all_corrupted) - 20} more")
    else:
        print("\n[OK] All scanned images are valid")


if __name__ == "__main__":
    validate_dataset()
