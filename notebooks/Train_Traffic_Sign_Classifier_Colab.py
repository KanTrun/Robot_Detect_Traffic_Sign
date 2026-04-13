# %% [markdown]
# # 🚦 Traffic Sign Classifier — GTSRB → ESP32-CAM
# **Dataset**: GTSRB (German Traffic Signs) = biển báo quốc tế giống Việt Nam
#
# **Pipeline**: GTSRB 16 folders → 5 classes → MobileNetV2 Classifier → Int8 TFLite → model_data.h → ESP32-CAM
#
# **Classes**: no_sign (0), stop (1), speed_limit (2), warning (3), other_reg (4)
#
# ---
# ### Cách dùng:
# 1. Upload file `data.zip` (chứa data/train, data/val, data/test) lên Google Drive
# 2. Chạy từng cell tuần tự
# 3. Download `model_data.h` + `classifier_gtsrb_int8.tflite` ở cell cuối
#
# ### Hoặc:
# 1. Upload trực tiếp file `data.zip` khi cell yêu cầu
# 2. Chạy từng cell tuần tự

# %% [markdown]
# ## Cell 1: Cài đặt & Setup

# %%
# ======================== CELL 1: SETUP ========================
import os, sys, json, random, shutil, time
from pathlib import Path
from datetime import datetime

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.applications import MobileNetV2

# PIL for augmentation
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

print(f"Python: {sys.version.split()[0]}")
print(f"TensorFlow: {tf.__version__}")
print(f"GPU: {tf.config.list_physical_devices('GPU')}")

# Verify GPU
if tf.config.list_physical_devices('GPU'):
    print("✅ GPU detected — training will be fast!")
else:
    print("⚠️  No GPU — training will be slower. Go to Runtime > Change runtime type > GPU")

# %% [markdown]
# ## Cell 2: Upload Data
# Zip thư mục `data/` trên máy bạn (bao gồm train/, val/, test/), rồi upload.
#
# **Cách 1**: Upload qua Google Drive (nhanh hơn cho file lớn)
#
# **Cách 2**: Upload trực tiếp (nhỏ hơn 200MB)

# %%
# ======================== CELL 2: UPLOAD DATA ========================
# Chọn 1 trong 2 cách dưới đây:

# --- Cách 1: Google Drive ---
USE_DRIVE = True  # Đổi thành False nếu upload trực tiếp

if USE_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')

    # Đường dẫn file zip trên Drive (SỬA LẠI cho đúng!)
    DRIVE_ZIP = '/content/drive/MyDrive/DoAn_Robot/data.zip'

    if os.path.exists(DRIVE_ZIP):
        print(f"✅ Found: {DRIVE_ZIP}")
        os.system(f'unzip -q -o "{DRIVE_ZIP}" -d /content/')
        print("✅ Data extracted!")
    else:
        print(f"❌ NOT FOUND: {DRIVE_ZIP}")
        print("Hãy upload file data.zip lên Google Drive và sửa đường dẫn DRIVE_ZIP")
else:
    # --- Cách 2: Upload trực tiếp ---
    from google.colab import files
    print("Upload file data.zip...")
    uploaded = files.upload()
    for filename in uploaded:
        os.system(f'unzip -q -o "{filename}" -d /content/')
    print("✅ Data extracted!")

# Verify data structure
DATA_DIR = Path('/content/data')
for split in ['train', 'val', 'test']:
    d = DATA_DIR / split
    if d.exists():
        folders = sorted([f.name for f in d.iterdir() if f.is_dir()])
        total = sum(len(list((d / f).glob('*'))) for f in folders)
        print(f"  {split}: {total} images in {len(folders)} folders")
    else:
        print(f"  ❌ {split}/ NOT FOUND!")

# %% [markdown]
# ## Cell 3: Cấu hình

# %%
# ======================== CELL 3: CONFIGURATION ========================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

# Model config
IMG_SIZE = 96
ALPHA = 0.5              # MobileNetV2 width multiplier (0.5 = good balance)
NUM_CLASSES = 5
BATCH_SIZE = 32           # Colab GPU handles 32 easily
EPOCHS_PHASE1 = 50        # Frozen backbone
EPOCHS_PHASE2 = 40        # Fine-tune backbone
LR_PHASE1 = 1e-3
LR_PHASE2 = 5e-5          # Very low LR for fine-tuning

