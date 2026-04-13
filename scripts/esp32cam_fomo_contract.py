from __future__ import annotations

from pathlib import Path

IMG_SIZE = 96
FOMO_GRID_SIZE = 12
NUM_CLASSES = 5
BACKGROUND_CLASS_ID = 0
SIGN_CLASS_IDS = (1, 2, 3, 4)
CLASS_LABELS = [
    "_background_",
    "stop",
    "speed_limit",
    "warning",
    "other_reg",
]
EXPECTED_OUTPUT_SHAPE = (FOMO_GRID_SIZE, FOMO_GRID_SIZE, NUM_CLASSES)
CANONICAL_SCHEMA = "fomo-grid-v2"
CANONICAL_MODEL_TYPE = "fomo_grid_detector"
CANONICAL_OUTPUT_MODE = "full_frame_detection"
DEFAULT_RELEASE_CELL_THRESHOLD = 0.70
DEFAULT_RELEASE_MIN_VOTES = 2
ARTIFACT_TFLITE_FLOAT = "traffic_sign_fomo_float32.tflite"
ARTIFACT_TFLITE_INT8 = "traffic_sign_fomo_int8.tflite"
ARTIFACT_MODEL_DATA = "model_data.h"
ARTIFACT_LABELS = "class_labels.txt"
ARTIFACT_SUMMARY = "fomo_summary.json"
ARTIFACT_EVAL = "fomo_eval_report.json"
DEFAULT_DATASET_ROOT = Path("data") / "esp32cam-fomo"
DEFAULT_CAPTURE_MANIFEST = DEFAULT_DATASET_ROOT / "capture_manifest.csv"
DEFAULT_CANONICAL_MANIFEST = DEFAULT_DATASET_ROOT / "fomo_manifest.csv"


def label_to_id(label: str) -> int:
    if label not in CLASS_LABELS:
        raise ValueError(f"Unknown label: {label}")
    return CLASS_LABELS.index(label)


def id_to_label(class_id: int) -> str:
    if class_id < 0 or class_id >= len(CLASS_LABELS):
        raise ValueError(f"Unknown class_id: {class_id}")
    return CLASS_LABELS[class_id]


def ensure_canonical_labels(labels: list[str] | tuple[str, ...]) -> None:
    if list(labels) != CLASS_LABELS:
        raise ValueError(
            "Canonical labels mismatch: "
            f"expected={CLASS_LABELS} actual={list(labels)}"
        )
