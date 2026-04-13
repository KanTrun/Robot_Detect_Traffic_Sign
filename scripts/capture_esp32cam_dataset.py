from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image

from esp32cam_fomo_contract import CLASS_LABELS, DEFAULT_CAPTURE_MANIFEST, DEFAULT_DATASET_ROOT

CAPTURE_COLUMNS = [
    "image_path",
    "domain",
    "split",
    "label",
    "x1",
    "y1",
    "x2",
    "y2",
    "source_kind",
    "notes",
    "annotation_status",
    "capture_url",
    "captured_at",
]


def fetch_capture(capture_url: str, timeout: float) -> Image.Image:
    request = Request(capture_url, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return Image.open(BytesIO(response.read())).convert("RGB")


def append_manifest_row(manifest_path: Path, row: dict[str, str]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    exists = manifest_path.exists()
    with manifest_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAPTURE_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture full-frame ESP32-CAM data for FOMO training")
    parser.add_argument("--ip", required=True, help="ESP32-CAM IP address")
    parser.add_argument("--port", type=int, default=81, help="ESP32-CAM capture port")
    parser.add_argument("--count", type=int, default=40, help="How many frames to save")
    parser.add_argument("--interval-sec", type=float, default=0.8, help="Delay between frames")
    parser.add_argument("--timeout-sec", type=float, default=5.0, help="HTTP timeout")
    parser.add_argument("--label", required=True, choices=CLASS_LABELS, help="Canonical grouped label")
    parser.add_argument("--domain", required=True, choices=["print", "screen", "no-sign", "hard-negative"])
    parser.add_argument("--split", default="train", choices=["train", "val", "test"])
    parser.add_argument("--source-kind", default="esp32cam-live")
    parser.add_argument("--notes", default="")
    parser.add_argument("--out-root", default=str(DEFAULT_DATASET_ROOT / "raw"))
    parser.add_argument("--manifest", default=str(DEFAULT_CAPTURE_MANIFEST))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    capture_url = f"http://{args.ip}:{args.port}/capture"
    out_dir = Path(args.out_root) / args.domain / args.label
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest)

    print(f"[RUN] Capturing {args.count} frames from {capture_url}")
    print(f"[RUN] Saving to {out_dir}")

    for index in range(args.count):
        try:
            frame = fetch_capture(capture_url, timeout=args.timeout_sec)
        except URLError as exc:
            print(f"[ERR] capture failed ({index + 1}/{args.count}): {exc}")
            time.sleep(args.interval_sec)
            continue
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        image_path = out_dir / f"{stamp}.jpg"
        frame.save(image_path, format="JPEG", quality=95)
        annotation_status = "ready" if args.label == "_background_" else "pending_box"
        row = {
            "image_path": str(image_path.resolve()),
            "domain": args.domain,
            "split": args.split,
            "label": args.label,
            "x1": "",
            "y1": "",
            "x2": "",
            "y2": "",
            "source_kind": args.source_kind,
            "notes": args.notes,
            "annotation_status": annotation_status,
            "capture_url": capture_url,
            "captured_at": stamp,
        }
        append_manifest_row(manifest_path, row)
        print(f"[OK] {index + 1}/{args.count} -> {image_path.name} status={annotation_status}")
        time.sleep(args.interval_sec)

    print(f"[DONE] Manifest: {manifest_path.resolve()}")
    if args.label != "_background_":
        print("[NEXT] Fill x1,y1,x2,y2 for sign rows, then run prepare_esp32cam_fomo_manifest.py")


if __name__ == "__main__":
    main()
