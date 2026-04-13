# Code Standards

## Purpose
Tài liệu này mô tả chuẩn thực tế cho repo hiện tại, tập trung vào phần dữ liệu, train, evaluate và documentation. Nó không áp đặt framework mới ngoài những gì đã thấy trong codebase.

## Source of Truth
- Tài liệu chuẩn nằm trong `D:/DoAn_Robot/docs/`.
- Khi docs legacy mâu thuẫn với bộ docs cốt lõi, ưu tiên bộ docs cốt lõi này.
- Khi mô tả code contract, phải bám artifact và script đã xác minh.

## Directory Intent

| Path | Purpose |
|---|---|
| `docs/` | tài liệu chuẩn, ngắn gọn, cập nhật |
| `scripts/` | script vận hành chính cho data/train/eval/monitor |
| `notebooks/` | notebook hoặc launcher phục vụ training experiments |
| `models/` | artifact export và metadata |
| `reports/` | báo cáo đánh giá sinh ra từ script |
| `data/` | dữ liệu nguồn, dữ liệu sinh ra, manifest |
| `captures/` | ảnh capture thủ công/runtime test |

## Naming
- File Python mới hoặc đổi tên nên dùng kebab-case nếu là file tài liệu/shell, và snake_case cho script Python đang theo convention hiện tại.
- Label/class phải giữ đúng case và thứ tự canonical:
  - `_background_`
  - `stop`
  - `speed_limit`
  - `warning`
  - `other_reg`
- Không tự đổi tên artifact canonical:
  - `traffic_sign_fomo_float32.tflite`
  - `traffic_sign_fomo_int8.tflite`
  - `model_data.h`
  - `class_labels.txt`
  - `fomo_summary.json`
  - `fomo_eval_report.json`

## Documentation Standards
- Viết ngắn, dựa trên bằng chứng.
- Không khẳng định accuracy, latency, hay hardware behavior nếu repo không có file chứng minh.
- Khi nói về canonical pipeline, phải nêu rõ đây là FOMO 12x12x5.
- Khi nói về baseline classifier, phải nêu rõ đây là baseline/debug path.
- File docs nên dưới 800 dòng; nếu lớn hơn phải tách module.

## Python Script Standards
Áp dụng theo style đang hiện diện trong repo:
- Có `argparse` cho entry-point CLI.
- Dùng `Path` thay vì ghép path thủ công nếu có thể.
- Ghi file output qua JSON/CSV/text rõ ràng.
- Kiểm tra contract quan trọng bằng guard rõ ràng.

Ví dụ đã xác minh:
- `train_esp32cam_fomo.py` kiểm tra `model.output_shape` khớp `(12, 12, 5)`.
- `evaluate_esp32cam_fomo.py` từ chối model không có đúng số phần tử output FOMO.

## Data Contract Standards
- Label order phải thống nhất giữa:
  - `scripts/esp32cam_fomo_contract.py`
  - `models/class_labels.txt`
  - metadata/report liên quan
- Manifest FOMO canonical phải đi qua bước chuẩn hóa bằng `prepare_esp32cam_fomo_manifest.py`.
- BBox phải tồn tại cho row có sign trước khi xem là canonical-ready.

## Model Contract Standards

### Canonical FOMO
- Input shape: `[1,96,96,3]`
- Output shape: `[1,12,12,5]`
- Schema: `fomo-grid-v2`
- Model type: `fomo_grid_detector`

### Baseline classifier
- Input shape: `96x96x3`
- Output elements: `5`
- Schema thường thấy trong metadata cũ: `classifier-v1`

## Reporting Standards
- Báo cáo sinh từ script nên đặt trong `reports/`.
- Nếu là report pack, giữ tất cả ảnh/CSV/Markdown trong một thư mục riêng như `reports/esp32cam_fomo_report_pack/`.
- Chỉ ghi các metric có thật trong file report/checkpoint hiện có.

## README and Doc Hygiene
- README giữ ngắn gọn, dưới 300 dòng.
- README chỉ làm entry point; chi tiết dồn về `docs/`.
- Legacy docs không xóa nếu còn giá trị tham khảo, nhưng phải được định vị là supplemental.

## Change Management for Docs
Khi cập nhật code liên quan pipeline:
1. Kiểm tra `models/` metadata hiện hành.
2. Kiểm tra `scripts/esp32cam_fomo_contract.py` nếu thay đổi contract.
3. Cập nhật `project-overview-pdr.md`, `codebase-summary.md`, `system-architecture.md` nếu scope thay đổi.
4. Cập nhật `project-roadmap.md` nếu milestone dịch chuyển.

## Avoid
- Không mô tả Edge Impulse là canonical path nếu repo artifact hiện tại cho thấy FOMO local pipeline.
- Không trộn 15-class mapping vào 5-label canonical mà không ghi chú.
- Không ghi `fomo_*` là detector nếu metadata thực tế vẫn là classifier, hoặc ngược lại; phải gọi ra mâu thuẫn.

## Validation
Sau khi sửa docs, chạy:
```bash
node .claude/scripts/validate-docs.cjs docs/
```

## Unresolved Questions
- Có nên tách riêng chuẩn metadata cho baseline classifier để tránh reuse tên `fomo_*` không?
- Có nên hạ cấp hoặc lưu trữ các docs legacy để tránh người mới đọc nhầm?