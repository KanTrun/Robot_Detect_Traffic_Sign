# System Architecture

## Architecture Scope
Tài liệu này mô tả kiến trúc phần repo đã xác minh: data preparation, model training, evaluation, artifact export, và tool hỗ trợ runtime kiểm thử.

## High-Level View

```text
Raw/sign datasets + no-sign corpus
        |
        +--> Baseline classifier prep/train path
        |
        +--> ESP32-CAM FOMO capture + manifest path
                         |
                         v
                 canonical manifest
                         |
                         v
                 FOMO train/evaluate/export
                         |
                         v
                  models/ + reports/
                         |
                         v
              live capture test / monitoring tools
```

## Main Architectural Tracks

### 1. Baseline classifier track
Mục đích: baseline và debug path.

Components đã xác minh:
- `scripts/download_gtsrb.py`
- `scripts/filter_classes.py`
- `scripts/convert_images.py`
- `scripts/split_dataset.py`
- `scripts/validate_dataset.py`
- `notebooks/train_classifier_gtsrb.py`
- `notebooks/Train_Traffic_Sign_Classifier_Colab.py`

Data style:
- dữ liệu được crop/convert rồi chia `train/val/test`
- model output là vector 5 lớp

### 2. Canonical FOMO track
Mục đích: current release path cho ESP32-CAM theo artifact hiện có.

Components đã xác minh:
- `scripts/capture_esp32cam_dataset.py`
- `scripts/prepare_esp32cam_fomo_manifest.py`
- `scripts/bootstrap_fomo_dataset_from_existing_data.py`
- `scripts/esp32cam_fomo_contract.py`
- `scripts/esp32cam_fomo_dataset.py`
- `scripts/train_esp32cam_fomo.py`
- `scripts/evaluate_esp32cam_fomo.py`
- `scripts/generate_esp32cam_fomo_report.py`

Data style:
- frame full-image 96x96
- annotation bbox trong manifest
- split theo train/val/test và có domain summary print/screen trong report

## Canonical FOMO Contract Layer
`esp32cam_fomo_contract.py` đóng vai trò contract trung tâm cho:
- image size
- grid size
- số lớp
- label order
- artifact names
- default manifest paths
- release decode defaults

Đây là lý do docs xem file này là architectural anchor cho pipeline canonical.

## Training and Export Flow

### FOMO flow
1. Input lấy từ canonical manifest `data/esp32cam-fomo/fomo_manifest.csv`.
2. Dataset loader biến annotation thành tensor/grid labels.
3. `train_esp32cam_fomo.py` build model conv nhỏ, train với weighted grid loss.
4. Script export:
   - float32 TFLite
   - int8 TFLite
   - `model_data.h`
   - `class_labels.txt`
   - `fomo_summary.json`
   - `fomo_eval_report.json`
5. `generate_esp32cam_fomo_report.py` đóng gói markdown + charts vào `reports/esp32cam_fomo_report_pack/`.

### Baseline flow
1. Dữ liệu từ GTSRB/raw + split classifier directories.
2. Notebook/script train MobileNetV2 classifier.
3. Export baseline `.tflite` riêng và metadata classifier-style.

## Runtime Test Layer
Các script hỗ trợ kiểm thử hiện có:
- `scripts/test_model_live_capture.py` - auto-detect classifier vs FOMO dựa vào số phần tử output.
- `scripts/esp32_cam_live_dashboard.py` - dashboard stream + serial metrics.
- `scripts/run_no_sign_fp_monitor.py` - theo dõi false positives khi không có biển.
- `scripts/run_with_sign_monitor.py` - theo dõi khi có biển.

Một điểm quan trọng đã xác minh:
- test tool dùng preprocess khác nhau cho 2 model types:
  - FOMO: full-frame resize
  - classifier: center crop

## Data and Artifact Boundaries

| Layer | Input | Output |
|---|---|---|
| Dataset prep | raw sign images / captures | split dirs / manifest |
| Train | split tensors | trained keras/tflite model |
| Export | trained model | header + metadata + tflite |
| Evaluate | model + manifest/split | JSON report |
| Report pack | summary + eval + strict test | markdown + plots |

## Current Canonical Evidence
Kiến trúc canonical được hỗ trợ bởi:
- contract file đặt hằng số FOMO
- train script kiểm tra output `(12,12,5)`
- eval script từ chối output không đúng dạng FOMO
- `models/fomo_summary.json` và `models/fomo_eval_report.json` theo schema FOMO

## Known Architecture Gaps
- `fomo_calibration.json` chưa đồng bộ với canonical FOMO metadata.
- Legacy docs vẫn phản ánh một kiến trúc classifier-first hoặc Edge Impulse-first.
- Firmware production path không nằm rõ trong root hiện tại, nên chưa mô tả sâu hơn.

## Runtime Firmware Note
- Sketch tích hợp ESP32-S3 tại `D:/DoAn_Robot/.claude/tmp/test_esp32s3_phase05_integration/test_esp32s3_phase05_integration.ino` hiện đã có:
  - sonar scan luân phiên `C-L-C-R`
  - fail-safe obstacle FSM
  - `STARTUP_STRAIGHT` để xe không nhảy cruise ngay lúc release
  - `TURN_SETTLE` sau steer/reverse arc để caster tự align lại
  - heading-hold ngắn hạn bằng `MPU6050::getAngleZ()` để bù lệch đầu hành trình
- Runtime hardware evidence mới cho tuning caster vẫn còn pending.

## Architecture Decision Record
### Decision
Dùng FOMO làm canonical documentation path.

### Why
- Có contract chuyên biệt.
- Có artifact, eval, report pack khớp nhau.
- Có tool runtime test hỗ trợ cả FOMO lẫn classifier, chứng tỏ classifier là compatibility/baseline path.

### Consequence
- Docs phải luôn nêu rõ dual-path state.
- Các metadata/legacy docs chưa đồng bộ phải được đánh dấu là inconsistency, không che đi.

## Unresolved Questions
- `model_data.h` đang đại diện cho FOMO float32 export ở bản nào?
- Runtime firmware tiêu thụ `fomo_calibration.json` hay metadata nào khác hiện chưa thấy trong repo?
