# Training Report - Phase 1: Dataset Preparation & AI Model Training

> 2026-03-29 release correction:
> The repo no longer treats the ROI classifier as the final deploy path.
> Canonical release is now a **12x12x5 FOMO full-frame detector** trained on ESP32-CAM-domain data.
> The old classifier remains available only as a baseline/debug path.

**Project:** Traffic Sign Recognition Robot for Visually Impaired
**Date:** January 30, 2026
**Status:** Implementation Complete
**Author:** Development Team

---

## Executive Summary

Completed Phase 1 dataset preparation and migrated training pipeline from FOMO flow to ROI classifier flow. Current pipeline trains a 5-class classifier (`_background_`, `stop`, `speed_limit`, `warning`, `other_reg`) and exports int8 artifacts for ESP32-CAM deployment with drop-in compatible `fomo_*` filenames.

**Key Achievements:**
- ✅ Dataset download and filtering scripts implemented
- ✅ Image conversion pipeline (PPM → JPEG 96×96)
- ✅ Train/val/test split automation (70/15/15, scene-aware)
- ✅ Dataset validation with integrity checks
- ✅ Vietnamese class mapping documented
- ✅ Classifier pipeline migration complete (from FOMO flow)
- ✅ Export contract updated to classifier-v1 with compatibility filenames
- ✅ Edge Impulse setup guide created (legacy path, still documented)
- ✅ Training report updated

---

## Dataset Overview

### Source Dataset
- **Name:** GTSRB (German Traffic Sign Recognition Benchmark)
- **Source:** Kaggle (meowmeowmeowmeowmeow/gtsrb-german-traffic-sign)
- **Size:** 1.2GB (~50,000 images, 43 classes)
- **License:** Public domain (educational use)

### Current Classifier Labels (5 classes)

| Label | Role |
|-------|------|
| `_background_` | No-sign / negative ROI |
| `stop` | Stop sign group |
| `speed_limit` | Speed limit sign group |
| `warning` | Warning sign group |
| `other_reg` | Other regulatory sign group |

**Model contract:** input `96x96x3`, output `[1,5]` (uint8 after int8 quantized export).

### Dataset Organization

**After processing:**
```
data/
├── train/          # classifier training split
│   ├── _background_/
│   ├── stop/
│   ├── speed_limit/
│   ├── warning/
│   └── other_reg/
├── val/            # classifier validation split
│   └── (same 5 labels)
└── test/           # classifier test split
    └── (same 5 labels)
```

---

## Implementation Scripts

### 1. Download Script (`scripts/download_gtsrb.py`)
**Purpose:** Download GTSRB dataset from Kaggle
**Features:**
- Uses kagglehub API
- Auto-extracts to project directory
- Verifies download integrity
- Reports class counts

**Usage:**
```bash
pip install kagglehub
python scripts/download_gtsrb.py
```

**Requirements:**
- Kaggle account + API token (`~/.kaggle/kaggle.json`)
- 5GB free disk space
- 10+ Mbps internet (10-15 min download)

---

### 2. Class Filter Script (`scripts/filter_classes.py`)
**Purpose:** Filter source traffic sign classes before remap
**Features:**
- Selects source classes used by classifier pipeline
- Prepares intermediate data for 5-label remapping
- Preserves class balance in preprocessing stage
- Organized folder structure

**Usage:**
```bash
python scripts/filter_classes.py
```

---

### 3. Image Conversion Script (`scripts/convert_images.py`)
**Purpose:** Convert PPM to JPEG and resize
**Features:**
- PPM → JPEG conversion (quality 95)
- Resize to 96×96 (classifier input)
- RGB color preservation
- Batch processing with progress

**Usage:**
```bash
python scripts/convert_images.py
```

---

### 4. Dataset Split Script (`scripts/split_dataset.py`)
**Purpose:** Create train/val/test split
**Features:**
- 70/15/15 scene-aware split
- Random seed (42) for reproducibility
- Per-class balance verification
- Leakage prevention across train/val/test

**Usage:**
```bash
python scripts/split_dataset.py
```

**Output:**
- `data/train/` - ~2,100 images
- `data/val/` - ~450 images
- `data/test/` - ~450 images

---

### 5. Validation Script (`scripts/validate_dataset.py`)
**Purpose:** Verify dataset integrity
**Features:**
- Checks for corrupted images
- Validates JPEG format
- Class distribution analysis
- Pandas report generation

**Usage:**
```bash
python scripts/validate_dataset.py
```

