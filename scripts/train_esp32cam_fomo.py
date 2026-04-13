from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from esp32cam_fomo_contract import (
    ARTIFACT_EVAL,
    ARTIFACT_LABELS,
    ARTIFACT_MODEL_DATA,
    ARTIFACT_SUMMARY,
    ARTIFACT_TFLITE_FLOAT,
    ARTIFACT_TFLITE_INT8,
    CANONICAL_MODEL_TYPE,
    CANONICAL_OUTPUT_MODE,
    CANONICAL_SCHEMA,
    CLASS_LABELS,
    DEFAULT_CANONICAL_MANIFEST,
    DEFAULT_RELEASE_CELL_THRESHOLD,
    DEFAULT_RELEASE_MIN_VOTES,
    EXPECTED_OUTPUT_SHAPE,
    IMG_SIZE,
    NUM_CLASSES,
)
from esp32cam_fomo_dataset import (
    build_numpy_split,
    class_distribution,
    decode_grid_prediction,
    load_manifest_records,
    summarize_domains,
)

tf = None
keras = None
layers = None
BACKGROUND_LOSS_WEIGHT = 0.05
SIGN_LOSS_WEIGHT = 8.0


def build_model():
    inputs = keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3), dtype="float32", name="image")
    x = inputs
    x = layers.Conv2D(16, 3, strides=2, padding="same", activation="relu")(x)
    x = layers.SeparableConv2D(24, 3, padding="same", activation="relu")(x)
    x = layers.MaxPooling2D(pool_size=2)(x)
    x = layers.SeparableConv2D(32, 3, padding="same", activation="relu")(x)
    x = layers.MaxPooling2D(pool_size=2)(x)
    x = layers.SeparableConv2D(48, 3, padding="same", activation="relu")(x)
    x = layers.SeparableConv2D(64, 3, padding="same", activation="relu")(x)
    logits = layers.Conv2D(NUM_CLASSES, 1, padding="same", name="grid_logits")(x)
    outputs = layers.Softmax(axis=-1, name="grid_probs")(logits)
    model = keras.Model(inputs=inputs, outputs=outputs, name="esp32cam_fomo_release")
    class_weights = tf.constant(
        [BACKGROUND_LOSS_WEIGHT] + [SIGN_LOSS_WEIGHT] * (NUM_CLASSES - 1),
        dtype=tf.float32,
    )

    def weighted_grid_loss(y_true, y_pred):
        cell_weights = tf.reduce_sum(y_true * class_weights, axis=-1)
        ce = keras.losses.categorical_crossentropy(y_true, y_pred)
        return ce * cell_weights

    def sign_cell_recall(y_true, y_pred):
        true_cls = tf.argmax(y_true, axis=-1, output_type=tf.int32)
        pred_cls = tf.argmax(y_pred, axis=-1, output_type=tf.int32)
        mask = tf.cast(tf.not_equal(true_cls, 0), tf.float32)
        correct = tf.cast(tf.equal(true_cls, pred_cls), tf.float32) * mask
        return tf.reduce_sum(correct) / tf.maximum(tf.reduce_sum(mask), 1.0)

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss=weighted_grid_loss,
        metrics=["categorical_accuracy", sign_cell_recall],
    )
    if tuple(model.output_shape[1:]) != EXPECTED_OUTPUT_SHAPE:
        raise RuntimeError(
            f"Output shape mismatch: got={model.output_shape[1:]} expected={EXPECTED_OUTPUT_SHAPE}"
        )
    return model


def export_tflite(model, train_images: np.ndarray, output_dir: Path) -> tuple[bytes, bytes]:
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    float_bytes = converter.convert()

    quant_converter = tf.lite.TFLiteConverter.from_keras_model(model)
    quant_converter.optimizations = [tf.lite.Optimize.DEFAULT]
    quant_converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    quant_converter.inference_input_type = tf.uint8
    quant_converter.inference_output_type = tf.uint8

    sample_count = min(len(train_images), 128)
    reps = train_images[:sample_count].astype(np.float32)

    def representative_dataset():
        for image in reps:
            yield [np.expand_dims(image, axis=0)]

    quant_converter.representative_dataset = representative_dataset
    int8_bytes = quant_converter.convert()

    (output_dir / ARTIFACT_TFLITE_FLOAT).write_bytes(float_bytes)
    (output_dir / ARTIFACT_TFLITE_INT8).write_bytes(int8_bytes)
    return float_bytes, int8_bytes


def write_model_header(model_bytes: bytes, path: Path) -> None:
    hex_rows = []
    for offset in range(0, len(model_bytes), 12):
        chunk = model_bytes[offset : offset + 12]
        hex_rows.append("  " + ", ".join(f"0x{byte:02x}" for byte in chunk))
    body = ",\n".join(hex_rows)
    text = (
        "#pragma once\n"
        "#include <stdint.h>\n\n"
        "alignas(16) const unsigned char model_data[] = {\n"
        f"{body}\n"
        "};\n"
        f"const unsigned int model_data_len = {len(model_bytes)};\n"
    )
    path.write_text(text, encoding="utf-8")


