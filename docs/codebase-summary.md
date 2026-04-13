# Codebase Summary

## Current State
Repo tập trung vào phần dữ liệu, huấn luyện, đánh giá và artifact cho traffic-sign recognition trên ESP32-CAM. Theo `repomix-output.xml` vừa tạo, repo pack được 53 file text chính; dữ liệu ảnh và model nhị phân lớn bị loại khỏi output text nhưng vẫn tồn tại trong repo.

## Top-Level Summary
Dựa trên quét thư mục hiện có:

| Directory | Notes |
|---|---|
| `captures/` | Thư mục ảnh chụp thử, hiện trống hoặc gần như trống |
| `data/` | Lớn nhất; chứa raw GTSRB, split classifier, no-sign, và dataset FOMO |
| `docs/` | 4 tài liệu legacy/transition hiện có |
| `models/` | Artifact baseline classifier và canonical FOMO |
| `notebooks/` | 3 script/notebook cho train classifier/FOMO |
| `plans/` | Kế hoạch làm việc nội bộ |
| `reports/` | JSON eval và report pack FOMO |
| `scripts/` | Script chuẩn bị dữ liệu, train, evaluate, monitor |

## Verified Important Files

### Root
- `D:/DoAn_Robot/CLAUDE.md`
- `D:/DoAn_Robot/AGENTS.md`
- `D:/DoAn_Robot/release-manifest.json`
- `D:/DoAn_Robot/repomix-output.xml`
- `D:/DoAn_Robot/{PASS` - file lạ, chưa xác minh vai trò

### Docs
- `D:/DoAn_Robot/docs/colab_usage_guide.md`
- `D:/DoAn_Robot/docs/training_report.md`
- `D:/DoAn_Robot/docs/edge_impulse_setup.md`
- `D:/DoAn_Robot/docs/dataset_mapping.md`

### Models
- `D:/DoAn_Robot/models/classifier_gtsrb.keras`
- `D:/DoAn_Robot/models/classifier_gtsrb_float32.tflite`
- `D:/DoAn_Robot/models/classifier_gtsrb_int8.tflite`
- `D:/DoAn_Robot/models/traffic_sign_fomo_float32.tflite`
- `D:/DoAn_Robot/models/traffic_sign_fomo_int8.tflite`
- `D:/DoAn_Robot/models/model_data.h`
- `D:/DoAn_Robot/models/class_labels.txt`
- `D:/DoAn_Robot/models/fomo_summary.json`
- `D:/DoAn_Robot/models/fomo_eval_report.json`
- `D:/DoAn_Robot/models/fomo_calibration.json`

### Notebooks / Training Entry Points
- `D:/DoAn_Robot/notebooks/train_classifier_gtsrb.py`
- `D:/DoAn_Robot/notebooks/Train_Traffic_Sign_Classifier_Colab.py`
- `D:/DoAn_Robot/notebooks/train_fomo_detection.py`
- `D:/DoAn_Robot/notebooks/traffic_sign_training.ipynb`

### Scripts
Core canonical FOMO files:
- `D:/DoAn_Robot/scripts/esp32cam_fomo_contract.py`
- `D:/DoAn_Robot/scripts/esp32cam_fomo_dataset.py`
- `D:/DoAn_Robot/scripts/train_esp32cam_fomo.py`
- `D:/DoAn_Robot/scripts/evaluate_esp32cam_fomo.py`
- `D:/DoAn_Robot/scripts/generate_esp32cam_fomo_report.py`
- `D:/DoAn_Robot/scripts/capture_esp32cam_dataset.py`
- `D:/DoAn_Robot/scripts/prepare_esp32cam_fomo_manifest.py`
- `D:/DoAn_Robot/scripts/bootstrap_fomo_dataset_from_existing_data.py`
- `D:/DoAn_Robot/scripts/test_model_live_capture.py`
- `D:/DoAn_Robot/scripts/esp32_cam_live_dashboard.py`
- `D:/DoAn_Robot/scripts/run_no_sign_fp_monitor.py`
- `D:/DoAn_Robot/scripts/run_with_sign_monitor.py`

