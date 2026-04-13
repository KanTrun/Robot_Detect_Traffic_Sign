# Project Overview & PDR

## Overview
Repo này phục vụ bài toán nhận diện biển báo giao thông cho robot/thiết bị hỗ trợ thị giác, với trọng tâm hiện tại là inference trên ESP32-CAM. Repo đang chứa đồng thời pipeline baseline classifier và pipeline canonical FOMO.

## Problem Statement
Thiết bị cần nhận diện nhanh nhóm biển báo chính từ ảnh camera độ phân giải thấp, với artifact đủ nhỏ để dùng trên thiết bị nhúng và quy trình dữ liệu có thể lặp lại.

## Verified Scope
Hiện repo đã có:
- Script xử lý dữ liệu classifier-style từ GTSRB.
- Script capture/manifest/train/evaluate cho FOMO ESP32-CAM.
- Artifact model baseline classifier và artifact canonical FOMO trong `models/`.
- Report pack FOMO trong `reports/esp32cam_fomo_report_pack/`.

Repo chưa cho thấy đầy đủ firmware production trong root hiện tại, nên tài liệu này chỉ mô tả phần ML/data/tooling đã xác minh.

## Product Goals
1. Duy trì một release path rõ ràng cho ESP32-CAM.
2. Giữ baseline classifier để debug, so sánh, hoặc fallback nghiên cứu.
3. Chuẩn hóa dữ liệu, manifest, label order, input/output contract.
4. Giảm nhầm lẫn giữa tài liệu legacy và pipeline canonical.

## Current Pipelines

### Baseline classifier
- Mục tiêu: baseline/debug path.
- Input: `96x96x3`
- Output: `5` lớp
- Labels: `_background_`, `stop`, `speed_limit`, `warning`, `other_reg`
- Nguồn chính:
  - `notebooks/train_classifier_gtsrb.py`
  - `notebooks/Train_Traffic_Sign_Classifier_Colab.py`
  - `models/classifier_gtsrb_float32.tflite`
  - `models/classifier_gtsrb_int8.tflite`

### Canonical FOMO
- Mục tiêu: release path hiện tại theo artifact và contract đang có.
- Input: `[1,96,96,3]`
- Output: `[1,12,12,5]`
- Schema: `fomo-grid-v2`
- Model type: `fomo_grid_detector`
- Nguồn chính:
  - `scripts/esp32cam_fomo_contract.py`
  - `scripts/train_esp32cam_fomo.py`
  - `scripts/evaluate_esp32cam_fomo.py`
  - `models/traffic_sign_fomo_float32.tflite`
  - `models/traffic_sign_fomo_int8.tflite`
  - `models/fomo_summary.json`
  - `models/fomo_eval_report.json`

## Canonical Decision for Docs
Bộ docs cốt lõi này xem FOMO là canonical pipeline hiện tại vì:
- Contract tập trung được định nghĩa riêng trong `scripts/esp32cam_fomo_contract.py`.
- Train/eval/report scripts đang kiểm tra chặt output grid 12x12x5.
- Artifact summary/eval trong `models/` khớp contract FOMO.

Baseline classifier vẫn được ghi nhận, nhưng không được mô tả là release path.

## Verified Data Assets
- `data/gtsrb_raw/` - raw dataset lớn.
- `data/gtsrb_filtered/` - dữ liệu đã lọc.
- `data/train|val|test/` - split kiểu classifier.
- `data/no_sign/`, `data/_zz_no_sign_excess/` - negative samples.
- `data/esp32cam-fomo/generated/` và `data/esp32cam-fomo/fomo_manifest.csv` - nguồn cho FOMO.

## Functional Requirements
1. Hệ thống dữ liệu phải giữ đúng 5 labels theo thứ tự canonical.
2. Pipeline FOMO phải sinh được artifact TFLite float32/int8 và metadata summary/eval.
3. Pipeline evaluate phải từ chối model không có output đúng 12x12x5.
4. Baseline classifier phải vẫn test được bằng tool live capture hiện có.
5. Tài liệu phải nêu rõ phần nào canonical, phần nào legacy.

## Non-Functional Requirements
- Tài liệu súc tích, dựa trên bằng chứng từ repo.
- File docs giữ dưới giới hạn vận hành thông thường.
- Hướng dẫn chạy script phải tái lập được từ root repo.
- Không mô tả tính năng firmware/hardware chưa xác minh trong repo hiện tại.

## Acceptance Criteria
- Có README ngắn gọn cho repo.
- Có bộ docs cốt lõi thống nhất trong `docs/`.
- Bộ docs nêu rõ dual-pipeline state và canonical decision.
- Các mâu thuẫn đã biết được ghi chú công khai.

## Known Inconsistencies
1. `fomo_calibration.json` vẫn mang schema classifier.
2. `docs/colab_usage_guide.md` và `docs/training_report.md` còn trộn release update FOMO với nội dung classifier cũ.
3. `docs/edge_impulse_setup.md` còn tham chiếu nhãn/số lớp kiểu legacy.
4. `docs/dataset_mapping.md` mô tả mapping 15 lớp tiếng Việt, không khớp 5-label canonical hiện tại.

## Success Metrics
Trong phạm vi tài liệu ban đầu, thành công là:
- Người mới vào repo xác định được canonical pipeline trong <10 phút.
- Không còn phải suy luận từ artifact tên `fomo_*` nhưng nội dung classifier.
- Bộ docs cốt lõi nhất quán hơn các tài liệu legacy.

## Out of Scope
- Sửa code train/eval/runtime.
- Hợp nhất hay xóa pipeline legacy.
- Xác nhận benchmark phần cứng thực tế nếu chưa có file chứng cứ trong repo.

## Unresolved Questions
- `models/model_data.h` hiện khớp artifact FOMO hay artifact classifier ở lần export gần nhất?
- `fomo_calibration.json` có nên được thay bằng calibration schema riêng cho FOMO không?
- Release-manifest hiện thuộc quy trình phát hành nào và có còn được bảo trì không?