# Paths
DATA_DIR = Path('/content/data')
TRAIN_DIR = DATA_DIR / 'train'
VAL_DIR = DATA_DIR / 'val'
TEST_DIR = DATA_DIR / 'test'
OUTPUT_DIR = Path('/content/output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Class mapping: 16 GTSRB folders → 5 classes
CLASS_LABELS = ["no_sign", "stop", "speed_limit", "warning", "other_reg"]

FOLDER_TO_CLASS = {
    "zz_no_sign": 0,
    "stop": 1,
    "speed_limit_20": 2, "speed_limit_30": 2, "speed_limit_50": 2,
    "children_crossing": 3, "pedestrian_crossing": 3, "road_work": 3,
    "no_entry": 4, "end_restriction": 4, "keep_left": 4, "keep_right": 4,
    "turn_left_ahead": 4, "turn_right_ahead": 4, "ahead_only": 4, "roundabout": 4,
}

# Extra augmentation for underrepresented classes
# stop (class 1) gets 12x extra, no_sign (class 0) gets 6x extra
EXTRA_AUG_PER_CLASS = {0: 6, 1: 12, 2: 3, 3: 3, 4: 0}

print("✅ Configuration set!")
print(f"   Model: MobileNetV2 alpha={ALPHA}")
print(f"   Input: {IMG_SIZE}x{IMG_SIZE}x3")
print(f"   Classes: {CLASS_LABELS}")

# %% [markdown]
# ## Cell 4: Data Augmentation Functions

# %%
# ======================== CELL 4: AUGMENTATION ========================
def augment_image(img, extra_count=0):
    """
    Generate augmented versions simulating real ESP32-CAM conditions.
    Returns list of PIL Images.
    """
    augmented = []

    # 1. Brightness (camera auto-exposure)
    aug = ImageEnhance.Brightness(img).enhance(random.uniform(0.4, 1.6))
    augmented.append(aug)

    # 2. Rotation (sign not perfectly straight)
    angle = random.uniform(-25, 25)
    aug = img.rotate(angle, expand=False, fillcolor=(128, 128, 128))
    augmented.append(aug)

    # 3. Color jitter (white balance changes)
    aug = ImageEnhance.Color(img).enhance(random.uniform(0.4, 1.6))
    aug = ImageEnhance.Contrast(aug).enhance(random.uniform(0.6, 1.4))
    augmented.append(aug)

    # 4. Gaussian blur (focus/motion blur)
    aug = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 2.5)))
    augmented.append(aug)

    # 5. Mirror (symmetric signs)
    aug = ImageOps.mirror(img)
    augmented.append(aug)

    # 6. Combined: dark + blur (night/indoor conditions)
    aug = ImageEnhance.Brightness(img).enhance(random.uniform(0.3, 0.6))
    aug = aug.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 1.5)))
    augmented.append(aug)

    # 7. High contrast (direct sunlight)
    aug = ImageEnhance.Contrast(img).enhance(random.uniform(1.3, 2.0))
    aug = ImageEnhance.Brightness(aug).enhance(random.uniform(1.1, 1.4))
    augmented.append(aug)

    # Extra augmentation for underrepresented classes
    for _ in range(extra_count):
        aug = img.copy()
        aug = ImageEnhance.Brightness(aug).enhance(random.uniform(0.3, 1.7))
        aug = ImageEnhance.Contrast(aug).enhance(random.uniform(0.5, 1.5))
        aug = ImageEnhance.Color(aug).enhance(random.uniform(0.3, 1.7))
        aug = aug.rotate(random.uniform(-30, 30), expand=False,
                        fillcolor=(random.randint(60, 200),) * 3)
        if random.random() > 0.4:
            aug = aug.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 2.0)))
        if random.random() > 0.5:
            aug = ImageOps.mirror(aug)
        augmented.append(aug)

    return augmented

print("✅ Augmentation functions defined!")

# %% [markdown]
# ## Cell 5: Load Data

