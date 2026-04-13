# Project Roadmap

## Status Summary
Repo đã vượt qua giai đoạn khởi tạo dữ liệu cơ bản và hiện ở trạng thái chuyển dịch từ baseline classifier sang canonical FOMO cho ESP32-CAM.

## Phases

| Phase | Status | Notes |
|---|---|---|
| 1. Dataset acquisition and filtering | Done | Có script download/filter/convert/split/validate |
| 2. Baseline classifier training | Done as baseline | Có notebook/script và artifact `classifier_gtsrb_*` |
| 3. ESP32-CAM FOMO dataset pipeline | In progress but artifact-backed | Có capture, manifest, bootstrap, canonical manifest |
| 4. Canonical FOMO training/export | In progress | Có artifact và report pack, nhưng metadata/docs chưa đồng bộ hoàn toàn |
| 5. Runtime validation and monitoring | Partial | Có live capture test, dashboard, no-sign/with-sign monitors |
| 6. Documentation normalization | In progress | Bộ docs cốt lõi vừa được chuẩn hóa; legacy docs vẫn còn |

## Near-Term Priorities
1. Chuẩn hóa tất cả metadata liên quan canonical FOMO.
2. Quyết định rõ giữ hay archive pipeline classifier trong docs phụ trợ.
3. Thêm bằng chứng benchmark thiết bị thật nếu có chủ đích release.
4. Đồng bộ legacy docs còn giá trị với canonical docs.
5. Tune firmware ESP32-S3 trên chassis thật sau khi đã thêm startup-straight, turn-settle, và yaw heading-hold cho caster compensation.

## What Is Already Evidenced
- Canonical FOMO artifacts đã được check-in.
- FOMO report pack đã tồn tại trong `reports/esp32cam_fomo_report_pack/`.
- Baseline classifier artifacts vẫn được giữ để so sánh/debug.

## Risks
- Người mới đọc nhầm docs legacy và đi sai pipeline.
- Tên artifact `fomo_*` từng được tái dùng cho classifier, gây mơ hồ lịch sử.
- Calibration metadata chưa đồng bộ có thể làm downstream integration mơ hồ.

## Recommended Next Documentation Milestones
- M1: Hoàn tất source-of-truth docs trong `docs/`.
- M2: Gắn nhãn rõ legacy/reference cho `colab_usage_guide.md`, `training_report.md`, `edge_impulse_setup.md`, `dataset_mapping.md`.
- M3: Bổ sung release checklist khi có firmware/runtime evidence rõ hơn.

## Deferred / Optional
- Archive Edge Impulse path thành tài liệu historical-only.
- Tách docs baseline classifier thành một mục riêng nếu tiếp tục bảo trì.
- Tạo changelog tài liệu nếu repo bắt đầu cập nhật thường xuyên.

## Success Condition for Current Cycle
- Repo có entry docs rõ ràng.
- Canonical pipeline được nêu dứt khoát là FOMO.
- Inconsistency được liệt kê thay vì che giấu.

## Unresolved Questions
- Có kế hoạch tiếp tục train/cải thiện baseline classifier song song không?
- Có cần một release checklist riêng cho hardware-run validation không?
