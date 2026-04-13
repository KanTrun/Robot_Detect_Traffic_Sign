# -*- coding: utf-8 -*-
"""
GTSRB Classifier for ESP32-CAM — Train + Export Pipeline
=========================================================
Maps 16 GTSRB folders → 5 classes: no_sign, stop, speed_limit, warning, other_reg
Output: Simple classifier (not FOMO grid) → firmware auto-detects.
Run: python notebooks/train_classifier_gtsrb.py
"""

import os
import sys
import json
import hashlib
import random
import shutil
from pathlib import Path
from datetime import datetime

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# ============================================================
# CONFIG
# ============================================================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

IMG_SIZE = 96
ALPHA = 0.35
BATCH_SIZE = 16
EPOCHS_PHASE1 = 50
EPOCHS_PHASE2 = 30
LR_PHASE1 = 1e-3
LR_PHASE2 = 1e-4

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "val"
TEST_DIR = DATA_DIR / "test"
OUTPUT_DIR = PROJECT_ROOT / "models"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Class mapping: 16 GTSRB folders → 5 classes
# Class 0: no_sign (background)
# Class 1: stop
# Class 2: speed_limit
# Class 3: warning
# Class 4: other_reg (regulatory/directional)
CLASS_LABELS = ["no_sign", "stop", "speed_limit", "warning", "other_reg"]
NUM_CLASSES = len(CLASS_LABELS)

FOLDER_TO_CLASS = {
    "zz_no_sign": 0,
    "stop": 1,
    "speed_limit_20": 2,
    "speed_limit_30": 2,
    "speed_limit_50": 2,
    "children_crossing": 3,
    "pedestrian_crossing": 3,
    "road_work": 3,
    "no_entry": 4,
    "end_restriction": 4,
    "keep_left": 4,
    "keep_right": 4,
    "turn_left_ahead": 4,
    "turn_right_ahead": 4,
    "ahead_only": 4,
    "roundabout": 4,
}

print(f"Python: {sys.version.split()[0]}")
print(f"TensorFlow: {tf.__version__}")
print(f"GPU: {tf.config.list_physical_devices('GPU')}")
print(f"Classes: {CLASS_LABELS}")

# ============================================================
# LOAD DATA
# ============================================================
def load_dataset(data_dir: Path, augment: bool = False):
    """Load images from class folders, map to 5 classes."""
    images = []
    labels = []
    class_counts = {i: 0 for i in range(NUM_CLASSES)}

    for folder_name, class_id in FOLDER_TO_CLASS.items():
        folder_path = data_dir / folder_name
        if not folder_path.exists():
            print(f"  [WARN] Missing folder: {folder_path}")
            continue

        # Determine extra augmentation count based on class
        # stop (class 1) gets 10x extra, no_sign (class 0) gets 5x extra
        # other_reg (class 4) gets 0 extra (already overrepresented)
        extra_aug = {0: 5, 1: 10, 2: 2, 3: 2, 4: 0}.get(class_id, 0)

        for img_file in sorted(folder_path.iterdir()):
            if img_file.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.ppm', '.bmp'):
                continue
            try:
                img = Image.open(img_file).convert("RGB")
                img = img.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
                arr = np.array(img, dtype=np.uint8)
                images.append(arr)
                labels.append(class_id)
                class_counts[class_id] += 1

                # Data augmentation for training
                if augment:
                    augmented = augment_image(img, extra_count=extra_aug)
                    for aug_img in augmented:
                        aug_arr = np.array(aug_img, dtype=np.uint8)
                        images.append(aug_arr)
                        labels.append(class_id)
                        class_counts[class_id] += 1

            except Exception as e:
                print(f"  [WARN] Failed to load {img_file}: {e}")

    X = np.array(images, dtype=np.uint8)
    Y = np.array(labels, dtype=np.int32)
    return X, Y, class_counts