# %%
# ======================== CELL 5: LOAD DATA ========================
def load_dataset(data_dir, augment=False):
    """Load images from GTSRB folder structure, map to 5 classes."""
    images, labels = [], []
    class_counts = {i: 0 for i in range(NUM_CLASSES)}

    for folder_name, class_id in FOLDER_TO_CLASS.items():
        folder_path = data_dir / folder_name
        if not folder_path.exists():
            print(f"  ⚠️  Missing: {folder_path.name}")
            continue

        extra = EXTRA_AUG_PER_CLASS.get(class_id, 0) if augment else 0

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

                if augment:
                    for aug_img in augment_image(img, extra_count=extra):
                        images.append(np.array(aug_img, dtype=np.uint8))
                        labels.append(class_id)
                        class_counts[class_id] += 1

            except Exception as e:
                print(f"  ⚠️  Failed: {img_file.name}: {e}")

    X = np.array(images, dtype=np.uint8)
    Y = np.array(labels, dtype=np.int32)
    return X, Y, class_counts


print("Loading TRAINING data (with augmentation)...")
t0 = time.time()
X_train, Y_train, train_counts = load_dataset(TRAIN_DIR, augment=True)
print(f"  Done in {time.time()-t0:.1f}s → {X_train.shape[0]} samples")
for cid in range(NUM_CLASSES):
    print(f"    {CLASS_LABELS[cid]:<15}: {train_counts[cid]:>6}")

print("\nLoading VALIDATION data...")
X_val, Y_val, val_counts = load_dataset(VAL_DIR, augment=False)
print(f"  {X_val.shape[0]} samples")

print("\nLoading TEST data...")
X_test, Y_test, test_counts = load_dataset(TEST_DIR, augment=False)
print(f"  {X_test.shape[0]} samples")

# Shuffle training data
perm = np.random.permutation(len(X_train))
X_train, Y_train = X_train[perm], Y_train[perm]

# Compute class weights
from sklearn.utils.class_weight import compute_class_weight
cw_values = compute_class_weight('balanced', classes=np.arange(NUM_CLASSES), y=Y_train)
class_weights = {i: w for i, w in enumerate(cw_values)}
print(f"\nClass weights: {class_weights}")

# %% [markdown]
# ## Cell 6: Visualize Data Samples

# %%
# ======================== CELL 6: VISUALIZE ========================
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 5, figsize=(15, 6))
fig.suptitle('Sample images per class', fontsize=14)

for cid in range(NUM_CLASSES):
    # Original
    mask = Y_train == cid
    idx = np.where(mask)[0]
    sample_idx = idx[random.randint(0, len(idx)-1)]

    axes[0, cid].imshow(X_train[sample_idx])
    axes[0, cid].set_title(f"{CLASS_LABELS[cid]}\n({train_counts[cid]} samples)", fontsize=10)
    axes[0, cid].axis('off')

    # Another random sample
    sample_idx2 = idx[random.randint(0, len(idx)-1)]
    axes[1, cid].imshow(X_train[sample_idx2])
    axes[1, cid].axis('off')

plt.tight_layout()
plt.show()

# Class distribution bar chart
plt.figure(figsize=(10, 4))
plt.bar(CLASS_LABELS, [train_counts[i] for i in range(NUM_CLASSES)],
        color=['gray', 'red', 'blue', 'orange', 'green'])
plt.title('Training samples per class (after augmentation)')
plt.ylabel('Count')
plt.show()

# %% [markdown]
# ## Cell 7: Build Model
# **Architecture**: MobileNetV2 (alpha=0.5) + GlobalAveragePooling + Dense(5)
#
# **Rescaling layer** tích hợp bên trong model: tự động chuyển [0,255] → [-1,1]
#
# → Firmware chỉ cần feed raw pixel values [0,255], model tự xử lý!

# %%
# ======================== CELL 7: BUILD MODEL ========================
def build_classifier():
    """
    Build MobileNetV2 classifier WITH Rescaling layer inside.
    Input: uint8 [0, 255] → Rescaling → [-1, 1] → MobileNetV2 → softmax
    This way firmware just feeds raw pixels!
    """
    inputs = keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3), name="image_input")

    # Rescaling: [0, 255] → [-1, 1] (same as MobileNetV2 preprocess_input)
    x = layers.Rescaling(scale=1./127.5, offset=-1.0, name="rescale")(inputs)

    # MobileNetV2 backbone (pretrained on ImageNet)
    backbone = MobileNetV2(
        input_shape=(IMG_SIZE, IMG_SIZE, 3),
        alpha=ALPHA,
        include_top=False,
        weights="imagenet",
    )

    x = backbone(x)
    x = layers.GlobalAveragePooling2D(name="gap")(x)
    x = layers.Dropout(0.4, name="dropout")(x)
    outputs = layers.Dense(NUM_CLASSES, activation="softmax", name="classifier")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="traffic_sign_classifier")
    return model, backbone

