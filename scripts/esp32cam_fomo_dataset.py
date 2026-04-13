from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from esp32cam_fomo_contract import (
    BACKGROUND_CLASS_ID,
    CLASS_LABELS,
    FOMO_GRID_SIZE,
    IMG_SIZE,
    NUM_CLASSES,
    id_to_label,
    label_to_id,
)


@dataclass
class BoxAnnotation:
    class_id: int
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class ImageRecord:
    image_path: Path
    domain: str
    split: str
    boxes: list[BoxAnnotation] = field(default_factory=list)

    @property
    def primary_class_id(self) -> int:
        return self.boxes[0].class_id if self.boxes else BACKGROUND_CLASS_ID


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    return float(text) if text else None


def _normalize_split(value: str | None) -> str:
    split = (value or "").strip().lower() or "train"
    if split not in {"train", "val", "test"}:
        raise ValueError(f"Unsupported split: {value}")
    return split


def load_manifest_records(manifest_path: Path) -> list[ImageRecord]:
    grouped: dict[str, ImageRecord] = {}
    with manifest_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"image_path", "domain", "split", "label", "x1", "y1", "x2", "y2"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                "Manifest missing required columns: "
                f"{sorted(required - set(reader.fieldnames or []))}"
            )
        for row in reader:
            image_path = Path(row["image_path"]).expanduser().resolve()
            key = str(image_path)
            record = grouped.setdefault(
                key,
                ImageRecord(
                    image_path=image_path,
                    domain=(row["domain"] or "unknown").strip().lower(),
                    split=_normalize_split(row["split"]),
                ),
            )
            label = (row["label"] or "").strip()
            if not label:
                raise ValueError(f"Missing label for {image_path}")
            class_id = label_to_id(label)
            x1 = _float_or_none(row.get("x1"))
            y1 = _float_or_none(row.get("y1"))
            x2 = _float_or_none(row.get("x2"))
            y2 = _float_or_none(row.get("y2"))
            if class_id == BACKGROUND_CLASS_ID:
                continue
            if None in {x1, y1, x2, y2}:
                raise ValueError(f"Sign row missing bbox for {image_path}")
            record.boxes.append(BoxAnnotation(class_id=class_id, x1=x1, y1=y1, x2=x2, y2=y2))
    return list(grouped.values())


def preprocess_full_frame(image_path: Path) -> np.ndarray:
    image = Image.open(image_path).convert("RGB")
    resized = image.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    return np.asarray(resized, dtype=np.uint8)


def encode_record_to_grid(record: ImageRecord, original_size: tuple[int, int]) -> np.ndarray:
    width, height = original_size
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image size: {(width, height)}")
    target = np.zeros((FOMO_GRID_SIZE, FOMO_GRID_SIZE, NUM_CLASSES), dtype=np.float32)
    target[:, :, BACKGROUND_CLASS_ID] = 1.0
    for box in record.boxes:
        cx = (box.x1 + box.x2) * 0.5
        cy = (box.y1 + box.y2) * 0.5
        grid_x = min(FOMO_GRID_SIZE - 1, max(0, int((cx / width) * FOMO_GRID_SIZE)))
        grid_y = min(FOMO_GRID_SIZE - 1, max(0, int((cy / height) * FOMO_GRID_SIZE)))
        target[grid_y, grid_x, :] = 0.0
        target[grid_y, grid_x, box.class_id] = 1.0
    return target


def build_numpy_split(records: list[ImageRecord], split: str) -> tuple[np.ndarray, np.ndarray, list[ImageRecord]]:
    chosen = [record for record in records if record.split == split]
    images: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for record in chosen:
        image = Image.open(record.image_path).convert("RGB")
        orig_size = image.size
        images.append(np.asarray(image.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR), dtype=np.uint8))
        targets.append(encode_record_to_grid(record, orig_size))
    if not images:
        return (
            np.zeros((0, IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8),
            np.zeros((0, FOMO_GRID_SIZE, FOMO_GRID_SIZE, NUM_CLASSES), dtype=np.float32),
            chosen,
        )
    return np.stack(images), np.stack(targets), chosen


def decode_grid_prediction(
    grid_scores: np.ndarray,
    threshold: float,
    min_votes: int = 1,
) -> tuple[int, float, float]:
    grid = np.asarray(grid_scores, dtype=np.float32).reshape(FOMO_GRID_SIZE, FOMO_GRID_SIZE, NUM_CLASSES)
    votes = np.zeros(NUM_CLASSES, dtype=np.int32)
    conf_sum = np.zeros(NUM_CLASSES, dtype=np.float32)
    for cy in range(FOMO_GRID_SIZE):
        for cx in range(FOMO_GRID_SIZE):
            cell = grid[cy, cx]
            best_class = int(np.argmax(cell))
            best_score = float(cell[best_class])
            if best_class >= 1 and best_score >= threshold:
                votes[best_class] += 1
                conf_sum[best_class] += best_score
    if votes[1:].sum() == 0:
        return BACKGROUND_CLASS_ID, 1.0, 1.0
    best_class = BACKGROUND_CLASS_ID
    best_conf = -1.0
    second_conf = 0.0
    for class_id in range(1, NUM_CLASSES):
        if votes[class_id] < max(1, min_votes):
            continue
        avg_conf = float(conf_sum[class_id] / votes[class_id])
        if avg_conf > best_conf:
            second_conf = best_conf if best_conf > 0 else 0.0
            best_conf = avg_conf
            best_class = class_id
        elif avg_conf > second_conf:
            second_conf = avg_conf
    margin = max(0.0, best_conf - second_conf)
    return best_class, best_conf, margin


def build_confusion_matrix(y_true: list[int], y_pred: list[int]) -> list[list[int]]:
    matrix = [[0 for _ in CLASS_LABELS] for _ in CLASS_LABELS]
    for gt, pred in zip(y_true, y_pred):
        matrix[gt][pred] += 1
    return matrix


def summarize_domains(records: list[ImageRecord], preds: list[int], confs: list[float]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    by_domain: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        by_domain.setdefault(record.domain, []).append(index)
    for domain, indices in by_domain.items():
        y_true = [records[i].primary_class_id for i in indices]
        y_pred = [preds[i] for i in indices]
        domain_confs = [confs[i] for i in indices]
        correct = sum(int(gt == pred) for gt, pred in zip(y_true, y_pred))
        result[domain] = {
            "count": len(indices),
            "accuracy": round(correct / len(indices), 4) if indices else 0.0,
            "mean_confidence": round(float(np.mean(domain_confs)), 4) if domain_confs else 0.0,
            "confusion_matrix": build_confusion_matrix(y_true, y_pred),
            "labels": CLASS_LABELS,
        }
    return result


def class_distribution(records: list[ImageRecord]) -> dict[str, int]:
    counts = {label: 0 for label in CLASS_LABELS}
    for record in records:
        counts[id_to_label(record.primary_class_id)] += 1
    return counts
