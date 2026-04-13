# Hướng dẫn sử dụng Google Colab Notebook
# Google Colab Notebook Usage Guide

> 2026-03-29 release update:
> Canonical deploy flow đã chuyển sang **FOMO detector full-frame** cho ESP32-CAM.
> Baseline classifier `1x5` chỉ còn dùng cho debug/đối chứng, không phải release path.
>
> Canonical release contract:
> - labels: `_background_`, `stop`, `speed_limit`, `warning`, `other_reg`
> - input: `96x96x3`
> - output: `[1,12,12,5]`
> - schema: `fomo-grid-v2`
>
> Quick start:
> 1. `python scripts/capture_esp32cam_dataset.py --ip <ip> --label stop --domain print`
> 2. Ghi bbox `x1,y1,x2,y2` vào manifest thu được
> 3. `python scripts/prepare_esp32cam_fomo_manifest.py`
> 4. `python notebooks/train_fomo_detection.py --manifest data/esp32cam-fomo/fomo_manifest.csv`
> 5. `python scripts/evaluate_esp32cam_fomo.py --model models/traffic_sign_fomo_int8.tflite`

## Tổng quan (Overview)

Notebook này chứa quy trình huấn luyện **ROI classifier** cho nhận dạng biển báo giao thông trên Google Colab, từ chuẩn bị dữ liệu đến xuất model cho ESP32-CAM.

This notebook contains the workflow for training a **ROI classifier** traffic-sign model on Google Colab, from data preparation to ESP32-CAM export.

> Cập nhật theo pipeline mới: classifier 5 lớp (`_background_`, `stop`, `speed_limit`, `warning`, `other_reg`), MobileNetV2 `alpha=0.35`, input `96x96`, output tensor `[1,5]`, export int8 + `model_data.h` + `class_labels.txt` + `fomo_*.json` (schema `classifier-v1`).

---

## Chuẩn bị (Prerequisites)

### 1. Tài khoản Google (Google Account)
- Cần tài khoản Google với **15GB dung lượng trống** trên Drive
- Need Google account with **15GB free space** on Drive

### 2. Tài khoản Kaggle (Kaggle Account)
- Đăng ký tại: https://www.kaggle.com
- Tạo API token: Account → API → Create New Token
- Tải file `kaggle.json` về máy
- Register at: https://www.kaggle.com
- Create API token: Account → API → Create New Token
- Download `kaggle.json` file

### 3. Kích hoạt GPU trên Colab (Enable GPU on Colab)
- Runtime → Change runtime type → Hardware accelerator → **GPU (T4)**

---

## Cách sử dụng (How to Use)

### Bước 1: Upload Notebook lên Colab