def augment_image(img: Image.Image, extra_count: int = 0):
    """Generate augmented versions of an image to simulate camera conditions."""
    augmented = []

    # 1. Brightness variation (camera auto-exposure)
    bright = ImageEnhance.Brightness(img).enhance(random.uniform(0.5, 1.5))
    augmented.append(bright)

    # 2. Rotation + slight perspective (sign not perfectly straight)
    angle = random.uniform(-20, 20)
    rotated = img.rotate(angle, expand=False, fillcolor=(128, 128, 128))
    augmented.append(rotated)

    # 3. Color jitter (camera white balance changes)
    color = ImageEnhance.Color(img).enhance(random.uniform(0.5, 1.5))
    contrast = ImageEnhance.Contrast(color).enhance(random.uniform(0.7, 1.3))
    augmented.append(contrast)

    # 4. Blur (focus issues / motion blur)
    blurred = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 2.0)))
    augmented.append(blurred)

    # 5. Horizontal flip (for symmetric signs like speed limit)
    flipped = ImageOps.mirror(img)
    augmented.append(flipped)

    # Extra augmentation for underrepresented classes
    for _ in range(extra_count):
        aug = img.copy()
        # Random combo of transformations
        aug = ImageEnhance.Brightness(aug).enhance(random.uniform(0.4, 1.6))
        aug = ImageEnhance.Contrast(aug).enhance(random.uniform(0.6, 1.4))
        aug = ImageEnhance.Color(aug).enhance(random.uniform(0.4, 1.6))
        aug = aug.rotate(random.uniform(-25, 25), expand=False,
                        fillcolor=(random.randint(80, 180),) * 3)
        if random.random() > 0.5:
            aug = aug.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 1.5)))
        if random.random() > 0.5:
            aug = ImageOps.mirror(aug)
        augmented.append(aug)

    return augmented


print("\n[LOAD] Loading datasets...")
print("  Training data (with augmentation)...")
X_train, Y_train, train_counts = load_dataset(TRAIN_DIR, augment=True)
print(f"  Train: {X_train.shape} samples")
for cid, count in sorted(train_counts.items()):
    print(f"    Class {cid} ({CLASS_LABELS[cid]}): {count}")

print("  Validation data...")
X_val, Y_val, val_counts = load_dataset(VAL_DIR, augment=False)
print(f"  Val: {X_val.shape} samples")

print("  Test data...")
X_test, Y_test, test_counts = load_dataset(TEST_DIR, augment=False)
print(f"  Test: {X_test.shape} samples")

# Shuffle training data
perm = np.random.permutation(len(X_train))
X_train = X_train[perm]
Y_train = Y_train[perm]

# ============================================================
# BUILD MODEL — Simple Classifier (NOT FOMO)
# ============================================================
def build_classifier(img_size=IMG_SIZE, num_classes=NUM_CLASSES, alpha=ALPHA):
    """MobileNetV2 classifier with proper preprocessing built-in."""
    inputs = keras.Input(shape=(img_size, img_size, 3), name="image")

    # Preprocessing: normalize to [-1, 1] for MobileNetV2
    x = layers.Lambda(preprocess_input, name="preprocess")(inputs)

    backbone = MobileNetV2(
        input_shape=(img_size, img_size, 3),
        alpha=alpha,
        include_top=False,
        weights="imagenet",
    )
    backbone.trainable = False  # Freeze initially

    features = backbone(x)
    x = layers.GlobalAveragePooling2D(name="gap")(features)
    x = layers.Dropout(0.3, name="dropout")(x)
    outputs = layers.Dense(num_classes, activation="softmax", name="classifier")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="traffic_sign_classifier")
    return model, backbone


print("\n[BUILD] Building classifier model...")
model, backbone = build_classifier()

model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=LR_PHASE1),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"],
)
model.summary()

# ============================================================
# TRAIN — Phase 1: Frozen backbone
# ============================================================
X_train_f = X_train.astype(np.float32)
X_val_f = X_val.astype(np.float32)
X_test_f = X_test.astype(np.float32)

callbacks_p1 = [
    keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=10,
                                  restore_best_weights=True, verbose=1),
    keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5,
                                      patience=5, min_lr=1e-6, verbose=1),
]

# Compute class weights to handle remaining imbalance
from sklearn.utils.class_weight import compute_class_weight
try:
    cw = compute_class_weight('balanced', classes=np.unique(Y_train), y=Y_train)
    class_weights = {i: w for i, w in enumerate(cw)}
except ImportError:
    # Manual balanced weights if sklearn not available
    total = len(Y_train)
    class_weights = {}
    for i in range(NUM_CLASSES):
        count = (Y_train == i).sum()
        class_weights[i] = total / (NUM_CLASSES * max(count, 1))

print(f"  Class weights: {class_weights}")

print("\n[TRAIN] Phase 1: Frozen backbone")
history1 = model.fit(
    X_train_f, Y_train,
    validation_data=(X_val_f, Y_val),
    epochs=EPOCHS_PHASE1,
    batch_size=BATCH_SIZE,
    callbacks=callbacks_p1,
    class_weight=class_weights,
    verbose=1,
)

# ============================================================
# NOTE: Phase 2 fine-tuning SKIPPED — causes OOM on CPU-only machine
# Phase 1 frozen backbone already gives ~88% val accuracy
# Fine-tuning can be done on Colab/GPU later if needed
# ============================================================
import gc
gc.collect()
print("\n[SKIP] Phase 2 fine-tuning skipped (OOM on CPU). Using Phase 1 weights.")