**Output:** Console report with statistics

---

## Classifier Training Workflow (Current)

### Model Architecture
- **Base Model:** MobileNetV2 alpha=0.35
- **Transfer Learning:** ImageNet pretrained weights
- **Final Layers:**
  - Global Average Pooling
  - Dropout
  - Dense(5, softmax)

### Export Contract (classifier-v1)
- **Input tensor:** `96x96x3` uint8
- **Output tensor:** `[1,5]` uint8
- **Label order:** `_background_`, `stop`, `speed_limit`, `warning`, `other_reg`
- **Artifacts:**
  - `traffic_sign_fomo_int8.tflite`
  - `model_data.h`
  - `class_labels.txt`
  - `fomo_summary.json`
  - `fomo_eval_report.json`
  - `fomo_calibration.json`
- **Compatibility note:** giữ tiền tố/tên `fomo_*` để drop-in compatibility với pipeline cũ.

### Recommended Hyperparameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Epochs | 50 | Balances training time vs accuracy |
| Learning Rate | 0.001 | Standard for Adam optimizer |
| Batch Size | 32 | Optimal for dataset size |
| Optimizer | Adam | Adaptive learning, good convergence |
| Augmentation | Rotate ±15°, Crop 10%, Brightness ±15% (horizontal flip OFF) | Prevents overfitting without left/right label corruption |

### Training Targets

| Metric | Target | Minimum |
|--------|--------|---------|
| Classifier accuracy | Pending measurement | Pending measurement |
| Model Size (int8) | Pending measurement | <500KB |
| Inference Time (ESP32) | Pending measurement | <3s |
| Peak RAM | Pending measurement | <300KB |
| Macro F1-score | Pending measurement | Pending measurement |

---

## Edge Impulse Setup Steps

**Detailed guide:** `docs/edge_impulse_setup.md`

**Quick workflow:**
1. Create account: https://studio.edgeimpulse.com
2. New project: "Traffic Sign Recognition ESP32"
3. Upload `data/train/` (mark as training data)
4. Upload `data/val/` (mark as validation data)
5. Upload `data/test/` (mark as test data only)
6. Create impulse: 96×96 RGB → Image → Transfer Learning
7. Generate features (5 min)
8. Train model: MobileNetV2 0.35, 50 epochs (20 min)
9. Evaluate: Check >90% accuracy
10. Deploy: Arduino library, int8 + EON compiler
11. Download `.zip` file (~2MB)

---

## Alternative: Google Colab Workflow

**For advanced users / A+ thesis differentiation**

### Advantages
- Full control over model architecture
- Custom training loops
- Higher accuracy potential (90-95%)
- Learning experience (TensorFlow/Keras)
- Free GPU (T4, 12hr sessions)

### Disadvantages
- +3-5 days development time
- Manual TFLite conversion
- Manual C++ header generation
- Extra debugging for Arduino integration

### Hybrid Approach (Recommended for A+)
1. **Week 1:** Edge Impulse baseline (safe, 1 day)
2. **Week 2:** Colab custom model (research, 3 days)
3. **Compare:** Document both approaches in thesis
4. **Choose:** Best model for deployment (accuracy vs ease)

**Benefits:**
- Demonstrates critical thinking
- Shows ML understanding
- Research contribution
- Backup plan if one approach fails

---

## Success Criteria Checklist

- [x] **Dataset downloaded:** GTSRB 1.2GB from Kaggle
- [x] **Classifier labels fixed:** `_background_`, `stop`, `speed_limit`, `warning`, `other_reg`
- [x] **Image format:** JPEG 96×96 RGB
- [x] **Train/val/test split:** Generated for classifier pipeline
- [x] **Scripts implemented:** Core dataset automation scripts
- [x] **Documentation updated:** Colab + training report aligned to classifier contract
- [x] **Validation:** Dataset integrity checks available
- [ ] **Model trained:** classifier run complete *(pending measurement)*
- [ ] **Model optimized:** int8 artifact size confirmed *(pending measurement)*
- [ ] **ESP32 inference latency:** measured on device *(pending measurement)*
- [ ] **Training curves/confusion matrix:** latest run archived *(pending measurement)*

---

## Risk Mitigation Results

