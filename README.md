# Robot_Detect_Traffic_Sign

This repository contains a traffic sign recognition robot project with a vision pipeline for ESP32-CAM and integrated control firmware for ESP32-S3.

## Main Components

- `firmware/esp32cam/` - ESP32-CAM firmware that sends traffic sign recognition results
- `firmware/esp32s3/` - ESP32-S3 firmware for integrated control and signal handling
- `models/` - models and artifacts used for inference
- `scripts/` - scripts for data preparation, training, evaluation, and monitoring
- `notebooks/` - training notebooks/scripts
- `docs/` - project documentation and standards
- `reports/` - evaluation reports

## Firmware Tracked in This Repository

- `firmware/esp32cam/test-esp32cam-phase05.ino`
- `firmware/esp32cam/model_data.h`
- `firmware/esp32s3/test-esp32s3-phase05-integration.ino`

Notes:
- Wi-Fi values in ESP32-CAM firmware are placeholders:
  - `YOUR_WIFI_SSID`
  - `YOUR_WIFI_PASSWORD`
- Replace them before flashing firmware.

## High-Level Workflow

1. Collect/prepare image data (`scripts/`)
2. Train model (FOMO/classifier)
3. Evaluate and generate reports (`reports/`)
4. Update deployable model files / `model_data.h`
5. Flash ESP32-CAM + ESP32-S3 firmware for integrated run

## Quick Python Setup

```bash
pip install -r scripts/requirements.txt
```

## Recommended Reading

- `docs/project-overview-pdr.md`
- `docs/codebase-summary.md`
- `docs/system-architecture.md`
- `docs/deployment-guide.md`
- `docs/project-roadmap.md`

## Git Notes

- Internal tooling folders such as `.claude/` and `.opencode/` are ignored and not pushed to remote.
- The repository only tracks source/assets that are directly related to the robot project.