model, backbone = build_classifier()
backbone.trainable = False  # Phase 1: freeze backbone

model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=LR_PHASE1),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"],
)

model.summary()
print(f"\n✅ Model built! Trainable params: {sum(np.prod(v.shape) for v in model.trainable_variables)}")

# %% [markdown]
# ## Cell 8: Train Phase 1 — Frozen Backbone
# Chỉ train Dense head, backbone MobileNetV2 giữ nguyên ImageNet weights.
# Nhanh, ~30s/epoch trên Colab GPU.

# %%
# ======================== CELL 8: TRAIN PHASE 1 ========================
# Feed raw uint8 as float32 (Rescaling layer handles normalization)
X_train_f = X_train.astype(np.float32)
X_val_f = X_val.astype(np.float32)
X_test_f = X_test.astype(np.float32)

callbacks_p1 = [
    keras.callbacks.EarlyStopping(
        monitor="val_accuracy", patience=12,
        restore_best_weights=True, verbose=1, mode="max"
    ),
    keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5,
        patience=5, min_lr=1e-6, verbose=1
    ),
]

print("🚀 Phase 1: Training with FROZEN backbone...")
print(f"   Epochs: up to {EPOCHS_PHASE1}, Batch: {BATCH_SIZE}")

history1 = model.fit(
    X_train_f, Y_train,
    validation_data=(X_val_f, Y_val),
    epochs=EPOCHS_PHASE1,
    batch_size=BATCH_SIZE,
    callbacks=callbacks_p1,
    class_weight=class_weights,
    verbose=1,
)

p1_val_acc = max(history1.history['val_accuracy'])
print(f"\n✅ Phase 1 done! Best val_accuracy: {p1_val_acc:.2%}")

# %% [markdown]
# ## Cell 9: Train Phase 2 — Fine-tune Backbone
# Unfreeze toàn bộ backbone, train với learning rate rất thấp.
# Đây là bước QUAN TRỌNG nhất — cần GPU!

# %%
# ======================== CELL 9: TRAIN PHASE 2 ========================
import gc
gc.collect()

print("🔓 Unfreezing backbone for fine-tuning...")
backbone.trainable = True

model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=LR_PHASE2),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"],
)

trainable_count = sum(np.prod(v.shape) for v in model.trainable_variables)
print(f"   Total trainable params: {trainable_count:,}")

callbacks_p2 = [
    keras.callbacks.EarlyStopping(
        monitor="val_accuracy", patience=10,
        restore_best_weights=True, verbose=1, mode="max"
    ),
    keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5,
        patience=4, min_lr=1e-7, verbose=1
    ),
]

print(f"\n🚀 Phase 2: Fine-tuning FULL model...")
print(f"   Epochs: up to {EPOCHS_PHASE2}, LR: {LR_PHASE2}")

history2 = model.fit(
    X_train_f, Y_train,
    validation_data=(X_val_f, Y_val),
    epochs=EPOCHS_PHASE2,
    batch_size=BATCH_SIZE,
    callbacks=callbacks_p2,
    class_weight=class_weights,
    verbose=1,
)

p2_val_acc = max(history2.history['val_accuracy'])
print(f"\n✅ Phase 2 done! Best val_accuracy: {p2_val_acc:.2%}")
print(f"   Improvement: {p1_val_acc:.2%} → {p2_val_acc:.2%} ({(p2_val_acc-p1_val_acc)*100:+.1f}pp)")

# %% [markdown]
# ## Cell 10: Evaluate Keras Model

# %%
# ======================== CELL 10: EVALUATE KERAS ========================
print("📊 Evaluating Keras model on test set...")
test_loss, test_acc = model.evaluate(X_test_f, Y_test, verbose=0)
print(f"   Test accuracy: {test_acc:.2%}")
print(f"   Test loss: {test_loss:.4f}")

