"""
Test model trực tiếp với ảnh chụp từ ESP32-CAM.

Cách dùng:
  python scripts/test_model_live_capture.py --ip 192.168.1.226

Bấm phím:
  SPACE  = chụp + classify
  A      = auto mode (chụp liên tục mỗi 1.5 giây)
  S      = lưu ảnh hiện tại vào thư mục captures/
  Q/ESC  = thoát
"""

import argparse
import sys
import time
from pathlib import Path
from io import BytesIO
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from urllib.request import urlopen, Request
from urllib.error import URLError

# --- Config ---
DEFAULT_RELEASE_MODEL = Path(__file__).parent.parent / "models" / "traffic_sign_fomo_float32.tflite"
DEFAULT_RELEASE_MODEL_INT8 = Path(__file__).parent.parent / "models" / "traffic_sign_fomo_int8.tflite"
DEFAULT_BASELINE_MODEL = Path(__file__).parent.parent / "models" / "classifier_gtsrb_int8.tflite"
MODEL_PATH = (
    DEFAULT_RELEASE_MODEL
    if DEFAULT_RELEASE_MODEL.exists()
    else DEFAULT_RELEASE_MODEL_INT8
    if DEFAULT_RELEASE_MODEL_INT8.exists()
    else DEFAULT_BASELINE_MODEL
)
CLASS_LABELS = ["_background_", "stop", "speed_limit", "warning", "other_reg"]
IMG_SIZE = 96
FOMO_GRID_SIZE = 12
NUM_CLASSES = 5
CENTER_CROP_RATIO = 0.5

CAPTURES_DIR = Path(__file__).parent.parent / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


def load_tflite_model(model_path: str):
    """Load TFLite model and return interpreter."""
    try:
        import tensorflow as tf
        interpreter = tf.lite.Interpreter(model_path=str(model_path))
    except ImportError:
        import tflite_runtime.interpreter as tflite
        interpreter = tflite.Interpreter(model_path=str(model_path))

    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]

    print(f"[OK] Model loaded: {model_path}")
    print(f"  Input:  shape={inp['shape']} dtype={inp['dtype']} "
          f"scale={inp['quantization'][0]:.6f} zp={inp['quantization'][1]}")
    print(f"  Output: shape={out['shape']} dtype={out['dtype']} "
          f"scale={out['quantization'][0]:.6f} zp={out['quantization'][1]}")

    return interpreter, inp, out


def capture_frame(ip: str, port: int = 81, timeout: float = 5.0) -> Image.Image | None:
    """Capture one JPEG frame from ESP32-CAM /capture endpoint."""
    url = f"http://{ip}:{port}/capture"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return Image.open(BytesIO(data)).convert("RGB")
    except (URLError, Exception) as e:
        print(f"[ERR] Capture failed: {e}")
        return None


def preprocess_frame(frame: Image.Image, is_fomo: bool, img_size: int = IMG_SIZE,
                     center_crop_ratio: float = CENTER_CROP_RATIO) -> tuple[np.ndarray, Image.Image]:
    """
    Simulate firmware preprocessing:
    1. FOMO release path: full frame -> resize 96x96
    2. Baseline classifier path: center crop -> resize 96x96
    Return (model_input_array, cropped_pil_image_for_display)
    """
    w, h = frame.size

    if is_fomo:
        cropped = frame
    else:
        crop_w = int(w * center_crop_ratio)
        crop_h = int(h * center_crop_ratio)
        left = (w - crop_w) // 2
        top = (h - crop_h) // 2
        cropped = frame.crop((left, top, left + crop_w, top + crop_h))

    # Resize to model input size
    resized = cropped.resize((img_size, img_size), Image.BILINEAR)
    arr = np.array(resized, dtype=np.uint8)

    return arr, cropped


