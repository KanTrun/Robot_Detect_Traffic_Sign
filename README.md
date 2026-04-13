# Robot_Detect_Traffic_Sign

Repository cho d? án robot nh?n di?n bi?n báo giao thông v?i pipeline th? giác cho ESP32-CAM và firmware tích h?p ESP32-S3.

## Thành ph?n chính

- `firmware/esp32cam/` - firmware ESP32-CAM g?i k?t qu? nh?n di?n bi?n báo
- `firmware/esp32s3/` - firmware ESP32-S3 di?u khi?n/nh?n tín hi?u tích h?p
- `models/` - model và artifact ph?c v? inference
- `scripts/` - script chu?n b? d? li?u, train, evaluate, monitor
- `notebooks/` - notebook/script hu?n luy?n
- `docs/` - tài li?u chu?n c?a d? án
- `reports/` - báo cáo dánh giá

## Firmware dang track trong repo

- `firmware/esp32cam/test-esp32cam-phase05.ino`
- `firmware/esp32cam/model_data.h`
- `firmware/esp32s3/test-esp32s3-phase05-integration.ino`

Luu ý:
- Wi-Fi trong firmware ESP32-CAM dang d? placeholder:
  - `YOUR_WIFI_SSID`
  - `YOUR_WIFI_PASSWORD`
- C?n d?i tru?c khi n?p firmware.

## Lu?ng t?ng quan

1. Thu th?p/chu?n hóa d? li?u ?nh (`scripts/`)
2. Train model (FOMO/classifier)
3. Evaluate và sinh báo cáo (`reports/`)
4. C?p nh?t `model_data.h`/model deploy
5. N?p firmware ESP32-CAM + ESP32-S3 d? ch?y tích h?p

## Thi?t l?p nhanh môi tru?ng Python

```bash
pip install -r scripts/requirements.txt
```

## Tài li?u nên d?c tru?c

- `docs/project-overview-pdr.md`
- `docs/codebase-summary.md`
- `docs/system-architecture.md`
- `docs/deployment-guide.md`
- `docs/project-roadmap.md`

## Ghi chú Git

- Các thu m?c công c? n?i b? nhu `.claude/`, `.opencode/` dã du?c ignore và không push lên remote.
- Ch? gi? l?i source/asset th?c s? liên quan d?n d? án robot.
