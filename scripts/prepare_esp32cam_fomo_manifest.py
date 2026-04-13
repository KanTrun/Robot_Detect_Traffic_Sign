from __future__ import annotations

import argparse
import csv
from pathlib import Path

from esp32cam_fomo_contract import DEFAULT_CANONICAL_MANIFEST, DEFAULT_CAPTURE_MANIFEST

REQUIRED_COLUMNS = [
    "image_path",
    "domain",
    "split",
    "label",
    "x1",
    "y1",
    "x2",
    "y2",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and canonicalize ESP32-CAM FOMO annotations")
    parser.add_argument("--in", dest="input_path", default=str(DEFAULT_CAPTURE_MANIFEST))
    parser.add_argument("--out", dest="output_path", default=str(DEFAULT_CANONICAL_MANIFEST))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_path)
    output_path = Path(args.output_path)

    with input_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = set(reader.fieldnames or [])

    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    normalized_rows: list[dict[str, str]] = []
    pending = 0
    for row in rows:
        label = (row.get("label") or "").strip()
        status = (row.get("annotation_status") or "").strip().lower()
        bbox_values = [row.get("x1", "").strip(), row.get("y1", "").strip(), row.get("x2", "").strip(), row.get("y2", "").strip()]
        has_box = all(bbox_values)
        if label != "_background_" and not has_box:
            pending += 1
            continue
        if label == "_background_":
            row["x1"] = ""
            row["y1"] = ""
            row["x2"] = ""
            row["y2"] = ""
        row["annotation_status"] = "ready" if status != "ready" else status
        normalized_rows.append({column: row.get(column, "") for column in REQUIRED_COLUMNS})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized_rows)

    print(f"[OK] Canonical manifest: {output_path.resolve()}")
    print(f"[OK] Ready rows: {len(normalized_rows)}")
    if pending:
        print(f"[WARN] Skipped {pending} rows still missing bbox coordinates")


if __name__ == "__main__":
    main()