def evaluate_split(model, images: np.ndarray, records, threshold: float, min_votes: int) -> dict:
    if len(images) == 0:
        return {"count": 0, "domains": {}, "accuracy": 0.0}
    probs = model.predict(images, verbose=0)
    preds: list[int] = []
    confs: list[float] = []
    for grid in probs:
        pred, conf, _ = decode_grid_prediction(grid, threshold=threshold, min_votes=min_votes)
        preds.append(pred)
        confs.append(conf)
    y_true = [record.primary_class_id for record in records]
    accuracy = sum(int(gt == pred) for gt, pred in zip(y_true, preds)) / len(records)
    return {
        "count": len(records),
        "accuracy": round(accuracy, 4),
        "domains": summarize_domains(records, preds, confs),
        "class_distribution": class_distribution(records),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train canonical 12x12x5 FOMO release model for ESP32-CAM")
    parser.add_argument("--manifest", default=str(DEFAULT_CANONICAL_MANIFEST))
    parser.add_argument("--output-dir", default="models")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--cell-threshold", type=float, default=DEFAULT_RELEASE_CELL_THRESHOLD)
    parser.add_argument("--min-votes", type=int, default=DEFAULT_RELEASE_MIN_VOTES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global tf, keras, layers
    import tensorflow as tf_module
    from tensorflow import keras as keras_module
    from tensorflow.keras import layers as layers_module

    tf = tf_module
    keras = keras_module
    layers = layers_module

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_manifest_records(manifest_path)
    train_x, train_y, train_records = build_numpy_split(records, "train")
    val_x, val_y, val_records = build_numpy_split(records, "val")
    test_x, test_y, test_records = build_numpy_split(records, "test")
    if len(train_x) == 0 or len(val_x) == 0:
        raise RuntimeError("Need both train and val splits in canonical manifest")
    train_x = train_x.astype(np.float32) / 255.0
    val_x = val_x.astype(np.float32) / 255.0
    test_x = test_x.astype(np.float32) / 255.0

    model = build_model()
    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=6, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3),
    ]
    history = model.fit(
        train_x,
        train_y,
        validation_data=(val_x, val_y),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=callbacks,
        verbose=1,
    )

    float_bytes, int8_bytes = export_tflite(model, train_x, output_dir)
    write_model_header(float_bytes, output_dir / ARTIFACT_MODEL_DATA)
    (output_dir / ARTIFACT_LABELS).write_text("\n".join(CLASS_LABELS) + "\n", encoding="utf-8")

    eval_report = {
        "schema": CANONICAL_SCHEMA,
        "model_type": CANONICAL_MODEL_TYPE,
        "output_mode": CANONICAL_OUTPUT_MODE,
        "cell_threshold": args.cell_threshold,
        "min_votes": args.min_votes,
        "loss_weights": {
            "_background_": BACKGROUND_LOSS_WEIGHT,
            "sign": SIGN_LOSS_WEIGHT,
        },
        "train": evaluate_split(model, train_x, train_records, args.cell_threshold, args.min_votes),
        "val": evaluate_split(model, val_x, val_records, args.cell_threshold, args.min_votes),
        "test": evaluate_split(model, test_x, test_records, args.cell_threshold, args.min_votes),
    }
    (output_dir / ARTIFACT_EVAL).write_text(
        json.dumps(eval_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "schema": CANONICAL_SCHEMA,
        "model_type": CANONICAL_MODEL_TYPE,
        "output_mode": CANONICAL_OUTPUT_MODE,
        "class_labels": CLASS_LABELS,
        "input_shape": [1, IMG_SIZE, IMG_SIZE, 3],
        "output_shape": [1, *EXPECTED_OUTPUT_SHAPE],
        "splits": {
            "train": class_distribution(train_records),
            "val": class_distribution(val_records),
            "test": class_distribution(test_records),
        },
        "artifacts": {
            ARTIFACT_TFLITE_FLOAT: len(float_bytes),
            ARTIFACT_TFLITE_INT8: len(int8_bytes),
            ARTIFACT_MODEL_DATA: (output_dir / ARTIFACT_MODEL_DATA).stat().st_size,
            ARTIFACT_EVAL: (output_dir / ARTIFACT_EVAL).stat().st_size,
        },
        "deploy_header_source": ARTIFACT_TFLITE_FLOAT,
        "loss_weights": {
            "_background_": BACKGROUND_LOSS_WEIGHT,
            "sign": SIGN_LOSS_WEIGHT,
        },
        "release_decode": {
            "cell_threshold": args.cell_threshold,
            "min_votes": args.min_votes,
        },
        "history": {key: [float(v) for v in values] for key, values in history.history.items()},
    }
    (output_dir / ARTIFACT_SUMMARY).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] Release artifacts written to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