predictions = model.predict(X_test_f, verbose=0)
pred_classes = np.argmax(predictions, axis=-1)

print(f"\n{'Class':<15} {'Total':>6} {'Correct':>8} {'Recall':>8}")
print("-" * 45)
for cid in range(NUM_CLASSES):
    mask = Y_test == cid
    total = mask.sum()
    correct = (pred_classes[mask] == cid).sum()
    recall = correct / max(total, 1)
    status = "✅" if recall >= 0.9 else "⚠️" if recall >= 0.8 else "❌"
    print(f"{status} {CLASS_LABELS[cid]:<13} {total:>6} {correct:>8} {recall:>8.1%}")

# Confusion Matrix
print("\n📋 Confusion Matrix (rows=true, cols=predicted):")
print(f"{'':>15}", end="")
for lbl in CLASS_LABELS:
    print(f" {lbl[:8]:>8}", end="")
print()
for true_id in range(NUM_CLASSES):
    print(f"  {CLASS_LABELS[true_id]:<13}", end="")
    for pred_id in range(NUM_CLASSES):
        count = ((Y_test == true_id) & (pred_classes == pred_id)).sum()
        print(f" {count:>8}", end="")
    print()

# %% [markdown]
# ## Cell 11: Export TFLite (Float32 + Int8)
# Int8 model dùng **uint8 input** — firmware feed raw pixel values trực tiếp!

# %%
# ======================== CELL 11: EXPORT TFLITE ========================
print("📦 Exporting TFLite models...")

# Save Keras model
keras_path = OUTPUT_DIR / "classifier_gtsrb.keras"
model.save(str(keras_path))
print(f"   Keras: {keras_path}")

# --- Float32 TFLite ---
converter_f = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_f32 = converter_f.convert()
f32_path = OUTPUT_DIR / "classifier_gtsrb_float32.tflite"
f32_path.write_bytes(tflite_f32)
print(f"   Float32 TFLite: {len(tflite_f32):,} bytes ({len(tflite_f32)/1024:.1f} KB)")

# --- Int8 TFLite (full integer quantization) ---
def representative_gen():
    """Use real training images as calibration data."""
    indices = np.random.choice(len(X_train), min(500, len(X_train)), replace=False)
    for idx in indices:
        # Feed raw uint8 as float32 — Rescaling layer is inside the model!
        yield [X_train[idx:idx + 1].astype(np.float32)]

converter_q = tf.lite.TFLiteConverter.from_keras_model(model)
converter_q.optimizations = [tf.lite.Optimize.DEFAULT]
converter_q.representative_dataset = representative_gen
converter_q.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter_q.inference_input_type = tf.uint8    # Input: raw uint8 pixels [0, 255]
converter_q.inference_output_type = tf.uint8   # Output: uint8 probabilities

tflite_q = converter_q.convert()
int8_path = OUTPUT_DIR / "classifier_gtsrb_int8.tflite"
int8_path.write_bytes(tflite_q)
print(f"   Int8 TFLite: {len(tflite_q):,} bytes ({len(tflite_q)/1024:.1f} KB)")

# Verify input/output contracts
interp = tf.lite.Interpreter(model_path=str(int8_path))
interp.allocate_tensors()
inp_d = interp.get_input_details()[0]
out_d = interp.get_output_details()[0]

print(f"\n   📋 Int8 Model Contract:")
print(f"   Input:  shape={inp_d['shape']} dtype={inp_d['dtype']}")
print(f"           scale={inp_d['quantization'][0]:.6f} zero_point={inp_d['quantization'][1]}")
print(f"   Output: shape={out_d['shape']} dtype={out_d['dtype']}")
print(f"           scale={out_d['quantization'][0]:.6f} zero_point={out_d['quantization'][1]}")

# %% [markdown]
# ## Cell 12: Evaluate Int8 Model (QUAN TRỌNG!)
# Kiểm tra accuracy sau khi quantize int8.
# **Target**: Gap < 3pp so với Keras accuracy.

# %%
# ======================== CELL 12: EVALUATE INT8 ========================
print("📊 Evaluating Int8 TFLite model on test set...")

int8_correct = 0
int8_total = 0
int8_pc = {i: [0, 0] for i in range(NUM_CLASSES)}  # [correct, total]

