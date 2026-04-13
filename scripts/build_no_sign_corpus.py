"""
Build no-sign corpus from GTSRB Test split.
Creates reproducible, balanced no-sign pool excluding the 15 in-scope classes.
"""

import csv
import random
import shutil
from pathlib import Path

# 15 in-scope classes used by project
IN_SCOPE_CLASS_IDS = {0, 1, 2, 14, 17, 25, 28, 31, 33, 34, 35, 38, 39, 40, 41}
TARGET_NO_SIGN_IMAGES = 1200
RANDOM_SEED = 42


def build_no_sign_corpus(target_count: int = TARGET_NO_SIGN_IMAGES, seed: int = RANDOM_SEED):
    project_root = Path(__file__).parent.parent
    source_test_dir = project_root / "data" / "gtsrb_raw" / "Test"
    source_test_csv = project_root / "data" / "gtsrb_raw" / "Test.csv"
    target_dir = project_root / "data" / "no_sign"
    manifest_path = project_root / "data" / "no_sign_manifest.csv"

    if not source_test_dir.exists() or not source_test_csv.exists():
        print("[ERROR] Missing GTSRB test source. Run 'python scripts/download_gtsrb.py' first")
        return

    print("Building no-sign corpus from GTSRB Test split...")
    print(f"Target images: {target_count}")
    print(f"Random seed: {seed}\n")

    candidates = []
    with source_test_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            class_id = int(row["ClassId"])
            if class_id in IN_SCOPE_CLASS_IDS:
                continue
            file_name = row["Path"].split("/")[-1]
            img_path = source_test_dir / file_name
            if img_path.exists():
                candidates.append((img_path, class_id))

    if not candidates:
        print("[ERROR] No no-sign candidates found in GTSRB Test.csv")
        return

    print(f"Candidate pool (out-of-scope classes): {len(candidates)} images")

    rng = random.Random(seed)
    if len(candidates) > target_count:
        selected = rng.sample(candidates, target_count)
    else:
        selected = candidates
        if len(candidates) < target_count:
            print(f"[WARN] Candidate pool smaller than target: {len(candidates)} < {target_count}")

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    class_counts = {}

    for idx, (src_path, class_id) in enumerate(sorted(selected, key=lambda x: x[0].name), start=1):
        dst_name = f"nosign_{idx:05d}_{src_path.name}"
        dst_path = target_dir / dst_name
        shutil.copy2(src_path, dst_path)

        class_counts[class_id] = class_counts.get(class_id, 0) + 1
        manifest_rows.append(
            {
                "source": "gtsrb_test_out_of_scope",
                "filename": dst_name,
                "orig_filename": src_path.name,
                "class_id": class_id,
                "is_no_sign": 1,
            }
        )

    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source", "filename", "orig_filename", "class_id", "is_no_sign"],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    print("\n[OK] No-sign corpus build complete")
    print(f"Output dir: {target_dir}")
    print(f"Manifest:   {manifest_path}")
    print(f"Selected:   {len(selected)}")
    print(f"Unique out-of-scope classes: {len(class_counts)}")


if __name__ == "__main__":
    build_no_sign_corpus()
