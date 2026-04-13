from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from esp32cam_fomo_contract import CLASS_LABELS, DEFAULT_CANONICAL_MANIFEST, IMG_SIZE

GROUP_MAP = {
    "stop": "stop",
    "speed_limit_20": "speed_limit",
    "speed_limit_30": "speed_limit",
    "speed_limit_50": "speed_limit",
    "children_crossing": "warning",
    "pedestrian_crossing": "warning",
    "road_work": "warning",
    "ahead_only": "other_reg",
    "end_restriction": "other_reg",
    "keep_left": "other_reg",
    "keep_right": "other_reg",
    "no_entry": "other_reg",
    "roundabout": "other_reg",
    "turn_left_ahead": "other_reg",
    "turn_right_ahead": "other_reg",
}
SPLIT_SIGN_COUNTS = {"train": 480, "val": 120, "test": 120}
SPLIT_BG_COUNTS = {"train": 480, "val": 120, "test": 120}
DOMAINS = ("print", "screen")


def _hash_to_split(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "val"
    return "test"


def _load_background_pool(project_root: Path) -> dict[str, list[Path]]:
    by_split: dict[str, list[Path]] = defaultdict(list)
    no_sign_dir = project_root / "data" / "no_sign"
    if no_sign_dir.exists():
        for path in sorted(no_sign_dir.iterdir()):
            if path.is_file():
                by_split[_hash_to_split(path.name)].append(path)
    for split in ("train", "val", "test"):
        zz_dir = project_root / "data" / split / "zz_no_sign"
        if zz_dir.exists():
            by_split[split].extend(sorted(path for path in zz_dir.iterdir() if path.is_file()))
    return by_split


def _load_sign_pool(project_root: Path) -> dict[str, dict[str, list[Path]]]:
    by_split: dict[str, dict[str, list[Path]]] = {}
    for split in ("train", "val", "test"):
        split_map: dict[str, list[Path]] = defaultdict(list)
        split_dir = project_root / "data" / split
        for label_dir in sorted(path for path in split_dir.iterdir() if path.is_dir()):
            mapped = GROUP_MAP.get(label_dir.name)
            if mapped is None:
                continue
            split_map[mapped].extend(sorted(path for path in label_dir.iterdir() if path.is_file()))
        by_split[split] = split_map
    return by_split


def _apply_domain_style(image: Image.Image, domain: str, rng: random.Random, sign_present: bool) -> Image.Image:
    styled = image.convert("RGB")
    if domain == "print":
        if rng.random() < 0.8:
            styled = styled.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.0, 1.2)))
        styled = ImageEnhance.Brightness(styled).enhance(rng.uniform(0.85, 1.15))
        styled = ImageEnhance.Contrast(styled).enhance(rng.uniform(0.85, 1.20))
    else:
        overlay = Image.new("RGBA", styled.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        if rng.random() < 0.55:
            bar_h = rng.randint(10, 16)
            draw.rectangle((0, 0, styled.width, bar_h), fill=(245, 245, 245, 220))
            draw.ellipse((5, 3, 9, 7), fill=(255, 95, 86, 220))
            draw.ellipse((11, 3, 15, 7), fill=(255, 189, 46, 220))
            draw.ellipse((17, 3, 21, 7), fill=(39, 201, 63, 220))
        for y in range(0, styled.height, 3):
            alpha = rng.randint(8, 18)
            draw.line((0, y, styled.width, y), fill=(255, 255, 255, alpha))
        styled = Image.alpha_composite(styled.convert("RGBA"), overlay).convert("RGB")
        styled = ImageEnhance.Brightness(styled).enhance(rng.uniform(0.9, 1.05))
        styled = ImageEnhance.Color(styled).enhance(rng.uniform(0.95, 1.15))
    if sign_present and rng.random() < 0.25:
        styled = ImageOps.autocontrast(styled)
    return styled


def _compose_sign_frame(background_path: Path, sign_path: Path, domain: str, rng: random.Random) -> tuple[Image.Image, tuple[int, int, int, int]]:
    background = Image.open(background_path).convert("RGB").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    background = _apply_domain_style(background, domain, rng, sign_present=False)
    sign = Image.open(sign_path).convert("RGB")
    side = rng.randint(28, 58)
    sign = ImageOps.contain(sign, (side, side), Image.BILINEAR)
    if rng.random() < 0.85:
        sign = sign.rotate(rng.uniform(-16, 16), resample=Image.BILINEAR, expand=True, fillcolor=(0, 0, 0))
    sign = ImageEnhance.Brightness(sign).enhance(rng.uniform(0.85, 1.15))
    sign = ImageEnhance.Contrast(sign).enhance(rng.uniform(0.85, 1.25))
    max_x = max(1, IMG_SIZE - sign.width - 2)
    max_y = max(1, IMG_SIZE - sign.height - 2)
    x = rng.randint(1, max_x)
    y = rng.randint(1, max_y)
    background.paste(sign, (x, y))
    frame = _apply_domain_style(background, domain, rng, sign_present=True)
    if rng.random() < 0.25:
        frame = frame.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.2, 0.8)))
    return frame, (x, y, x + sign.width, y + sign.height)


