from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from esp32cam_fomo_contract import (
    CLASS_LABELS,
    DEFAULT_CANONICAL_MANIFEST,
    DEFAULT_RELEASE_CELL_THRESHOLD,
    DEFAULT_RELEASE_MIN_VOTES,
)
from esp32cam_fomo_dataset import (
    build_numpy_split,
    decode_grid_prediction,
    load_manifest_records,
    summarize_domains,
)


def load_tflite(model_path: Path):
    try:
        import tensorflow as tf

        interpreter = tf.lite.Interpreter(model_path=str(model_path))
    except ImportError:
        import tflite_runtime.interpreter as tflite

        interpreter = tflite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    return interpreter, interpreter.get_input_details()[0], interpreter.get_output_details()[0]


def infer_grid(interpreter, input_detail, output_detail, image: np.ndarray) -> np.ndarray:
    input_batch = np.expand_dims(image, axis=0)
    if input_detail["dtype"] == np.uint8:
        prepared = input_batch.astype(np.uint8)
    elif input_detail["dtype"] == np.int8:
        scale, zp = input_detail["quantization"]
        prepared = np.clip(
            np.round(input_batch.astype(np.float32) / scale) + zp,
            -128,
            127,
        ).astype(np.int8)
    else:
        prepared = input_batch.astype(np.float32) / 255.0
    interpreter.set_tensor(input_detail["index"], prepared)
    interpreter.invoke()
    raw = interpreter.get_tensor(output_detail["index"])
    scale, zp = output_detail["quantization"]
    if output_detail["dtype"] in (np.uint8, np.int8):
        return (raw.astype(np.float32) - zp) * scale
    return raw.astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a FOMO TFLite model by ESP32-CAM domain")
    parser.add_argument("--model", required=True)
    parser.add_argument("--manifest", default=str(DEFAULT_CANONICAL_MANIFEST))
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--cell-threshold", type=float, default=DEFAULT_RELEASE_CELL_THRESHOLD)
    parser.add_argument("--min-votes", type=int, default=DEFAULT_RELEASE_MIN_VOTES)
    parser.add_argument("--out", default="reports/esp32cam-fomo-eval.json")
    args = parser.parse_args()

    records = load_manifest_records(Path(args.manifest))
    images, _, split_records = build_numpy_split(records, args.split)
    interpreter, input_detail, output_detail = load_tflite(Path(args.model))

    total_elements = int(np.prod(output_detail["shape"]))
    expected = 12 * 12 * len(CLASS_LABELS)
    if total_elements != expected:
        raise RuntimeError(
            f"Model output is not canonical FOMO grid: output_shape={output_detail['shape']} expected_elements={expected}"
        )

    preds: list[int] = []
    confs: list[float] = []
    for image in images:
        grid = infer_grid(interpreter, input_detail, output_detail, image).reshape(12, 12, len(CLASS_LABELS))
        pred, conf, _ = decode_grid_prediction(
            grid,
            threshold=args.cell_threshold,
            min_votes=args.min_votes,
        )
        preds.append(pred)
        confs.append(conf)

    report = {
        "split": args.split,
        "count": len(split_records),
        "cell_threshold": args.cell_threshold,
        "min_votes": args.min_votes,
        "domains": summarize_domains(split_records, preds, confs),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Eval report written: {out_path.resolve()}")


if __name__ == "__main__":
    main()