def run_inference(interpreter, inp_detail, out_detail, img_array: np.ndarray):
    """Run model inference and return results."""
    # Prepare input
    input_data = np.expand_dims(img_array, axis=0)

    if inp_detail['dtype'] == np.uint8:
        input_data = input_data.astype(np.uint8)
    elif inp_detail['dtype'] == np.int8:
        scale = inp_detail['quantization'][0]
        zp = inp_detail['quantization'][1]
        input_data = np.clip(
            np.round(input_data.astype(np.float32) / scale) + zp,
            -128, 127
        ).astype(np.int8)
    else:
        input_data = input_data.astype(np.float32) / 255.0

    interpreter.set_tensor(inp_detail['index'], input_data)
    interpreter.invoke()

    raw_output = interpreter.get_tensor(out_detail['index'])

    # Dequantize output
    out_scale = out_detail['quantization'][0]
    out_zp = out_detail['quantization'][1]
    if out_detail['dtype'] in [np.uint8, np.int8]:
        output = (raw_output.astype(np.float32) - out_zp) * out_scale
    else:
        output = raw_output.astype(np.float32)

    return output


def decode_fomo_output(output: np.ndarray, grid_size: int = FOMO_GRID_SIZE,
                       num_classes: int = NUM_CLASSES, cell_threshold: float = 0.4):
    """Decode FOMO grid output → class_id, confidence, margin."""
    output = output.reshape(grid_size, grid_size, num_classes)

    # Vote across grid cells
    vote_count = np.zeros(num_classes, dtype=int)
    vote_conf_sum = np.zeros(num_classes, dtype=float)

    for cy in range(grid_size):
        for cx in range(grid_size):
            cell_scores = output[cy, cx]
            best_cls = int(np.argmax(cell_scores))
            best_score = float(cell_scores[best_cls])

            if best_cls >= 1 and best_score >= cell_threshold:
                vote_count[best_cls] += 1
                vote_conf_sum[best_cls] += best_score

    # Find class with most votes
    max_votes = 0
    for c in range(1, num_classes):
        if vote_count[c] > max_votes:
            max_votes = vote_count[c]

    if max_votes == 0:
        return 0, 1.0, 1.0, output  # background

    best_conf = -1.0
    second_conf = -1.0
    best_class = 0

    for c in range(1, num_classes):
        if vote_count[c] == 0:
            continue
        avg_conf = vote_conf_sum[c] / vote_count[c]
        if avg_conf > best_conf:
            second_conf = best_conf
            best_conf = avg_conf
            best_class = c
        elif avg_conf > second_conf:
            second_conf = avg_conf

    margin = best_conf - max(0, second_conf)
    return best_class, best_conf, margin, output


def decode_classifier_output(output: np.ndarray, num_classes: int = NUM_CLASSES):
    """Decode simple classifier output → class_id, confidence, margin."""
    scores = output.flatten()[:num_classes]
    sorted_idx = np.argsort(scores)[::-1]
    best_class = int(sorted_idx[0])
    best_conf = float(scores[best_class])
    second_conf = float(scores[sorted_idx[1]]) if len(sorted_idx) > 1 else 0.0
    margin = best_conf - second_conf
    return best_class, best_conf, margin