def _compose_no_sign_frame(background_path: Path, domain: str, rng: random.Random) -> Image.Image:
    background = Image.open(background_path).convert("RGB").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    frame = _apply_domain_style(background, domain, rng, sign_present=False)
    if rng.random() < 0.35:
        draw = ImageDraw.Draw(frame)
        for _ in range(rng.randint(1, 3)):
            x0 = rng.randint(0, IMG_SIZE - 20)
            y0 = rng.randint(0, IMG_SIZE - 20)
            x1 = min(IMG_SIZE - 1, x0 + rng.randint(8, 26))
            y1 = min(IMG_SIZE - 1, y0 + rng.randint(8, 26))
            draw.rectangle((x0, y0, x1, y1), outline=(rng.randint(80, 255), rng.randint(80, 255), rng.randint(80, 255)))
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap canonical FOMO dataset from existing grouped sign crops")
    parser.add_argument("--out-root", default="data/esp32cam-fomo/generated")
    parser.add_argument("--manifest", default=str(DEFAULT_CANONICAL_MANIFEST))
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    out_root = Path(args.out_root)
    manifest_path = Path(args.manifest)
    sign_pool = _load_sign_pool(project_root)
    bg_pool = _load_background_pool(project_root)
    rng = random.Random(args.seed)

    out_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    for split in ("train", "val", "test"):
        if not bg_pool[split]:
            raise RuntimeError(f"No background images for split={split}")
        for label in CLASS_LABELS[1:]:
            samples = sign_pool[split].get(label, [])
            if not samples:
                raise RuntimeError(f"No sign samples for split={split} label={label}")
            for index in range(SPLIT_SIGN_COUNTS[split]):
                domain = DOMAINS[index % len(DOMAINS)]
                frame, bbox = _compose_sign_frame(
                    background_path=rng.choice(bg_pool[split]),
                    sign_path=rng.choice(samples),
                    domain=domain,
                    rng=rng,
                )
                out_dir = out_root / split / domain / label
                out_dir.mkdir(parents=True, exist_ok=True)
                name = f"{split}_{label}_{domain}_{index:04d}.jpg"
                out_path = out_dir / name
                frame.save(out_path, format="JPEG", quality=rng.randint(72, 92))
                rows.append(
                    {
                        "image_path": str(out_path.resolve()),
                        "domain": domain,
                        "split": split,
                        "label": label,
                        "x1": str(bbox[0]),
                        "y1": str(bbox[1]),
                        "x2": str(bbox[2]),
                        "y2": str(bbox[3]),
                    }
                )

        for index in range(SPLIT_BG_COUNTS[split]):
            domain = DOMAINS[index % len(DOMAINS)]
            frame = _compose_no_sign_frame(rng.choice(bg_pool[split]), domain=domain, rng=rng)
            out_dir = out_root / split / domain / "_background_"
            out_dir.mkdir(parents=True, exist_ok=True)
            name = f"{split}_background_{domain}_{index:04d}.jpg"
            out_path = out_dir / name
            frame.save(out_path, format="JPEG", quality=rng.randint(72, 92))
            rows.append(
                {
                    "image_path": str(out_path.resolve()),
                    "domain": domain,
                    "split": split,
                    "label": "_background_",
                    "x1": "",
                    "y1": "",
                    "x2": "",
                    "y2": "",
                }
            )

    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "domain", "split", "label", "x1", "y1", "x2", "y2"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Bootstrapped dataset root: {out_root.resolve()}")
    print(f"[OK] Canonical manifest: {manifest_path.resolve()}")
    print(f"[OK] Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
