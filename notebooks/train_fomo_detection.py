from __future__ import annotations

"""
Compatibility launcher for the canonical ESP32-CAM FOMO release pipeline.

This file used to export a classifier while keeping `fomo_*` names for drop-in
compatibility. The canonical release flow is now a true 12x12x5 detector.

Usage:
  python notebooks/train_fomo_detection.py --manifest data/esp32cam-fomo/fomo_manifest.csv
"""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    scripts_dir = project_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    target = scripts_dir / "train_esp32cam_fomo.py"
    runpy.run_path(str(target), run_name="__main__")