# ============================================================
# EVALUATE
# ============================================================
print("\n[EVAL] Evaluating on test set...")
test_loss, test_acc = model.evaluate(X_test_f, Y_test, verbose=0)
print(f"  Test accuracy: {test_acc:.4f}")
print(f"  Test loss: {test_loss:.4f}")

# Per-class metrics
predictions = model.predict(X_test_f, verbose=0)
pred_classes = np.argmax(predictions, axis=-1)

print("\n  Per-class results:")
print(f"  {'Class':<15} {'Total':>6} {'Correct':>8} {'Recall':>8}")
print(f"  {'-'*40}")
for cid in range(NUM_CLASSES):
    mask = Y_test == cid
    total = mask.sum()
    correct = (pred_classes[mask] == cid).sum()
    recall = correct / max(total, 1)
    print(f"  {CLASS_LABELS[cid]:<15} {total:>6} {correct:>8} {recall:>8.1%}")

# Confusion matrix
print("\n  Confusion Matrix (rows=true, cols=predicted):")
print(f"  {'':>15}", end="")
for lbl in CLASS_LABELS:
    print(f" {lbl[:8]:>8}", end="")
print()
for true_id in range(NUM_CLASSES):
    print(f"  {CLASS_LABELS[true_id]:<15}", end="")
    for pred_id in range(NUM_CLASSES):
        count = ((Y_test == true_id) & (pred_classes == pred_id)).sum()
        print(f" {count:>8}", end="")
    print()

# ============================================================
# EXPORT — TFLite int8 + model_data.h
# ============================================================
print("\n[EXPORT] Saving models...")

# Save Keras model
keras_path = OUTPUT_DIR / "classifier_gtsrb.h5"
model.save(str(keras_path))
print(f"  Keras: {keras_path}")

# Float32 TFLite
converter_f = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_f = converter_f.convert()
float_path = OUTPUT_DIR / "classifier_gtsrb_float32.tflite"
float_path.write_bytes(tflite_f)
print(f"  Float32 TFLite: {float_path} ({len(tflite_f)} bytes)")

# Int8 TFLite (full integer quantization)
def representative_gen():
    indices = np.random.choice(len(X_train), min(300, len(X_train)), replace=False)
    for idx in indices:
        yield [X_train[idx:idx + 1].astype(np.float32)]

converter_q = tf.lite.TFLiteConverter.from_keras_model(model)
converter_q.optimizations = [tf.lite.Optimize.DEFAULT]
converter_q.representative_dataset = representative_gen
converter_q.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter_q.inference_input_type = tf.uint8
converter_q.inference_output_type = tf.uint8

tflite_q = converter_q.convert()
int8_path = OUTPUT_DIR / "classifier_gtsrb_int8.tflite"
int8_path.write_bytes(tflite_q)
print(f"  Int8 TFLite: {int8_path} ({len(tflite_q)} bytes)")

# Verify int8 model
interpreter_q = tf.lite.Interpreter(model_path=str(int8_path))
interpreter_q.allocate_tensors()
inp_d = interpreter_q.get_input_details()[0]
out_d = interpreter_q.get_output_details()[0]
print(f"  Int8 input:  shape={inp_d['shape']} dtype={inp_d['dtype']} "
      f"scale={inp_d['quantization'][0]:.6f} zp={inp_d['quantization'][1]}")
print(f"  Int8 output: shape={out_d['shape']} dtype={out_d['dtype']} "
      f"scale={out_d['quantization'][0]:.6f} zp={out_d['quantization'][1]}")

# Evaluate int8 model accuracy
print("\n[EVAL] Int8 TFLite accuracy on test set...")
int8_correct = 0
int8_total = 0
int8_per_class_correct = {i: 0 for i in range(NUM_CLASSES)}
int8_per_class_total = {i: 0 for i in range(NUM_CLASSES)}

for i in range(len(X_test)):
    input_data = np.expand_dims(X_test[i], axis=0).astype(np.uint8)
    interpreter_q.set_tensor(inp_d['index'], input_data)
    interpreter_q.invoke()
    raw_out = interpreter_q.get_tensor(out_d['index'])[0]
    pred = int(np.argmax(raw_out))
    true_label = int(Y_test[i])

    int8_total += 1
    int8_per_class_total[true_label] += 1
    if pred == true_label:
        int8_correct += 1
        int8_per_class_correct[true_label] += 1

int8_acc = int8_correct / max(int8_total, 1)
print(f"  Int8 test accuracy: {int8_acc:.4f} ({int8_correct}/{int8_total})")