Legacy/baseline dataset prep files:
- `D:/DoAn_Robot/scripts/download_gtsrb.py`
- `D:/DoAn_Robot/scripts/filter_classes.py`
- `D:/DoAn_Robot/scripts/convert_images.py`
- `D:/DoAn_Robot/scripts/split_dataset.py`
- `D:/DoAn_Robot/scripts/validate_dataset.py`

### Reports
- `D:/DoAn_Robot/reports/esp32cam_fomo_test_eval.json`
- `D:/DoAn_Robot/reports/esp32cam_fomo_test_eval_t065.json`
- `D:/DoAn_Robot/reports/esp32cam_fomo_test_eval_float_t065.json`
- `D:/DoAn_Robot/reports/esp32cam_fomo_test_eval_int8_t065.json`
- `D:/DoAn_Robot/reports/esp32cam_fomo_test_eval_float_t070_v2.json`
- `D:/DoAn_Robot/reports/esp32cam_fomo_report_pack/esp32cam_fomo_report.md`

## Canonical ML Contract
Theo `scripts/esp32cam_fomo_contract.py`:
- `IMG_SIZE = 96`
- `FOMO_GRID_SIZE = 12`
- `NUM_CLASSES = 5`
- `CLASS_LABELS = [_background_, stop, speed_limit, warning, other_reg]`
- `EXPECTED_OUTPUT_SHAPE = (12, 12, 5)`
- `CANONICAL_SCHEMA = fomo-grid-v2`

## Baseline vs Canonical

| Topic | Baseline classifier | Canonical FOMO |
|---|---|---|
| Role | Debug / comparison | Current release path |
| Input | 96x96 RGB | 96x96 RGB |
| Output | 5-class vector | 12x12x5 grid |
| Preprocess | Center crop | Full-frame resize |
| Primary files | `train_classifier_gtsrb.py` | `train_esp32cam_fomo.py` |
| Current artifact evidence | `classifier_gtsrb_*.tflite` | `traffic_sign_fomo_*.tflite` + FOMO summary/eval |

## Artifact Evidence
`models/fomo_summary.json` confirms:
- schema `fomo-grid-v2`
- model type `fomo_grid_detector`
- input `[1,96,96,3]`
- output `[1,12,12,5]`

`models/fomo_eval_report.json` confirms domain-based FOMO evaluation exists for train/val/test.

`models/fomo_calibration.json` conflicts with the above because it declares `classifier-v1` and `model_type: classifier`.

## Reported Metrics Currently Present
From `reports/esp32cam_fomo_report_pack/esp32cam_fomo_report.md`:
- Canonical eval accuracy around `0.5996` train, `0.5900` val, `0.5433` test at threshold `0.65`
- Strict release test gate at threshold `0.7`, min votes `2`, lower accuracy than canonical eval

These are the metrics currently evidenced in repo; no higher claims should be documented.

## Legacy Docs Status
Current docs in `docs/` are useful as history/reference but not fully consistent with artifact state. Main issues:
- classifier/FOMO transition text mixed in same file
- Edge Impulse path no longer matches current canonical pipeline
- old class mappings not aligned to current 5-label contract

## Notes from Repomix
Generated file: `D:/DoAn_Robot/repomix-output.xml`

Notable pack summary:
- Text pack includes 53 files
- Binary `.tflite` and `.keras` artifacts excluded from text output
- Largest text-heavy inputs include raw CSV manifests and `models/model_data.h`

## Recommended Reading Order
1. `project-overview-pdr.md`
2. `system-architecture.md`
3. `deployment-guide.md`
4. legacy docs only if historical context is needed

## Unresolved Questions
- `release-manifest.json` appears large and likely historical, but current operational role is unclear.
- The exact provenance of the checked-in `models/model_data.h` remains unverified from filename alone.