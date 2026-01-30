# Hướng dẫn sử dụng Google Colab Notebook
# Google Colab Notebook Usage Guide

## Tổng quan (Overview)

Notebook này chứa toàn bộ quy trình huấn luyện mô hình nhận dạng biển báo giao thông trên Google Colab, từ tải dataset đến xuất model cho ESP32-CAM.

This notebook contains the complete workflow for training traffic sign recognition model on Google Colab, from downloading dataset to exporting model for ESP32-CAM.

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

**Cell 2.2:** Định nghĩa 15 lớp biển báo
- Chạy để xem danh sách 15 biển báo đã chọn

**Cell 2.3:** Lọc và sao chép 15 lớp
- Lọc từ 43 lớp GTSRB xuống 15 lớp
- Thời gian: 5 phút

**Cell 2.4:** Chuyển đổi PPM → JPEG
- Chuyển đổi và resize về 96×96
- Thời gian: 10-15 phút

**Cell 2.5:** Chia Train/Test (80/20)
- Tự động chia dataset
- Thời gian: 2 phút

**Cell 2.6:** Hiển thị mẫu ảnh
- Xem preview các lớp biển báo

---

#### PHẦN 3: Huấn luyện mô hình (30-45 phút)

**Cell 3.1:** Thiết lập Data Generators
- Tạo data generators với augmentation

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

# Tải TFLite model
files.download(f"{MODELS_DIR}/traffic_sign_model_int8.tflite")

# Tải class labels
files.download(f"{MODELS_DIR}/class_labels.txt")
```

### Cách 2: Từ Google Drive (khuyến nghị)

1. Mở Google Drive: https://drive.google.com
2. Vào thư mục: **MyDrive/TrafficSignRobot/models/**
3. Tải các file sau về `D:\DoAn_Robot\models\`:
   - ✅ **model_data.h** (quan trọng nhất cho ESP32)
   - ✅ **traffic_sign_model_int8.tflite**
   - ✅ **class_labels.txt**
   - 📊 training_curves.png (để báo cáo)
   - 📊 confusion_matrix.png (để báo cáo)
   - 📊 best_model.h5 (backup)

---

## Các file sẽ được tạo ra

```
Google Drive/MyDrive/TrafficSignRobot/
├── dataset/              # GTSRB raw dataset (1.2GB)
├── dataset_filtered/     # 15 lớp đã lọc (3,000 ảnh)
├── data_train/          # Training set (2,400 ảnh)
├── data_test/           # Test set (600 ảnh)
└── models/              # ⭐ FOLDER QUAN TRỌNG NHẤT
    ├── best_model.h5                    # Keras model (backup)
    ├── traffic_sign_model_int8.tflite  # TFLite int8 model
    ├── model_data.h                     # ⭐ C++ header cho ESP32
    ├── class_labels.txt                 # Danh sách tên lớp
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
| Test Accuracy | 92% | 90% |
| Model Size (int8) | 350KB | <500KB |
| Training Time | 30 min | - |
| Total Time | 90 min | - |

### 📊 Typical Results

```
✅ Test Accuracy: 92.3%
✅ Model Size: 347 KB
✅ Inference Time: ~2.1s on ESP32
✅ Classes: 15 Vietnamese traffic signs
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

### ❌ Lỗi: Accuracy < 90%

**Nguyên nhân:** Model chưa đủ tốt
**Giải pháp:**
1. Tăng EPOCHS từ 50 lên 80 ở Cell 3.3
2. Hoặc tăng ALPHA từ 0.35 lên 0.5 ở Cell 3.2
3. Chạy lại training

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