print(f"\n  Int8 per-class results:")
print(f"  {'Class':<15} {'Total':>6} {'Correct':>8} {'Recall':>8}")
print(f"  {'-'*40}")
for cid in range(NUM_CLASSES):
    total = int8_per_class_total[cid]
    correct = int8_per_class_correct[cid]
    recall = correct / max(total, 1)
    print(f"  {CLASS_LABELS[cid]:<15} {total:>6} {correct:>8} {recall:>8.1%}")

# Export model_data.h
def export_model_data_h(tflite_path: Path, output_h_path: Path):
    model_bytes = tflite_path.read_bytes()
    lines = []
    for i in range(0, len(model_bytes), 12):
        chunk = model_bytes[i:i + 12]
        lines.append(", ".join(f"0x{b:02x}" for b in chunk))
    hex_array = ",\n  ".join(lines)

    content = f"""// Auto-generated Traffic Sign Classifier Model (GTSRB)
// Model size: {len(model_bytes)} bytes
// Input: {IMG_SIZE}x{IMG_SIZE}x3 uint8
// Output: 1x{NUM_CLASSES} uint8 (classifier, NOT FOMO grid)
// Classes: {', '.join(CLASS_LABELS)}
// Generated: {datetime.now().isoformat()}

#ifndef MODEL_DATA_H
#define MODEL_DATA_H

alignas(8) const unsigned char model_data[] = {{
  {hex_array}
}};

const unsigned int model_data_len = {len(model_bytes)};

#endif  // MODEL_DATA_H
"""
    output_h_path.write_text(content, encoding="utf-8")
    return len(model_bytes)


model_h_path = OUTPUT_DIR / "model_data.h"
model_size = export_model_data_h(int8_path, model_h_path)
print(f"\n  model_data.h: {model_h_path} ({model_size} bytes)")

# Write class labels
labels_path = OUTPUT_DIR / "class_labels.txt"
labels_path.write_text("\n".join(CLASS_LABELS) + "\n", encoding="utf-8")
print(f"  class_labels.txt: {labels_path}")

# Write calibration
calibration = {
    "schema_version": "classifier-v1",
    "model_type": "classifier",
    "background_class_id": 0,
    "default": {
        "min_emit_conf100": 55,
        "min_margin_conf100": 20,
    },
    "per_class": {
        label: {"min_emit_conf100": 55, "min_margin_conf100": 20}
        for label in CLASS_LABELS[1:]
    },
}
calibration_path = OUTPUT_DIR / "fomo_calibration.json"
calibration_path.write_text(json.dumps(calibration, indent=2), encoding="utf-8")
print(f"  calibration: {calibration_path}")

# Write summary
summary = {
    "created_at": datetime.utcnow().isoformat() + "Z",
    "model_type": "classifier",
    "dataset": "GTSRB",
    "input_size": IMG_SIZE,
    "num_classes": NUM_CLASSES,
    "class_labels": CLASS_LABELS,
    "folder_mapping": FOLDER_TO_CLASS,
    "metrics": {
        "keras_test_accuracy": float(test_acc),
        "keras_test_loss": float(test_loss),
        "int8_test_accuracy": float(int8_acc),
    },
    "int8_per_class_recall": {
        CLASS_LABELS[cid]: float(int8_per_class_correct[cid] / max(int8_per_class_total[cid], 1))
        for cid in range(NUM_CLASSES)
    },
    "input_contract": {
        "shape": inp_d["shape"].tolist(),
        "dtype": str(inp_d["dtype"]),
        "quantization": [float(inp_d["quantization"][0]), int(inp_d["quantization"][1])],
    },
    "output_contract": {
        "shape": out_d["shape"].tolist(),
        "dtype": str(out_d["dtype"]),
        "quantization": [float(out_d["quantization"][0]), int(out_d["quantization"][1])],
    },
}
summary_path = OUTPUT_DIR / "fomo_summary.json"
summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"  summary: {summary_path}")

# ============================================================
# DONE
# ============================================================
print("\n" + "=" * 60)
print("DONE — All artifacts generated!")
print("=" * 60)
print(f"  Keras accuracy:  {test_acc:.2%}")
print(f"  Int8 accuracy:   {int8_acc:.2%}")
print(f"  Model size:      {model_size} bytes ({model_size/1024:.1f} KB)")
print(f"  Output type:     Classifier ({NUM_CLASSES} classes)")
print(f"  Firmware compat: AUTO (firmware detects classifier vs FOMO)")
print(f"\nNext: copy models/model_data.h to ESP32-CAM sketch folder and re-flash")
print("=" * 60)