def print_result(class_id: int, conf: float, margin: float, elapsed_ms: float,
                 all_scores: np.ndarray = None):
    """Pretty-print classification result."""
    label = CLASS_LABELS[class_id] if class_id < len(CLASS_LABELS) else f"unknown({class_id})"

    # Color coding
    if class_id == 0:
        status = "🟢 NO SIGN"
    elif conf >= 0.8 and margin >= 0.3:
        status = f"✅ {label.upper()}"
    elif conf >= 0.6:
        status = f"⚠️  {label.upper()}"
    else:
        status = f"❌ {label.upper()} (low conf)"

    print(f"\n{'='*50}")
    print(f"  {status}")
    print(f"  Confidence: {conf*100:.1f}%  |  Margin: {margin*100:.1f}%")
    print(f"  Inference time: {elapsed_ms:.0f}ms")

    if all_scores is not None:
        scores_flat = all_scores.flatten()
        if len(scores_flat) >= NUM_CLASSES:
            # Show per-class scores (either from grid mean or classifier)
            if len(scores_flat) == NUM_CLASSES:
                print(f"  Scores: ", end="")
                for i, lbl in enumerate(CLASS_LABELS):
                    print(f"{lbl}={scores_flat[i]*100:.1f}%  ", end="")
                print()

    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Test model with live ESP32-CAM captures")
    parser.add_argument("--ip", default="192.168.1.226",
                        help="ESP32-CAM IP address")
    parser.add_argument("--port", type=int, default=81,
                        help="ESP32-CAM stream port")
    parser.add_argument("--model", type=str, default=str(MODEL_PATH),
                        help="Path to TFLite model")
    parser.add_argument("--threshold", type=float, default=0.4,
                        help="FOMO cell threshold")
    parser.add_argument("--auto-interval", type=float, default=1.5,
                        help="Auto capture interval in seconds")
    parser.add_argument("--no-gui", action="store_true",
                        help="Run without GUI (terminal only)")
    args = parser.parse_args()

    # Load model
    interpreter, inp_detail, out_detail = load_tflite_model(args.model)

    # Detect model type
    out_shape = out_detail['shape']
    total_elements = 1
    for d in out_shape:
        total_elements *= d
    is_fomo = (total_elements == FOMO_GRID_SIZE * FOMO_GRID_SIZE * NUM_CLASSES)
    is_classifier = (total_elements == NUM_CLASSES)
    print(f"[OK] Model type: {'FOMO grid' if is_fomo else 'Classifier' if is_classifier else 'Unknown'}")
    print(f"[OK] Output elements: {total_elements}")
    print(f"[OK] Preprocess path: {'full-frame resize' if is_fomo else 'center-crop baseline'}")

    print(f"\n[INFO] ESP32-CAM: http://{args.ip}:{args.port}/capture")
    print(f"[INFO] Captures saved to: {CAPTURES_DIR}")

    if args.no_gui:
        print("\n--- Terminal Mode ---")
        print("Commands: [Enter]=capture  [a]=auto  [s]=save  [q]=quit\n")
        _run_terminal_mode(interpreter, inp_detail, out_detail,
                           is_fomo, args)
    else:
        try:
            import cv2
            print("\n--- GUI Mode (OpenCV) ---")
            print("Keys: [SPACE]=capture  [A]=auto  [S]=save  [Q/ESC]=quit\n")
            _run_gui_mode(interpreter, inp_detail, out_detail,
                          is_fomo, args)
        except ImportError:
            print("[WARN] OpenCV not installed, falling back to terminal mode")
            print("  Install: pip install opencv-python")
            print("\n--- Terminal Mode ---")
            print("Commands: [Enter]=capture  [a]=auto  [s]=save  [q]=quit\n")
            _run_terminal_mode(interpreter, inp_detail, out_detail,
                               is_fomo, args)