**Cách 1: Upload trực tiếp**
1. Mở https://colab.research.google.com
2. File → Upload notebook
3. Chọn file `traffic_sign_training.ipynb` từ `D:\DoAn_Robot\notebooks\`

**Cách 2: Từ Google Drive**
1. Upload notebook vào Google Drive
2. Mở bằng Google Colab (chuột phải → Open with → Google Colaboratory)

---

### Bước 2: Chạy các Cell theo thứ tự

**QUAN TRỌNG: Phải chạy các cell theo thứ tự từ trên xuống!**

#### PHẦN 1: Cài đặt môi trường (10 phút)

**Cell 1.1:** Kiểm tra GPU
- Nếu không có GPU, bật GPU trong Runtime → Change runtime type

**Cell 1.2:** Mount Google Drive
- Bạn sẽ được yêu cầu cấp quyền
- Nhấp vào link, chọn tài khoản Google, cho phép truy cập

**Cell 1.3:** Tạo cấu trúc thư mục
- Tự động tạo thư mục trong Google Drive

**Cell 1.4:** Cài đặt thư viện
- Tự động cài đặt các thư viện cần thiết

**Cell 1.5:** Upload kaggle.json
- Nhấn nút "Choose Files"
- Chọn file `kaggle.json` đã tải từ Kaggle
- Đợi upload hoàn tất

---

#### PHẦN 2: Tải và xử lý dataset (30-45 phút)

**Cell 2.1:** Tải GTSRB Dataset
- Tải ~1.2GB từ Kaggle
- Thời gian: 10-15 phút
- Tự động copy vào Google Drive

**Cell 2.2:** Định nghĩa nhãn classifier 5 lớp
- Chạy để xem danh sách nhãn: `_background_`, `stop`, `speed_limit`, `warning`, `other_reg`

**Cell 2.3:** Tạo ROI dataset cho classifier
- Gom và remap dữ liệu về 5 lớp mục tiêu
- Thời gian: 5-10 phút

**Cell 2.4:** Chuyển đổi PPM → JPEG
- Chuyển đổi và resize về 96×96
- Thời gian: 10-15 phút

**Cell 2.5:** Chia Train/Val/Test (70/15/15)
- Tự động chia dataset theo split scene-aware
- Thời gian: 2-3 phút

**Cell 2.6:** Hiển thị mẫu ảnh
- Xem preview các lớp biển báo

---

#### PHẦN 3: Huấn luyện mô hình (30-45 phút)

**Cell 3.1:** Thiết lập Data Generators
- Tạo data generators với augmentation
- **Lưu ý:** tắt `horizontal_flip` để tránh gây nhầm lớp trái/phải

**Cell 3.2:** Xây dựng MobileNetV2
- Xây dựng mô hình MobileNetV2 alpha=0.35

**Cell 3.3:** Huấn luyện mô hình ⚠️ **CELL QUAN TRỌNG NHẤT**
- Huấn luyện 50 epochs
- Thời gian: 20-30 phút trên GPU T4
- Tự động lưu model tốt nhất vào Google Drive

**Cell 3.4:** Vẽ biểu đồ
- Xem đường cong accuracy và loss

---

#### PHẦN 4: Tối ưu hóa và xuất model (10 phút)

**Cell 4.1:** Chuyển đổi sang TFLite
- Convert sang TensorFlow Lite (float32)

**Cell 4.2:** int8 Quantization ⚠️ **CELL QUAN TRỌNG**
- Giảm kích thước model ~4 lần
- Từ ~1.2MB xuống ~300KB

**Cell 4.3:** Tạo C++ Header ⚠️ **CELL QUAN TRỌNG**
- Tạo file `model_data.h` cho Arduino
- File này sẽ dùng cho ESP32-CAM

**Cell 4.4:** Tải xuống files
- Hướng dẫn tải file về máy tính

---

#### PHẦN 5: Đánh giá kết quả (10 phút)

**Cell 5.1:** Đánh giá trên test set
- Kiểm tra accuracy trên test set
- Mục tiêu: **>90%**

**Cell 5.2:** Ma trận nhầm lẫn
- Xem confusion matrix

**Cell 5.3:** Classification Report
- Báo cáo chi tiết precision, recall, f1-score

**Cell 5.4:** Kiểm tra TFLite int8
- Verify độ chính xác sau quantization

---

#### PHẦN 6: Tóm tắt

**Cell 6.1:** Tóm tắt kết quả
- Xem tổng kết toàn bộ quá trình

---

## Tải file về máy tính (Download Files)

Sau khi chạy xong, bạn có 2 cách tải file:

### Cách 1: Từ Google Colab (trong notebook)

Bỏ dấu `#` ở Cell 4.4 và chạy lại:

```python
from google.colab import files

# Tải file quan trọng nhất (C++ header cho ESP32)
files.download(f"{MODELS_DIR}/model_data.h")

# Tải TFLite model (tên giữ fomo_* để compatibility)
files.download(f"{MODELS_DIR}/traffic_sign_fomo_int8.tflite")

# Tải class labels
files.download(f"{MODELS_DIR}/class_labels.txt")

# Tải metadata/report theo schema classifier-v1
files.download(f"{MODELS_DIR}/fomo_summary.json")
files.download(f"{MODELS_DIR}/fomo_eval_report.json")
files.download(f"{MODELS_DIR}/fomo_calibration.json")
```

### Cách 2: Từ Google Drive (khuyến nghị)