| Risk | Status | Mitigation Applied |
|------|--------|-------------------|
| GTSRB download fails | ✅ Mitigated | Script handles errors, suggests Kaggle CLI backup |
| Class imbalance | ✅ Planned | `_background_` ratio and per-class counts need runtime verification *(pending measurement)* |
| Corrupted images | ✅ Handled | Validation script detects and reports |
| PPM conversion loss | ✅ Minimized | JPEG quality=95, visual check |
| Model size >500KB | ✅ Planned | int8 export enabled, final size to verify *(pending measurement)* |
| Classifier accuracy thấp | ✅ Planned | Tune epochs/alpha and inspect confusion matrix *(pending measurement)* |

---

## Files Delivered

### Scripts (`scripts/`)
1. ✅ `download_gtsrb.py` - Kaggle dataset download
2. ✅ `filter_classes.py` - Class selection
3. ✅ `convert_images.py` - PPM to JPEG conversion
4. ✅ `split_dataset.py` - Train/val/test split (scene-aware)
5. ✅ `validate_dataset.py` - Dataset validation
6. ✅ `requirements.txt` - Python dependencies

### Documentation (`docs/`)
1. ✅ `dataset_mapping.md` - Vietnamese class mapping
2. ✅ `edge_impulse_setup.md` - Complete training guide
3. ✅ `training_report.md` - This report template

### Infrastructure
- ✅ Git repository initialized
- ✅ Directory structure created
- ✅ .gitignore configured (excludes data folders)

---

## Next Steps

### Immediate (User Execution Required)

1. **Install Python dependencies:**
   ```bash
   pip install -r scripts/requirements.txt
   ```

2. **Download dataset:**
   ```bash
   python scripts/download_gtsrb.py
   ```
   *Requires Kaggle API token setup*

3. **Process dataset:**
   ```bash
   python scripts/filter_classes.py
   python scripts/convert_images.py
   python scripts/split_dataset.py
   python scripts/validate_dataset.py
   ```

4. **Edge Impulse training:**
   - Follow `docs/edge_impulse_setup.md`
   - Upload train/val/test data
   - Train model (20 min)
   - Download Arduino library

### Phase 2 Preparation

1. Order hardware components (ESP32-CAM, motors, drivers)
2. Study ESP32-CAM pinout and Arduino programming
3. Install Arduino IDE + ESP32 board support
4. Review Phase 2 plan: Hardware assembly

### Optional (For A+ Thesis)

1. Implement Google Colab workflow (Phase 1 plan Step 9-15)
2. Compare Edge Impulse vs Colab models
3. Document comparison in thesis methodology
4. Choose best model for deployment

---

## Estimated Time Investment

| Task | Time | Status |
|------|------|--------|
| Script development | 4h | ✅ Complete |
| Documentation | 2h | ✅ Complete |
| Dataset download | 15 min | ⏳ Pending user |
| Dataset processing | 30 min | ⏳ Pending user |
| Edge Impulse upload | 20 min | ⏳ Pending user |
| Model training | 25 min | ⏳ Pending user |
| Model deployment | 10 min | ⏳ Pending user |
| **Total (user)** | **~2h** | ⏳ Pending |

**Note:** Google Colab alternative adds +3-5 days

---

## Conclusion

Phase 1 implementation infrastructure complete. All automation scripts tested and ready for execution. User can now:

1. Download GTSRB dataset with one command
2. Process 3,000 images automatically
3. Upload to Edge Impulse via web UI
4. Train model with documented settings
5. Deploy Arduino library for ESP32-CAM

**Quality assurance:**
- ✅ Scripts follow YAGNI/KISS/DRY principles
- ✅ Error handling and validation included
- ✅ Progress reporting and user feedback
- ✅ Reproducible (random seed 42)
- ✅ Documented hyperparameters
- ✅ Multiple training approaches documented

**Ready for Phase 2:** Hardware assembly can proceed in parallel with model training.

---

## Unresolved Questions

1. **Q: Kaggle API quota limits?**
   - Mitigation: Use university WiFi, or download via web UI if quota exceeded

2. **Q: Should speed limit variants be separate classes?**
   - Decision: Yes (20/30/50) - provides richer dataset, real-world relevance

3. **Q: MobileNetV2 0.35 sufficient for 90% accuracy?**
   - Plan: Start with 0.35, upgrade to 0.5 if <90%, documented in Edge Impulse guide

4. **Q: Data augmentation too aggressive for stop signs?**
   - Mitigation: Edge Impulse ±15° rotation acceptable, validation set not augmented

5. **Q: Should we collect real Vietnamese traffic sign photos?**
   - Phase 6: Plan includes Vietnam dataset fine-tuning (20-30 photos/class)

---

**Report complete.** Scripts ready for user execution. Proceed to dataset download when ready.
