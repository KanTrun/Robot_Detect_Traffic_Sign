"""
LISA annotation filter + crop script.

Backward-compatible filename: filter_classes.py
Output classes (4): stop, speed_limit, warning, other_reg
"""

import argparse
import csv
import random
import re
import shutil
from pathlib import Path

from PIL import Image

TARGET_CLASSES = ["stop", "speed_limit", "warning", "other_reg"]
CLASS_ID = {name: idx + 1 for idx, name in enumerate(TARGET_CLASSES)}
IMAGE_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.ppm", "*.JPG", "*.JPEG", "*.PNG", "*.PPM")

STOP_KEYS = ("stop",)
SPEED_KEYS = ("speedlimit", "mph", "kph")
WARNING_KEYS = (
    "warning", "ahead", "cross", "pedestrian", "school", "curve", "merge", "dip",
    "intersection", "laneends", "signal", "children", "bump", "yieldahead", "stopahead",
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _sniff_delimiter(path: Path) -> str:
    sample = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except Exception:
        return ","


def _read_rows(path: Path):
    delim = _sniff_delimiter(path)
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        if not reader.fieldnames:
            return []
        return list(reader)


def _extract(row: dict):
    norm_map = {_norm(k): v for k, v in row.items() if k is not None}

    def pick(keys):
        for k in keys:
            if k in norm_map and str(norm_map[k]).strip():
                return str(norm_map[k]).strip()
        return ""

    filename = pick(["filename", "image", "imagefilename", "frame", "path", "imagepath"])
    raw_label = pick(["annotationtag", "label", "class", "signname", "signclass", "category"])
    x1 = pick(["upperleftcornerx", "xmin", "x1", "left", "bbxmin"])
    y1 = pick(["upperleftcornery", "ymin", "y1", "top", "bbymin"])
    x2 = pick(["lowerrightcornerx", "xmax", "x2", "right", "bbxmax"])
    y2 = pick(["lowerrightcornery", "ymax", "y2", "bottom", "bbymax"])

    if not filename or not raw_label or not x1 or not y1 or not x2 or not y2:
        return None

    try:
        return {
            "filename": filename.replace("\\", "/"),
            "raw_label": raw_label,
            "x1": int(float(x1)),
            "y1": int(float(y1)),
            "x2": int(float(x2)),
            "y2": int(float(y2)),
        }
    except Exception:
        return None


def _map_label(raw_label: str) -> str:
    t = _norm(raw_label)
    if any(k in t for k in SPEED_KEYS):
        return "speed_limit"
    if any(k in t for k in WARNING_KEYS):
        return "warning"
    if any(k in t for k in STOP_KEYS):
        return "stop"
    return "other_reg"


def _build_image_index(root: Path):
    by_rel = {}
    by_name = {}
    by_stem = {}

    seen = set()
    for pattern in IMAGE_PATTERNS:
        for p in root.rglob(pattern):
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)

            rel = p.relative_to(root).as_posix().lower()
            by_rel[rel] = p

            name = p.name.lower()
            by_name.setdefault(name, []).append(p)

            stem = p.stem.lower()
            by_stem.setdefault(stem, []).append(p)

    return by_rel, by_name, by_stem


def _resolve_image(filename: str, root: Path, by_rel, by_name, by_stem):
    rel_key = filename.strip("/").lower()
    if rel_key in by_rel:
        return by_rel[rel_key]

    direct = root / filename
    if direct.exists():
        return direct

    base = Path(filename).name.lower()
    if base in by_name and by_name[base]:
        return by_name[base][0]

    stem = Path(filename).stem.lower()
    if stem in by_stem and by_stem[stem]:
        return by_stem[stem][0]

    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Crop LISA signs into 4-class dataset")
    parser.add_argument("--source-dir", default="D:/DoAn_Robot/data/lisa_raw")
    parser.add_argument("--max-per-class", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-crop-size", type=int, default=8)
    return parser.parse_args()


def main():
    args = parse_args()

    project_root = Path(__file__).parent.parent
    lisa_root = Path(args.source_dir)
    target_dir = project_root / "data" / "gtsrb_filtered"
    manifest_path = project_root / "data" / "gtsrb_filtered_manifest.csv"

    if not lisa_root.exists():
        raise FileNotFoundError(f"LISA source not found: {lisa_root}")

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    by_rel, by_name, by_stem = _build_image_index(lisa_root)
    csv_paths = sorted(lisa_root.rglob("*.csv"))
    if not csv_paths:
        raise RuntimeError("No annotation CSV found under LISA source")

    candidates = {c: [] for c in TARGET_CLASSES}
    for csv_path in csv_paths:
        rows = _read_rows(csv_path)
        for row in rows:
            rec = _extract(row)
            if not rec:
                continue
            rec["class_name"] = _map_label(rec["raw_label"])
            candidates[rec["class_name"]].append(rec)

    rng = random.Random(args.seed)
    for class_name in TARGET_CLASSES:
        items = candidates[class_name]
        if len(items) > args.max_per_class:
            candidates[class_name] = rng.sample(items, args.max_per_class)

    for class_name in TARGET_CLASSES:
        (target_dir / class_name).mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    saved = {c: 0 for c in TARGET_CLASSES}
    missing_img = 0
    bad_crop = 0

    for class_name in TARGET_CLASSES:
        for i, rec in enumerate(candidates[class_name], start=1):
            img_path = _resolve_image(rec["filename"], lisa_root, by_rel, by_name, by_stem)
            if img_path is None:
                missing_img += 1
                continue

            try:
                with Image.open(img_path) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size

                    left = max(0, min(rec["x1"], rec["x2"]))
                    right = min(w, max(rec["x1"], rec["x2"]))
                    top = max(0, min(rec["y1"], rec["y2"]))
                    bottom = min(h, max(rec["y1"], rec["y2"]))

                    if (right - left) < args.min_crop_size or (bottom - top) < args.min_crop_size:
                        bad_crop += 1
                        continue

                    crop = rgb.crop((left, top, right, bottom))
            except Exception:
                bad_crop += 1
                continue

            out_name = f"{img_path.stem}_{i:06d}.jpg"
            out_path = target_dir / class_name / out_name
            crop.save(out_path, "JPEG", quality=95)

            saved[class_name] += 1
            manifest_rows.append(
                {
                    "source": "lisa",
                    "class_id": CLASS_ID[class_name],
                    "class_name": class_name,
                    "filename": out_name,
                    "scene_id": img_path.stem,
                    "split": "",
                    "raw_label": rec["raw_label"],
                    "bbox_x1": left,
                    "bbox_y1": top,
                    "bbox_x2": right,
                    "bbox_y2": bottom,
                }
            )

    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source", "class_id", "class_name", "filename", "scene_id", "split",
                "raw_label", "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    print("[OK] LISA filtering complete")
    for c in TARGET_CLASSES:
        print(f"  - {c}: {saved[c]} images")
    print(f"[INFO] missing_images={missing_img} bad_crops={bad_crop}")
    print(f"[OK] Manifest: {manifest_path}")
    print("Next step: run 'python scripts/convert_images.py'")


if __name__ == "__main__":
    main()