1. Mở Google Drive: https://drive.google.com
2. Vào thư mục: **MyDrive/TrafficSignRobot/models/**
3. Tải các file sau về `D:\DoAn_Robot\models\`:
   - ✅ **model_data.h** (quan trọng nhất cho ESP32)
   - ✅ **traffic_sign_fomo_int8.tflite** *(classifier model, giữ tên fomo để drop-in compatibility)*
   - ✅ **class_labels.txt**
   - ✅ **fomo_summary.json** *(schema `classifier-v1`)*
   - ✅ **fomo_eval_report.json** *(schema `classifier-v1`)*
   - ✅ **fomo_calibration.json** *(schema `classifier-v1`)*
   - 📊 training_curves.png (để báo cáo)
   - 📊 confusion_matrix.png (để báo cáo)
   - 📊 best_model.h5 (backup)

---

## Các file sẽ được tạo ra

```
Google Drive/MyDrive/TrafficSignRobot/
├── dataset/              # GTSRB raw dataset (1.2GB)
├── data_train/           # Training set cho classifier
├── data_val/             # Validation set cho classifier
├── data_test/            # Test set cho classifier
└── models/               # ⭐ FOLDER QUAN TRỌNG NHẤT
    ├── best_model.h5                    # Keras model (backup)
    ├── traffic_sign_fomo_int8.tflite   # TFLite int8 classifier (giữ tên fomo_*)
    ├── model_data.h                     # ⭐ C++ header cho ESP32
    ├── class_labels.txt                 # `_background_, stop, speed_limit, warning, other_reg`
    ├── fomo_summary.json                # Summary (schema `classifier-v1`)
    ├── fomo_eval_report.json            # Eval report (schema `classifier-v1`)
    ├── fomo_calibration.json            # Calibration (schema `classifier-v1`)
    ├── training_curves.png              # Biểu đồ huấn luyện
    ├── confusion_matrix.png             # Ma trận nhầm lẫn
    ├── classification_report.txt        # Báo cáo chi tiết
    └── sample_images.png                # Mẫu ảnh các lớp
```

---

## Kết quả mong đợi (Expected Results)

### ✅ Target Metrics

| Metric | Target | Minimum |
|--------|--------|---------|
| Classifier Top-1 Accuracy | Pending measurement | Pending measurement |
| Model Size (int8) | Pending measurement | <500KB |
| Training Time | 30 min | - |
| Total Time | 90 min | - |

### 📊 Typical Results

```
✅ Classifier labels: 5 (`_background_`, `stop`, `speed_limit`, `warning`, `other_reg`)
✅ Input/Output contract: `96x96x3` → `[1,5]` uint8
✅ Export artifacts: `traffic_sign_fomo_int8.tflite`, `model_data.h`, `class_labels.txt`, `fomo_*.json` (schema `classifier-v1`)
⏳ Accuracy / model size / ESP32 inference time: pending measurement
```

---

## Xử lý lỗi (Troubleshooting)

### ❌ Lỗi: No GPU detected

**Nguyên nhân:** Chưa bật GPU
**Giải pháp:**
1. Runtime → Change runtime type
2. Hardware accelerator → **GPU**
3. Save → Restart runtime
4. Chạy lại từ Cell 1.1

---

### ❌ Lỗi: Kaggle API authentication failed

**Nguyên nhân:** File kaggle.json không đúng
**Giải pháp:**
1. Kiểm tra file kaggle.json hợp lệ
2. Tải lại từ Kaggle: Account → API → Create New Token
3. Upload lại ở Cell 1.5

---

### ❌ Lỗi: Out of memory

**Nguyên nhân:** Batch size quá lớn
**Giải pháp:**
1. Giảm BATCH_SIZE từ 32 xuống 16 ở Cell 3.1
2. Runtime → Restart runtime
3. Chạy lại từ Cell 3.1

---

### ❌ Lỗi: Classifier accuracy thấp

**Nguyên nhân:** Model chưa đủ tốt hoặc dữ liệu chưa cân bằng tốt cho 5 lớp
**Giải pháp:**
1. Tăng EPOCHS từ 50 lên 80 ở Cell 3.3
2. Hoặc tăng ALPHA từ 0.35 lên 0.5 ở Cell 3.2
3. Rà soát lại tỷ lệ `_background_` và các lớp biển báo
4. Chạy lại training

---

### ❌ Lỗi: Model size > 500KB

**Nguyên nhân:** Model quá lớn cho ESP32
**Giải pháp:**
1. Giảm ALPHA từ 0.35 xuống 0.2 ở Cell 3.2
2. Hoặc giảm IMG_SIZE từ 96 xuống 64 ở Cell 3.1
3. Chạy lại training

---

## Lưu ý quan trọng (Important Notes)

### ⏰ Thời gian Session Colab

- Colab session có **giới hạn 12 giờ**
- Nếu session hết hạn, dữ liệu trong `/content/` sẽ mất
- **Nhưng:** Dữ liệu trong Google Drive vẫn được giữ nguyên
- **Khuyến nghị:** Hoàn thành trong 1 session (90 phút)

### 💾 Lưu dữ liệu

- Tất cả dữ liệu quan trọng được lưu vào Google Drive
- Model được lưu sau mỗi epoch (checkpoint)
- Nếu session crash, bạn vẫn có model tốt nhất

### 🔄 Chạy lại từ đầu

Nếu muốn chạy lại từ đầu:
1. Runtime → Restart runtime
2. Xóa thư mục `/content/drive/MyDrive/TrafficSignRobot/` (nếu muốn)
3. Chạy lại từ Cell 1.1

### 📱 Sử dụng trên điện thoại

- Có thể chạy Colab trên điện thoại (app hoặc browser)
- Nhưng khuyến nghị dùng máy tính để xem kết quả tốt hơn

---

## Tích hợp với ESP32-CAM (Phase 3)

Sau khi có file `model_data.h`:

1. **Copy file vào Arduino project:**
   ```
   D:\DoAn_Robot\esp32_code\model_data.h
   ```

2. **Cài đặt TensorFlow Lite Micro:**
   - Arduino IDE → Tools → Manage Libraries
   - Tìm "TensorFlow Lite Micro"
   - Install

3. **Include trong code:**
   ```cpp
   #include "model_data.h"

   // Load model
   const tflite::Model* model = tflite::GetModel(model_data);
   ```

4. **Xem Phase 3 plan để biết chi tiết integration**

---

## ESP32-CAM + DFPlayer Runtime Mapping

Pipeline runtime hiện tại dùng classifier 5 lớp, nhưng chỉ phát âm thanh cho 4 nhóm biển báo:

| Class ID | Label | Nhóm biển thực tế | DFPlayer Track | MP3 file | Câu đọc gợi ý |
|----------|-------|-------------------|----------------|----------|----------------|
| 0 | `_background_` | Nền / không có biển | 1 | `MP3/0001.mp3` | Không dùng trong runtime, có thể để beep test |
| 1 | `stop` | Biển dừng | 2 | `MP3/0002.mp3` | Biển dừng lại |
| 2 | `speed_limit` | Tốc độ 20 / 30 / 50 | 3 | `MP3/0003.mp3` | Biển giới hạn tốc độ |
| 3 | `warning` | Trẻ em, người đi bộ, đường đang thi công | 4 | `MP3/0004.mp3` | Biển cảnh báo phía trước |
| 4 | `other_reg` | Cấm đi vào, hết hạn chế, đi bên trái/phải, rẽ trái/phải, chỉ đi thẳng, vòng xuyến | 5 | `MP3/0005.mp3` | Biển chỉ dẫn hoặc biển cấm |

Lưu ý runtime:
- ESP32-CAM không chụp 1 ảnh rồi dừng. Nó đọc frame camera liên tục, suy luận trên từng frame, rồi lặp lại.
- Vòng lặp nhận diện có delay cơ bản `80ms`.
- Sau khi vừa gửi một biển hợp lệ, firmware cooldown `700ms` để tránh lặp âm thanh.
- Khi đang mở web stream, firmware giảm tần số suy luận xuống khoảng `200ms` mỗi lần để tránh tranh chấp camera.
- ESP32-S3 map âm thanh theo `track = classId + 1`, vì vậy chỉ cần chép đúng `0002.mp3` đến `0005.mp3` là đúng với 4 nhóm biển hiện tại.

Checklist test nhanh:
1. Copy file vào microSD theo đúng tên `MP3/0002.mp3` đến `MP3/0005.mp3`.
2. Mở serial ESP32-CAM và xác nhận có log `SIGN:<class_id>:<confidence>`.
3. Mở serial ESP32-S3 và xác nhận có log `SIGN_OK class=... label=... track=... file=...`.
4. Đưa biển thật trước camera và nghe DFPlayer phát đúng track tương ứng.

---

## Câu hỏi thường gặp (FAQ)

### Q: Tôi có thể pause và resume training không?

**A:** Có! Model được lưu checkpoint sau mỗi epoch vào Google Drive. Nếu session crash, bạn có thể:
1. Chạy lại notebook
2. Skip các cell đã chạy (dataset preparation)
3. Chạy lại Cell 3.3 (training sẽ tiếp tục từ best checkpoint)

### Q: Làm sao biết training đã xong?

**A:** Cell 3.3 sẽ hiển thị:
```
Epoch 50/50
...
✅ Training complete!
```

### Q: Tôi nên dùng local scripts hay Colab notebook?

**A:** Khuyến nghị **Colab notebook** vì:
- ✅ Có GPU miễn phí (nhanh hơn 5-10 lần)
- ✅ Không cần cài đặt Python local
- ✅ Tất cả trong 1 file notebook
- ✅ Dễ chia sẻ và reproduce

### Q: File model_data.h có thể dùng trực tiếp không?

**A:** Có! File này chứa model dưới dạng C array, copy trực tiếp vào Arduino project là dùng được.

### Q: Nếu accuracy chỉ đạt 85-88% thì sao?

**A:** Vẫn OK cho deployment! Trong Phase 6 sẽ fine-tune thêm với ảnh thật từ Việt Nam để tăng accuracy.

---

## Tiếp theo (Next Steps)

Sau khi hoàn thành notebook:

1. ✅ Tải file `model_data.h` về máy
2. ✅ Lưu ảnh training curves, confusion matrix cho báo cáo
3. ✅ Ghi lại accuracy cuối cùng
4. ⏭️  Chuyển sang **Phase 2: Hardware Assembly**
5. ⏭️  **Phase 3:** Tích hợp model vào ESP32-CAM

---

## Liên hệ / Support

Nếu gặp lỗi, check:
1. System messages trong notebook
2. Error logs ở mỗi cell
3. Phần Troubleshooting ở trên

**Good luck with your training! 🚀**
