# Deployment Guide

## Scope
Tài liệu này chỉ bao phủ phần deployment artifact và quy trình ML đã xác minh trong repo. Nó không thay thế hướng dẫn firmware đầy đủ vì firmware production path chưa hiện diện rõ trong root repo hiện tại.

## Canonical Deployment Artifact Set
Theo `scripts/train_esp32cam_fomo.py` và artifact hiện có trong `models/`, bộ artifact canonical gồm:
- `traffic_sign_fomo_float32.tflite`
- `traffic_sign_fomo_int8.tflite`
- `model_data.h`
- `class_labels.txt`
- `fomo_summary.json`
- `fomo_eval_report.json`

## Canonical Model Contract
- Labels: `_background_`, `stop`, `speed_limit`, `warning`, `other_reg`
- Input: `[1,96,96,3]`
- Output: `[1,12,12,5]`
- Schema: `fomo-grid-v2`

## Recommended Release Path
1. Chuẩn bị/canonicalize dữ liệu FOMO.
2. Train model bằng `scripts/train_esp32cam_fomo.py` hoặc launcher `notebooks/train_fomo_detection.py`.
3. Evaluate model bằng `scripts/evaluate_esp32cam_fomo.py`.
4. Tạo report pack bằng `scripts/generate_esp32cam_fomo_report.py`.
5. Chỉ dùng artifact sau khi metadata summary/eval khớp contract FOMO.

## Local Commands
```bash
pip install -r scripts/requirements.txt
python scripts/prepare_esp32cam_fomo_manifest.py
python notebooks/train_fomo_detection.py --manifest data/esp32cam-fomo/fomo_manifest.csv
python scripts/evaluate_esp32cam_fomo.py --model models/traffic_sign_fomo_int8.tflite
python scripts/generate_esp32cam_fomo_report.py
```

## Validation Checks Before Release
- `models/class_labels.txt` đúng thứ tự 5 labels canonical.
- `models/fomo_summary.json` ghi:
  - schema `fomo-grid-v2`
  - model type `fomo_grid_detector`
  - output `[1,12,12,5]`
- `models/fomo_eval_report.json` tồn tại và có số liệu cho split cần dùng.
- `reports/esp32cam_fomo_report_pack/esp32cam_fomo_report.md` được cập nhật nếu cần báo cáo.

## Live Verification Tools
- `scripts/test_model_live_capture.py`
- `scripts/esp32_cam_live_dashboard.py`
- `scripts/run_no_sign_fp_monitor.py`
- `scripts/run_with_sign_monitor.py`

Các tool này hữu ích để xác minh model hoạt động trên stream/capture, nhưng không thay thế một release benchmark chuẩn hóa.

## Baseline Classifier Note
Artifact classifier vẫn tồn tại:
- `classifier_gtsrb_float32.tflite`
- `classifier_gtsrb_int8.tflite`

Chúng nên được xem là baseline/debug artifact, không phải release mặc định.

## Known Deployment Caveats
- `fomo_calibration.json` đang mang schema classifier, không nên dùng làm bằng chứng duy nhất cho canonical release.
- `model_data.h` tồn tại nhưng cần cẩn thận xác nhận nguồn export gần nhất nếu dùng cho firmware.
- Tài liệu Edge Impulse hiện chỉ nên dùng làm tài liệu lịch sử/tham khảo.

## Minimum Release Checklist
- [ ] Canonical manifest đã chuẩn hóa
- [ ] Train/eval chạy thành công
- [ ] Summary/eval metadata khớp FOMO contract
- [ ] Header/model artifact đồng nguồn export
- [ ] Có bằng chứng kiểm thử runtime phù hợp mục tiêu sử dụng

## Unresolved Questions
- Firmware đang nạp `model_data.h` trực tiếp hay dùng `.tflite` qua bước chuyển đổi khác?
- Có cần một manifest release riêng cho FOMO artifact mới hơn `release-manifest.json` không?