for i in range(len(X_test)):
    # Feed raw uint8 — same as firmware will do!
    input_data = np.expand_dims(X_test[i], axis=0).astype(np.uint8)
    interp.set_tensor(inp_d['index'], input_data)
    interp.invoke()
    raw_out = interp.get_tensor(out_d['index'])[0]
    pred = int(np.argmax(raw_out))
    true_label = int(Y_test[i])

    int8_total += 1
    int8_pc[true_label][1] += 1
    if pred == true_label:
        int8_correct += 1
        int8_pc[true_label][0] += 1

int8_acc = int8_correct / max(int8_total, 1)
gap = (test_acc - int8_acc) * 100

print(f"\n   Keras accuracy:  {test_acc:.2%}")
print(f"   Int8 accuracy:   {int8_acc:.2%}")
print(f"   Gap:             {gap:.1f}pp {'✅ GOOD' if gap < 5 else '⚠️ HIGH' if gap < 10 else '❌ TOO HIGH'}")

print(f"\n{'Class':<15} {'Total':>6} {'Correct':>8} {'Recall':>8}")
print("-" * 45)
for cid in range(NUM_CLASSES):
    ok, tot = int8_pc[cid]
    recall = ok / max(tot, 1)
    status = "✅" if recall >= 0.9 else "⚠️" if recall >= 0.8 else "❌"
    print(f"{status} {CLASS_LABELS[cid]:<13} {tot:>6} {ok:>8} {recall:>8.1%}")

# %% [markdown]
# ## Cell 13: Export model_data.h + Artifacts
# File `model_data.h` để copy vào firmware ESP32-CAM.

# %%
# ======================== CELL 13: EXPORT model_data.h ========================
print("📦 Exporting model_data.h...")

model_bytes = int8_path.read_bytes()
hex_lines = []
for j in range(0, len(model_bytes), 12):
    chunk = model_bytes[j:j + 12]
    hex_lines.append("  " + ", ".join(f"0x{b:02x}" for b in chunk))

hex_str = ",\n".join(hex_lines)

header_content = f"""// Auto-generated Traffic Sign Classifier (GTSRB)
// Model size: {len(model_bytes)} bytes ({len(model_bytes)/1024:.1f} KB)
// Input: {IMG_SIZE}x{IMG_SIZE}x3 uint8 [0,255] — feed raw pixels!
// Output: 1x{NUM_CLASSES} uint8 (classifier)
// Classes: {', '.join(CLASS_LABELS)}
// Keras accuracy: {test_acc:.2%} | Int8 accuracy: {int8_acc:.2%}
// Input quantization: scale={inp_d['quantization'][0]:.6f} zp={inp_d['quantization'][1]}
// Output quantization: scale={out_d['quantization'][0]:.6f} zp={out_d['quantization'][1]}
// Generated: {datetime.now().isoformat()}

#ifndef MODEL_DATA_H
#define MODEL_DATA_H

alignas(8) const unsigned char model_data[] = {{
{hex_str}
}};

const unsigned int model_data_len = {len(model_bytes)};

#endif  // MODEL_DATA_H
"""

model_h_path = OUTPUT_DIR / "model_data.h"
model_h_path.write_text(header_content, encoding="utf-8")
print(f"   ✅ {model_h_path} ({len(model_bytes):,} bytes)")

# Class labels file
labels_path = OUTPUT_DIR / "class_labels.txt"
labels_path.write_text("\n".join(CLASS_LABELS) + "\n", encoding="utf-8")
print(f"   ✅ {labels_path}")

