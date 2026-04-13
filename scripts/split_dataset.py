"""
Dataset Split Script
Splits filtered dataset into train/val/test with reproducible, scene-aware grouping.
"""

import csv
import hashlib
import random
import shutil
from pathlib import Path

TRAIN_RATIO = 0.7
VAL_RATIO = 0.15
TEST_RATIO = 0.15
RANDOM_SEED = 42
NO_SIGN_CLASS_NAMES = {"no_sign", "zz_no_sign", "_background_"}
IMAGE_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.ppm", "*.JPG", "*.JPEG", "*.PNG", "*.PPM")


def _collect_images(class_dir: Path):
    images = []
    seen = set()
    for pattern in IMAGE_PATTERNS:
        for img_path in class_dir.glob(pattern):
            key = str(img_path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            images.append(img_path)
    return sorted(images)


def _safe_copy_with_unique_name(src_path: Path, target_dir: Path, used_names: set):
    base_name = src_path.name
    candidate = base_name
    renamed = False
    if candidate.lower() in used_names:
        stem = src_path.stem
        suffix = src_path.suffix
        token = hashlib.sha1(str(src_path.resolve()).encode("utf-8")).hexdigest()[:10]
        candidate = f"{stem}_{token}{suffix}"
        serial = 1
        while candidate.lower() in used_names:
            candidate = f"{stem}_{token}_{serial}{suffix}"
            serial += 1
        renamed = True
    used_names.add(candidate.lower())
    shutil.copy2(src_path, target_dir / candidate)
    return candidate, renamed


def _split_flat_images(images, rng):
    shuffled = images[:]
    rng.shuffle(shuffled)
    n = len(shuffled)

    if n == 0:
        return [], [], []

    n_train = int(round(n * TRAIN_RATIO))
    n_val = int(round(n * VAL_RATIO))
    n_test = n - n_train - n_val

    min_required = min(3, n)

    if n_train < 1 and min_required >= 1:
        n_train = 1
    if n_val < 1 and min_required >= 2:
        n_val = 1
    if n_test < 1 and min_required >= 3:
        n_test = 1

    while n_train + n_val + n_test > n:
        if n_train >= n_val and n_train >= n_test and n_train > 1:
            n_train -= 1
        elif n_val >= n_test and n_val > 1:
            n_val -= 1
        elif n_test > 1:
            n_test -= 1
        else:
            break

    while n_train + n_val + n_test < n:
        deficits = {
            "train": n * TRAIN_RATIO - n_train,
            "val": n * VAL_RATIO - n_val,
            "test": n * TEST_RATIO - n_test,
        }
        chosen = max(deficits.items(), key=lambda kv: kv[1])[0]
        if chosen == "train":
            n_train += 1
        elif chosen == "val":
            n_val += 1
        else:
            n_test += 1

    train_images = shuffled[:n_train]
    val_images = shuffled[n_train:n_train + n_val]
    test_images = shuffled[n_train + n_val:n_train + n_val + n_test]
    return train_images, val_images, test_images


def _scene_id_from_stem(stem: str):
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return stem


def _group_by_scene(image_paths):
    groups = {}
    for p in image_paths:
        scene_id = _scene_id_from_stem(p.stem)
        groups.setdefault(scene_id, []).append(p)
    return groups


def _split_groups(groups, rng):
    scene_items = [(scene_id, len(paths)) for scene_id, paths in groups.items()]
    rng.shuffle(scene_items)
    scene_items.sort(key=lambda item: item[1], reverse=True)

    total_images = sum(size for _, size in scene_items)
    target_train = max(1, int(round(total_images * TRAIN_RATIO)))
    target_val = max(1, int(round(total_images * VAL_RATIO)))
    target_test = max(1, total_images - target_train - target_val)

    while target_train + target_val + target_test > total_images:
        if target_train >= target_val and target_train >= target_test and target_train > 1:
            target_train -= 1
        elif target_val >= target_test and target_val > 1:
            target_val -= 1
        elif target_test > 1:
            target_test -= 1
        else:
            break

    targets = {"train": target_train, "val": target_val, "test": target_test}
    counts = {"train": 0, "val": 0, "test": 0}
    split_ids = {"train": set(), "val": set(), "test": set()}

    for split_name, (scene_id, size) in zip(["train", "val", "test"], scene_items[:3]):
        split_ids[split_name].add(scene_id)
        counts[split_name] += size

    for scene_id, size in scene_items[3:]:
        deficits = {name: targets[name] - counts[name] for name in ["train", "val", "test"]}
        max_deficit = max(deficits.values())
        candidates = [name for name, deficit in deficits.items() if deficit == max_deficit]
        chosen = rng.choice(candidates)
        split_ids[chosen].add(scene_id)
        counts[chosen] += size

    return split_ids["train"], split_ids["val"], split_ids["test"]


def split_dataset(seed: int = RANDOM_SEED):
    """Split dataset into train/val/test sets using scene-aware grouping."""
    project_root = Path(__file__).parent.parent
    filtered_dir = project_root / "data" / "gtsrb_filtered"
    no_sign_dir = project_root / "data" / "no_sign"
    train_dir = project_root / "data" / "train"
    val_dir = project_root / "data" / "val"
    test_dir = project_root / "data" / "test"
    manifest_path = project_root / "data" / "dataset_manifest.csv"

    if not filtered_dir.exists():
        print(f"[ERROR] Error: Filtered directory not found: {filtered_dir}")
        print("Please run the previous scripts first")
        return

    if no_sign_dir.exists():
        no_sign_target_dir = filtered_dir / "zz_no_sign"
        legacy_no_sign_dir = filtered_dir / "no_sign"

        if legacy_no_sign_dir.exists() and legacy_no_sign_dir.resolve() != no_sign_target_dir.resolve():
            shutil.rmtree(legacy_no_sign_dir)

        if no_sign_target_dir.exists():
            shutil.rmtree(no_sign_target_dir)
        no_sign_target_dir.mkdir(parents=True, exist_ok=True)

        no_sign_images = _collect_images(no_sign_dir)
        used_no_sign_names = set()
        renamed_no_sign = 0
        for img_path in no_sign_images:
            _, was_renamed = _safe_copy_with_unique_name(img_path, no_sign_target_dir, used_no_sign_names)
            if was_renamed:
                renamed_no_sign += 1

        print(
            f"[OK] Merged no_sign corpus into split source: {len(no_sign_images)} images "
            f"(renamed_on_collision={renamed_no_sign})"
        )

    print(
        f"Splitting dataset into train/val/test "
        f"({TRAIN_RATIO*100:.0f}/{VAL_RATIO*100:.0f}/{TEST_RATIO*100:.0f})..."
    )
    print(f"Random seed: {seed}\n")

    for d in [train_dir, val_dir, test_dir]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)

    total_train = 0
    total_val = 0
    total_test = 0
    manifest_rows = []

    for class_dir in sorted(filtered_dir.iterdir()):
        if not class_dir.is_dir():
            continue

        class_name = class_dir.name
        images = _collect_images(class_dir)

        if not images:
            print(f"[WARN] Warning: No images found in {class_name}")
            continue

        if class_name in NO_SIGN_CLASS_NAMES:
            train_images, val_images, test_images = _split_flat_images(images, rng)
        else:
            groups = _group_by_scene(images)
            scene_ids = list(groups.keys())

            if len(scene_ids) < 3:
                train_images, val_images, test_images = _split_flat_images(images, rng)
            else:
                train_ids, val_ids, test_ids = _split_groups(groups, rng)
                train_images = [p for sid in train_ids for p in groups[sid]]
                val_images = [p for sid in val_ids for p in groups[sid]]
                test_images = [p for sid in test_ids for p in groups[sid]]

        train_images = sorted(train_images)
        val_images = sorted(val_images)
        test_images = sorted(test_images)

        train_class_dir = train_dir / class_name
        val_class_dir = val_dir / class_name
        test_class_dir = test_dir / class_name
        train_class_dir.mkdir(parents=True, exist_ok=True)
        val_class_dir.mkdir(parents=True, exist_ok=True)
        test_class_dir.mkdir(parents=True, exist_ok=True)

        used_train_names = set()
        used_val_names = set()
        used_test_names = set()

        renamed_train = 0
        renamed_val = 0
        renamed_test = 0

        for img_path in train_images:
            copied_name, was_renamed = _safe_copy_with_unique_name(img_path, train_class_dir, used_train_names)
            if was_renamed:
                renamed_train += 1
            manifest_rows.append(
                {
                    "split": "train",
                    "class_name": class_name,
                    "filename": copied_name,
                    "scene_id": _scene_id_from_stem(img_path.stem),
                }
            )

        for img_path in val_images:
            copied_name, was_renamed = _safe_copy_with_unique_name(img_path, val_class_dir, used_val_names)
            if was_renamed:
                renamed_val += 1
            manifest_rows.append(
                {
                    "split": "val",
                    "class_name": class_name,
                    "filename": copied_name,
                    "scene_id": _scene_id_from_stem(img_path.stem),
                }
            )

        for img_path in test_images:
            copied_name, was_renamed = _safe_copy_with_unique_name(img_path, test_class_dir, used_test_names)
            if was_renamed:
                renamed_test += 1
            manifest_rows.append(
                {
                    "split": "test",
                    "class_name": class_name,
                    "filename": copied_name,
                    "scene_id": _scene_id_from_stem(img_path.stem),
                }
            )

        total_train += len(train_images)
        total_val += len(val_images)
        total_test += len(test_images)

        print(
            f"[OK] {class_name:25s}: "
            f"train={len(train_images):3d}, val={len(val_images):3d}, test={len(test_images):3d} "
            f"renamed(train/val/test)={renamed_train}/{renamed_val}/{renamed_test}"
        )

    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["split", "class_name", "filename", "scene_id"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print("\n[OK] Split complete!")
    print(f"Total train: {total_train} images")
    print(f"Total val:   {total_val} images")
    print(f"Total test:  {total_test} images")
    print(f"Total:       {total_train + total_val + total_test} images")
    print(f"Manifest:    {manifest_path}")
    print("\nNext step: Run 'python scripts/validate_dataset.py' to verify")


if __name__ == "__main__":
    split_dataset()