def _run_terminal_mode(interpreter, inp_detail, out_detail, is_fomo, args):
    """Terminal-only mode: type commands to capture and classify."""
    auto_mode = False
    last_capture_time = 0
    last_frame = None
    last_result = None

    while True:
        # Auto capture
        if auto_mode and time.time() - last_capture_time >= args.auto_interval:
            cmd = "capture"
        else:
            try:
                if auto_mode:
                    # Non-blocking check (simplified)
                    import select
                    if sys.platform == "win32":
                        import msvcrt
                        if msvcrt.kbhit():
                            cmd = msvcrt.getch().decode("utf-8", errors="ignore").strip()
                        else:
                            time.sleep(0.1)
                            if time.time() - last_capture_time >= args.auto_interval:
                                cmd = "capture"
                            else:
                                continue
                    else:
                        ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                        if ready:
                            cmd = sys.stdin.readline().strip()
                        elif time.time() - last_capture_time >= args.auto_interval:
                            cmd = "capture"
                        else:
                            continue
                else:
                    cmd = input(">>> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break

        if cmd in ("q", "quit", "exit"):
            break
        elif cmd == "a":
            auto_mode = not auto_mode
            print(f"[{'ON' if auto_mode else 'OFF'}] Auto capture mode "
                  f"(every {args.auto_interval}s)")
            continue
        elif cmd == "s":
            if last_frame is not None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                label = CLASS_LABELS[last_result[0]] if last_result else "unknown"
                save_path = CAPTURES_DIR / f"{ts}_{label}.jpg"
                last_frame.save(save_path, "JPEG", quality=95)
                print(f"[SAVED] {save_path}")
            else:
                print("[WARN] No captured frame to save")
            continue
        elif cmd in ("", "capture"):
            pass  # proceed to capture
        else:
            print("Commands: [Enter]=capture  [a]=auto  [s]=save  [q]=quit")
            continue

        # Capture
        print(f"[...] Capturing from {args.ip}...")
        frame = capture_frame(args.ip, args.port)
        if frame is None:
            continue

        last_frame = frame
        last_capture_time = time.time()

        # Preprocess
        img_array, cropped = preprocess_frame(frame, is_fomo=is_fomo)

        # Inference
        t0 = time.time()
        output = run_inference(interpreter, inp_detail, out_detail, img_array)
        elapsed_ms = (time.time() - t0) * 1000

        # Decode
        if is_fomo:
            class_id, conf, margin, grid = decode_fomo_output(
                output, cell_threshold=args.threshold)
            print_result(class_id, conf, margin, elapsed_ms)
        else:
            class_id, conf, margin = decode_classifier_output(output)
            print_result(class_id, conf, margin, elapsed_ms, output)

        last_result = (class_id, conf, margin)


def _run_gui_mode(interpreter, inp_detail, out_detail, is_fomo, args):
    """GUI mode with OpenCV window showing camera + prediction."""
    import cv2

    auto_mode = False
    last_capture_time = 0
    display_frame = None
    last_result_text = "Press SPACE to capture"

    # Create window
    cv2.namedWindow("ESP32-CAM Test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ESP32-CAM Test", 800, 600)

    # Show initial message
    blank = np.zeros((400, 600, 3), dtype=np.uint8)
    cv2.putText(blank, "Press SPACE to capture", (50, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.imshow("ESP32-CAM Test", blank)

    while True:
        key = cv2.waitKey(100) & 0xFF

        should_capture = False
        if key == ord(' '):
            should_capture = True
        elif key == ord('a'):
            auto_mode = not auto_mode
            print(f"[{'ON' if auto_mode else 'OFF'}] Auto mode")
        elif key == ord('s') and display_frame is not None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = CAPTURES_DIR / f"{ts}_capture.jpg"
            cv2.imwrite(str(save_path), display_frame)
            print(f"[SAVED] {save_path}")
        elif key == ord('q') or key == 27:
            break

        if auto_mode and time.time() - last_capture_time >= args.auto_interval:
            should_capture = True

        if not should_capture:
            continue

        # Capture
        frame = capture_frame(args.ip, args.port)
        if frame is None:
            continue

        last_capture_time = time.time()

        # Preprocess
        img_array, cropped = preprocess_frame(frame, is_fomo=is_fomo)

        # Inference
        t0 = time.time()
        output = run_inference(interpreter, inp_detail, out_detail, img_array)
        elapsed_ms = (time.time() - t0) * 1000

        # Decode
        if is_fomo:
            class_id, conf, margin, grid = decode_fomo_output(
                output, cell_threshold=args.threshold)
        else:
            class_id, conf, margin = decode_classifier_output(output)

        print_result(class_id, conf, margin, elapsed_ms,
                     output if not is_fomo else None)

        # Build display image
        frame_cv = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
        model_input_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        model_input_cv = cv2.resize(model_input_cv, (200, 200),
                                     interpolation=cv2.INTER_NEAREST)

        # Draw result overlay on frame
        label = CLASS_LABELS[class_id] if class_id < len(CLASS_LABELS) else "?"
        color = (0, 255, 0) if (conf >= 0.7 and class_id > 0) else \
                (0, 255, 255) if class_id > 0 else (128, 128, 128)

        text = f"{label.upper()} {conf*100:.0f}% (margin {margin*100:.0f}%)"
        cv2.putText(frame_cv, text, (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
        cv2.putText(frame_cv, f"Inference: {elapsed_ms:.0f}ms", (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # Show model input in corner
        h, w = frame_cv.shape[:2]
        frame_cv[10:210, w-210:w-10] = model_input_cv
        cv2.rectangle(frame_cv, (w-212, 8), (w-8, 212), (255, 255, 0), 1)
        cv2.putText(frame_cv, "Model input 96x96", (w-210, 228),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

        display_frame = frame_cv
        cv2.imshow("ESP32-CAM Test", frame_cv)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
