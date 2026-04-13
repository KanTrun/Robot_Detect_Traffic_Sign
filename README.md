# DoAn_Robot

Repository cho đồ án robot nhận diện biển báo giao thông, hiện tập trung vào pipeline thị giác cho ESP32-CAM.

## Trạng thái hiện tại
- Repo đang có 2 hướng pipeline:
  - Baseline classifier: phân loại ROI 5 lớp từ dữ liệu GTSRB đã crop/reshape.
  - Canonical FOMO: detector full-frame 12x12x5 cho ESP32-CAM.
- Theo artifact hiện có trong `models/` và script contract trong `scripts/esp32cam_fomo_contract.py`, pipeline canonical hiện tại là FOMO với:
  - input `[1,96,96,3]`
  - output `[1,12,12,5]`
  - labels `_background_`, `stop`, `speed_limit`, `warning`, `other_reg`
  - schema `fomo-grid-v2`
- Tuy vậy repo vẫn còn dấu vết legacy classifier trong tài liệu và một số metadata, nên cần đọc `docs/` trước khi dùng.

## Cấu trúc chính
- `docs/` - tài liệu chuẩn của repo
- `scripts/` - script chuẩn bị dữ liệu, train, evaluate, monitoring
- `notebooks/` - notebook/script huấn luyện baseline classifier và launcher FOMO
- `models/` - artifact model xuất ra
- `data/` - dữ liệu raw, split classifier-style, no-sign, và dataset FOMO
- `reports/` - báo cáo đánh giá và report pack FOMO
- `captures/` - ảnh chụp thử từ ESP32-CAM

## Pipeline trong repo

### 1. Baseline classifier
Mục đích: đối chứng/debug, không nên xem là release path hiện tại.

Nguồn bằng chứng:
- `notebooks/train_classifier_gtsrb.py`
- `notebooks/Train_Traffic_Sign_Classifier_Colab.py`
- `models/classifier_gtsrb_float32.tflite`
- `models/classifier_gtsrb_int8.tflite`

Đặc điểm:
- Input 96x96 RGB
- Output 5 logits/class probabilities
- Preprocess runtime dạng center crop trong `scripts/test_model_live_capture.py`

### 2. Canonical FOMO release pipeline
Mục đích: pipeline release hiện được repo ưu tiên.

Nguồn bằng chứng:
- `scripts/esp32cam_fomo_contract.py`
- `scripts/train_esp32cam_fomo.py`
- `scripts/evaluate_esp32cam_fomo.py`
- `notebooks/train_fomo_detection.py`
- `models/traffic_sign_fomo_float32.tflite`
- `models/traffic_sign_fomo_int8.tflite`
- `models/fomo_summary.json`
- `models/fomo_eval_report.json`

Luồng chuẩn:
1. Thu frame/annotation với `scripts/capture_esp32cam_dataset.py`
2. Chuẩn hóa manifest bằng `scripts/prepare_esp32cam_fomo_manifest.py`
3. Có thể bootstrap dữ liệu bằng `scripts/bootstrap_fomo_dataset_from_existing_data.py`
4. Train bằng `scripts/train_esp32cam_fomo.py` hoặc launcher `notebooks/train_fomo_detection.py`
5. Evaluate bằng `scripts/evaluate_esp32cam_fomo.py`
6. Tạo report pack bằng `scripts/generate_esp32cam_fomo_report.py`

## Mâu thuẫn cần biết
- `models/fomo_summary.json` và `models/fomo_eval_report.json` mô tả FOMO canonical.
- `models/fomo_calibration.json` lại ghi `schema_version: classifier-v1` và `model_type: classifier`.
- Một số docs cũ còn trộn Edge Impulse/15-class, classifier 1x5, và FOMO 12x12x5.
- `models/model_data.h` tồn tại nhưng không xác nhận chỉ bằng tên là được sinh từ artifact nào; script train FOMO hiện ghi header từ `traffic_sign_fomo_float32.tflite`.

## Tài liệu nên đọc trước
- `docs/project-overview-pdr.md`
- `docs/codebase-summary.md`
- `docs/system-architecture.md`
- `docs/code-standards.md`
- `docs/project-roadmap.md`
- `docs/deployment-guide.md`
- `docs/design-guidelines.md`

## Tài liệu legacy vẫn giữ lại
- `docs/colab_usage_guide.md`
- `docs/training_report.md`
- `docs/edge_impulse_setup.md`
- `docs/dataset_mapping.md`

Các file này vẫn có giá trị tham khảo lịch sử, nhưng không nên dùng làm source of truth khi có mâu thuẫn với bộ docs cốt lõi.

## Thiết lập môi trường tối thiểu
1. Cài Python 3.10+.
2. Cài dependency script:
   ```bash
   pip install -r scripts/requirements.txt
   ```
3. Kiểm tra dữ liệu và artifact trước khi chạy train/eval.

## Gợi ý bắt đầu nhanh
- Muốn hiểu repo: đọc `docs/project-overview-pdr.md`.
- Muốn train baseline classifier: xem `notebooks/train_classifier_gtsrb.py`.
- Muốn đi theo release path hiện tại: xem `notebooks/train_fomo_detection.py` và `docs/deployment-guide.md`.
- Muốn kiểm tra live model với ESP32-CAM: xem `scripts/test_model_live_capture.py`.

## Ghi chú
- Repo hiện chưa có README cũ; file này là bản tóm tắt ban đầu.
- Tài liệu chi tiết đã được chuẩn hóa lại trong `docs/` và nên được xem là source of truth.
# Robot_Detect_Traffic_Sign