# Summary JSON
summary = {
    "created_at": datetime.utcnow().isoformat() + "Z",
    "model_type": "classifier",
    "dataset": "GTSRB",
    "architecture": f"MobileNetV2 alpha={ALPHA}",
    "input_size": IMG_SIZE,
    "num_classes": NUM_CLASSES,
    "class_labels": CLASS_LABELS,
    "folder_mapping": FOLDER_TO_CLASS,
    "training": {
        "phase1_epochs": len(history1.history['loss']),
        "phase2_epochs": len(history2.history['loss']),
        "phase1_best_val_acc": float(p1_val_acc),
        "phase2_best_val_acc": float(p2_val_acc),
    },
    "metrics": {
        "keras_test_accuracy": float(test_acc),
        "int8_test_accuracy": float(int8_acc),
        "accuracy_gap_pp": round(gap, 1),
    },
    "int8_per_class_recall": {
        CLASS_LABELS[c]: float(int8_pc[c][0] / max(int8_pc[c][1], 1))
        for c in range(NUM_CLASSES)
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
print(f"   ✅ {summary_path}")

# Calibration JSON
calibration = {
    "schema_version": "classifier-v1",
    "model_type": "classifier",
    "background_class_id": 0,
    "default": {"min_emit_conf100": 55, "min_margin_conf100": 20},
    "per_class": {
        lbl: {"min_emit_conf100": 55, "min_margin_conf100": 20}
        for lbl in CLASS_LABELS[1:]
    },
}
cal_path = OUTPUT_DIR / "fomo_calibration.json"
cal_path.write_text(json.dumps(calibration, indent=2), encoding="utf-8")
print(f"   ✅ {cal_path}")

print("\n✅ All artifacts exported!")

# %% [markdown]
# ## Cell 14: Mô Phỏng Demo
# Test model trên ảnh test để xem kết quả trực quan.

# %%
# ======================== CELL 14: DEMO VISUALIZATION ========================
fig, axes = plt.subplots(3, 6, figsize=(18, 9))
fig.suptitle('Int8 Model Predictions on Test Samples', fontsize=14)

# Pick random test samples
test_indices = np.random.choice(len(X_test), 18, replace=False)

for i, idx in enumerate(test_indices):
    row, col = i // 6, i % 6
    ax = axes[row, col]

    # Show image
    ax.imshow(X_test[idx])

    # Run inference
    inp_data = np.expand_dims(X_test[idx], axis=0).astype(np.uint8)
    interp.set_tensor(inp_d['index'], inp_data)
    interp.invoke()
    raw_out = interp.get_tensor(out_d['index'])[0]

    # Dequantize
    out_scale = out_d['quantization'][0]
    out_zp = out_d['quantization'][1]
    scores = (raw_out.astype(np.float32) - out_zp) * out_scale
    pred = int(np.argmax(scores))
    conf = float(scores[pred])
    true_label = int(Y_test[idx])

    # Color: green=correct, red=wrong
    color = 'green' if pred == true_label else 'red'
    ax.set_title(f"P:{CLASS_LABELS[pred][:8]}\nT:{CLASS_LABELS[true_label][:8]}\n{conf:.0%}",
                 fontsize=8, color=color)
    ax.axis('off')

plt.tight_layout()
plt.show()
print("🟢 Green = correct, 🔴 Red = wrong")

# %% [markdown]
# ## Cell 15: Download Files
# Download tất cả files cần thiết về máy.
#
# Copy `model_data.h` vào folder firmware ESP32-CAM, re-flash là xong!

# %%
# ======================== CELL 15: DOWNLOAD ========================
from google.colab import files

# Zip all output files
os.system('cd /content/output && zip -r /content/esp32cam_model.zip .')

print("📥 Downloading model files...")
print("   Contents:")
for f in sorted(OUTPUT_DIR.iterdir()):
    print(f"   - {f.name} ({f.stat().st_size:,} bytes)")

files.download('/content/esp32cam_model.zip')

print("\n✅ Download complete!")
print("\n📋 Tiếp theo:")
print("   1. Giải nén esp32cam_model.zip")
print("   2. Copy model_data.h vào folder firmware ESP32-CAM")
print("   3. Copy class_labels.txt vào folder models/")
print("   4. Flash firmware → test!")

# %% [markdown]
# ## ✅ XONG!
#
# ### Tóm tắt:
# - Model: MobileNetV2 alpha=0.5 classifier (NOT FOMO grid)
# - Input: 96x96x3 uint8 [0,255] — firmware feed raw pixels
# - Output: 1x5 uint8 — firmware dùng argmax
# - Rescaling layer INSIDE model → firmware không cần preprocess
# - Firmware tự detect classifier mode (output 5 elements thay vì 720)
#
# ### Files quan trọng:
# - `model_data.h` → copy vào ESP32-CAM sketch folder
# - `class_labels.txt` → copy vào models/
# - `fomo_summary.json` → metadata model
# - `classifier_gtsrb_int8.tflite` → dùng cho test_model_live_capture.py
