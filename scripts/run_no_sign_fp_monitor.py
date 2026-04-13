"""
Run serial no-sign monitor and report FP/min for ESP32-CAM SIGN stream.
"""

import argparse
import json
import re
import time
from pathlib import Path

import serial

SIGN_PATTERN = re.compile(r"^SIGN:(\d+):(\d+)\.(\d{2})$")
STATS_PATTERN = re.compile(r"^DBG:sent=(\d+) no_sign=(\d+) low_conf=(\d+) drop=(\d+) parse_fail=(\d+)$")
TOP_PATTERN = re.compile(
    r"^DBG:top=(\d+)\(([^)]*)\) conf=(\d+)\.(\d{2}) second=(\d+)\.(\d{2}) margin=(\d+)\.(\d{2})(?: stable=(\d+))?$"
)
UNSTABLE_PATTERN = re.compile(
    r"^DBG:unstable top=(\d+) conf=(\d+)\.(\d{2}) margin=(\d+)\.(\d{2}) hits=(\d+)/(\d+)$"
)


def _open_serial(port: str, baud: int):
    ser = serial.Serial(port, baudrate=baud, timeout=0.2)
    ser.setDTR(False)
    ser.setRTS(False)
    return ser


def run_monitor(port: str, baud: int, duration_sec: int):
    end = time.time() + duration_sec

    sign_total = 0
    malformed = 0
    line_total = 0
    class_counts = {}
    samples = []
    top_samples = []
    conf_by_class = {}
    margin_by_class = {}
    unstable_total = 0
    last_stats = None
    reconnects = 0
    serial_errors = 0

    ser = None

    while time.time() < end:
        if ser is None:
            try:
                ser = _open_serial(port, baud)
            except serial.SerialException:
                serial_errors += 1
                time.sleep(0.5)
                continue

        try:
            raw = ser.readline()
        except serial.SerialException:
            serial_errors += 1
            reconnects += 1
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(0.2)
            continue

        if not raw:
            continue

        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            continue

        line_total += 1

        m_sign = SIGN_PATTERN.match(line)
        if m_sign:
            cid = int(m_sign.group(1))
            sign_total += 1
            class_counts[cid] = class_counts.get(cid, 0) + 1
            if len(samples) < 30:
                samples.append(line)
            continue

        if line.startswith("SIGN:"):
            malformed += 1
            if len(samples) < 30:
                samples.append(line)
            continue

        m_stats = STATS_PATTERN.match(line)
        if m_stats:
            last_stats = {
                "sent": int(m_stats.group(1)),
                "no_sign": int(m_stats.group(2)),
                "low_conf": int(m_stats.group(3)),
                "drop": int(m_stats.group(4)),
                "parse_fail": int(m_stats.group(5)),
            }
            continue

        m_unstable = UNSTABLE_PATTERN.match(line)
        if m_unstable:
            unstable_total += 1
            if len(top_samples) < 80:
                top_samples.append(line)
            continue

        m_top = TOP_PATTERN.match(line)
        if m_top:
            cid = int(m_top.group(1))
            conf = int(m_top.group(3)) + int(m_top.group(4)) / 100.0
            margin = int(m_top.group(7)) + int(m_top.group(8)) / 100.0
            conf_by_class.setdefault(cid, []).append(conf)
            margin_by_class.setdefault(cid, []).append(margin)
            if len(top_samples) < 80:
                top_samples.append(line)

    if ser is not None:
        try:
            ser.close()
        except Exception:
            pass

    fp_per_min = sign_total / (duration_sec / 60.0)
    conf_stats = {}
    for cid, vals in conf_by_class.items():
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        std = (sum((x - mean) ** 2 for x in vals) / len(vals)) ** 0.5
        conf_stats[str(cid)] = {
            "count": len(vals),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
        }

    margin_stats = {}
    for cid, vals in margin_by_class.items():
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        std = (sum((x - mean) ** 2 for x in vals) / len(vals)) ** 0.5
        margin_stats[str(cid)] = {
            "count": len(vals),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
        }

    return {
        "duration_sec": duration_sec,
        "line_total": line_total,
        "sign_total": sign_total,
        "fp_per_min": fp_per_min,
        "malformed": malformed,
        "class_counts": class_counts,
        "last_stats": last_stats,
        "reconnects": reconnects,
        "serial_errors": serial_errors,
        "unstable_total": unstable_total,
        "sign_samples": samples,
        "top_samples": top_samples,
        "conf_stats_by_class": conf_stats,
        "margin_stats_by_class": margin_stats,
    }


def main():
    parser = argparse.ArgumentParser(description="Measure no-sign FP/min from ESP32-CAM serial stream")
    parser.add_argument("--port", default="COM7")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--duration-sec", type=int, default=1800)
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    print(f"[RUN] no-sign monitor on {args.port}@{args.baud} for {args.duration_sec}s")
    result = run_monitor(args.port, args.baud, args.duration_sec)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] result written: {out_path}")
    print(f"[OK] sign_total={result['sign_total']} fp_per_min={result['fp_per_min']:.4f} malformed={result['malformed']}")


if __name__ == "__main__":
    main()
