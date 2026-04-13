# Chi Tiết Toàn Bộ Dự Án, Phần Cứng, Huấn Luyện và Hướng Đi

## 1. Tổng quan
Dự án này là một hệ thống robot nhận diện biển báo giao thông hướng tới triển khai trên nền tảng nhúng giá rẻ. Hệ thống không chỉ dừng ở mức huấn luyện mô hình AI mà còn bao gồm đầy đủ các phần:
- cơ khí,
- nguồn điện,
- điều khiển động cơ,
- cảm biến an toàn,
- camera AI,
- âm thanh cảnh báo,
- hiển thị,
- pipeline dữ liệu,
- huấn luyện và đánh giá mô hình.

Từ góc nhìn đồ án, đây là một đề tài tích hợp giữa:
- embedded systems,
- computer vision,
- robot control,
- human-assistive interaction.

---

## 2. Mục tiêu hệ thống
Mục tiêu của hệ thống là xây dựng một robot có thể:
1. nhìn thấy và nhận diện biển báo giao thông,
2. cảnh báo người dùng bằng âm thanh/hiển thị,
3. di chuyển cơ bản bằng động cơ,
4. dừng khi có vật cản phía trước,
5. duy trì pipeline train/eval rõ ràng để cải tiến mô hình theo thời gian.

Nói cách khác, mục tiêu không chỉ là “phân loại ảnh”, mà là tạo ra một hệ robot có thể **nhìn – hiểu – phản hồi – di chuyển**.

---

## 3. Kiến trúc phần cứng tổng thể
Theo `plans/260306-1640-hardware-assembly-guide`, hệ thống phần cứng gồm 5 cụm lớn.

### 3.1. Khung xe và hệ nguồn
- Khung xe 3 bánh, 2 tầng
- 2 motor TT DC
- 2 bánh chủ động
- 1 bánh caster
- Holder pin 18650 x2 nối tiếp
- Công tắc ON/OFF
- LM2596 buck converter
- Tụ lọc 470µF và 100µF

### 3.2. Cụm điều khiển chuyển động
- ESP32-S3 DevKitC-1
- L298N motor driver

### 3.3. Cụm cảm biến
- 3 HC-SR04: trái, giữa, phải
- MPU6050
- GPS NEO-6M
- OLED SSD1306

### 3.4. Cụm AI và camera
- ESP32-CAM
- Camera OV2640
- MicroSD trên ESP32-CAM

### 3.5. Cụm phản hồi người dùng
- DFPlayer Mini
- Loa 3W

---

## 4. Vai trò từng phần cứng
### Khung xe 3 bánh
Là giá đỡ toàn bộ hệ thống và nền tảng di chuyển.

### Pin 18650 x2 nối tiếp
Cấp năng lượng chính cho toàn robot. Điện áp danh định khoảng 7.4V, điện áp đầy khoảng 8.4V.

### LM2596
Hạ áp từ pin xuống 5V ổn định để cấp cho các board và ngoại vi logic.

### L298N
Nhận tín hiệu điều khiển từ ESP32-S3 và cấp dòng cho 2 motor. Đây là tầng công suất giữa vi điều khiển và động cơ.

### ESP32-S3
Là bộ điều khiển trung tâm, phụ trách:
- đọc cảm biến,
- xử lý logic tránh vật cản,
- nhận dữ liệu nhận diện từ ESP32-CAM,
- điều khiển motor,
- cập nhật OLED,
- phát âm thanh cảnh báo.

### ESP32-CAM
Phụ trách camera và AI inference. Đây là board chuyên về thị giác trong hệ thống.

### HC-SR04 trái/giữa/phải
Phát hiện vật cản ở 3 vùng không gian trước robot. Cảm biến giữa đặc biệt quan trọng cho quyết định dừng.

### OLED SSD1306
Hiển thị kết quả nhận diện hoặc trạng thái hệ thống.

### MPU6050
Đo góc nghiêng và tư thế robot. Có thể dùng cho ổn định hoặc phân tích chuyển động.

### GPS NEO-6M
Cung cấp vị trí ngoài trời, phục vụ hướng mở rộng định vị hoặc log hành trình.

### DFPlayer Mini + loa
Phát âm thanh thông báo biển báo nhằm tương tác trực tiếp với người dùng.

---

## 5. Kiến trúc 2 board và lý do chọn
Hệ thống được chia thành 2 MCU chính:

### ESP32-CAM
- chuyên xử lý camera,
- chạy phần AI,
- gửi kết quả nhận diện.

### ESP32-S3
- điều khiển robot,
- đọc sensor,
- chạy logic hành vi,
- xuất âm thanh và hiển thị.

### Ý nghĩa của cách tách này
- giảm tải cho từng board,
- tách thị giác và điều khiển thành 2 khối độc lập,
- dễ debug hơn,
- phù hợp vì ESP32-CAM bị hạn chế chân GPIO cho hệ robot nhiều cảm biến.

---

## 6. Luồng nguồn điện
Theo phase 1 plan phần cứng:

Pin 18650 x2 nối tiếp
→ công tắc ON/OFF
→ tụ lọc đầu vào
→ LM2596
→ 5V rail
→ cấp cho ESP32-CAM, ESP32-S3, L298N logic, sensor và module ngoại vi

Nhánh riêng cho motor:
- pin 7.4V đi thẳng vào L298N motor supply,
- không qua buck LM2596.

### Lý do
- motor cần dòng lớn hơn,
- nếu đi qua buck 5V sẽ không phù hợp,
- tách nhánh giúp hệ điều khiển ổn định hơn.

---

## 7. Luồng tương tác phần cứng
### Luồng tổng thể
1. ESP32-CAM chụp ảnh.
2. Mô hình AI xử lý ảnh.
3. ESP32-CAM gửi kết quả nhận diện qua UART sang ESP32-S3.
4. ESP32-S3 đọc đồng thời khoảng cách từ 3 HC-SR04.
5. ESP32-S3 quyết định cho robot chạy hay dừng.
6. ESP32-S3 cập nhật OLED.
7. ESP32-S3 điều khiển DFPlayer phát âm thanh.
8. L298N nhận lệnh điều khiển motor từ ESP32-S3.

### Bản chất hệ thống
Hệ thống là một chuỗi:
**perception → decision → actuation → user feedback**

---

## 8. Robot di chuyển như thế nào
Robot sử dụng 2 motor TT điều khiển độc lập qua L298N.

### Chế độ di chuyển cơ bản
- tiến,
- lùi,
- rẽ trái,
- rẽ phải,
- dừng.

### Cách điều khiển
ESP32-S3 xuất tín hiệu:
- GPIO4/5/6/7 điều khiển chiều quay motor,
- GPIO15/16 điều khiển PWM tốc độ cho ENA/ENB.

### Logic tránh vật cản
Trong integration test của plan phần cứng:
- nếu cảm biến giữa đo khoảng cách nhỏ hơn 30 cm,
- robot dừng ngay.

Đây là lớp an toàn cơ bản trước khi tích hợp AI hành vi phức tạp hơn.

---

## 9. Hai pipeline AI trong dự án
### 9.1. Baseline classifier
Đây là hướng nghiên cứu ban đầu hoặc hướng đối chiếu.

Đặc điểm:
- input ảnh `96x96`,
- output vector 5 lớp,
- phù hợp cho baseline/debug.

File chính:
- `notebooks/train_classifier_gtsrb.py`
- `notebooks/Train_Traffic_Sign_Classifier_Colab.py`
- `models/classifier_gtsrb_float32.tflite`
- `models/classifier_gtsrb_int8.tflite`

### 9.2. Canonical FOMO
Đây là pipeline chính hiện tại.

Contract:
- input: `[1,96,96,3]`
- output: `[1,12,12,5]`
- schema: `fomo-grid-v2`
- labels: `_background_`, `stop`, `speed_limit`, `warning`, `other_reg`

File chính:
- `scripts/esp32cam_fomo_contract.py`
- `scripts/esp32cam_fomo_dataset.py`
- `scripts/train_esp32cam_fomo.py`
- `scripts/evaluate_esp32cam_fomo.py`
- `scripts/generate_esp32cam_fomo_report.py`

---

## 10. Vì sao FOMO là hướng chính
FOMO được xem là canonical vì:
1. có file contract riêng,
2. train/eval/report đều khớp output `12x12x5`,
3. có artifact thực sự trong `models/`,
4. phù hợp hơn với ảnh full-frame từ camera thực tế.

Từ góc nhìn đồ án, việc chuyển từ classifier sang FOMO cho thấy đề tài đã tiến từ xử lý ảnh cắt sẵn sang nhận diện nhẹ trên ảnh camera thật.

---

## 11. Dữ liệu sử dụng
### Dữ liệu gốc
- `data/gtsrb_raw/`

### Dữ liệu đã lọc
- `data/gtsrb_filtered/`

### Dữ liệu train/val/test cho classifier-style
- `data/train/`
- `data/val/`
- `data/test/`

### Dữ liệu âm tính
- `data/no_sign/`
- `data/_zz_no_sign_excess/`

### Dữ liệu cho FOMO
- `data/esp32cam-fomo/generated/`
- `data/esp32cam-fomo/fomo_manifest.csv`

---

## 12. Chia train / val / test hiện tại
Theo `models/fomo_summary.json`:

Mỗi lớp đều được chia đều:
- Train: `480`
- Val: `120`
- Test: `120`

5 lớp gồm:
- `_background_`
- `stop`
- `speed_limit`
- `warning`
- `other_reg`

Tổng:
- Train: `2400`
- Val: `600`
- Test: `600`

### Ý nghĩa
- split cân bằng giúp so sánh công bằng giữa các lớp,
- giảm tình trạng một lớp chiếm ưu thế trong accuracy tổng.

---

## 13. Mapping nhãn hiện tại
Theo contract canonical:
- `_background_`
- `stop`
- `speed_limit`
- `warning`
- `other_reg`

### Ý nghĩa thực tế
- `_background_`: nền, không có biển báo
- `stop`: biển dừng
- `speed_limit`: nhóm biển giới hạn tốc độ
- `warning`: nhóm biển cảnh báo
- `other_reg`: nhóm biển quy định khác

### Lưu ý quan trọng
`docs/dataset_mapping.md` mô tả 15 lớp chi tiết theo nhãn cũ. Tài liệu đó chỉ nên dùng như dữ liệu lịch sử/tham khảo, không phải source of truth của pipeline hiện tại.

---

## 14. Manifest dữ liệu FOMO
Theo `scripts/prepare_esp32cam_fomo_manifest.py`, manifest canonical gồm các cột:
- `image_path`
- `domain`
- `split`
- `label`
- `x1`
- `y1`
- `x2`
- `y2`

### Quy tắc xử lý
- label khác `_background_` mà thiếu bbox thì bị loại,
- `_background_` thì bbox để trống,
- manifest đầu ra là canonical manifest phục vụ train/eval.

Điều này cho thấy pipeline dữ liệu đã được chuẩn hóa tương đối chặt chẽ.

---

## 15. Mô hình huấn luyện canonical hiện tại
Theo `scripts/train_esp32cam_fomo.py`, mô hình gồm:
- Conv2D(16, stride=2)
- SeparableConv2D(24)
- MaxPooling2D
- SeparableConv2D(32)
- MaxPooling2D
- SeparableConv2D(48)
- SeparableConv2D(64)
- Conv2D(NUM_CLASSES, kernel 1x1)
- Softmax

### Đặc tính
- mô hình nhỏ,
- phù hợp embedded AI,
- thiết kế cho grid detection thay vì classification thuần.

---

## 16. Cách huấn luyện mô hình
### Cấu hình chính
- Optimizer: Adam
- Learning rate: `1e-3`
- Epoch mặc định: `30`
- Batch size: `32`
- EarlyStopping: `patience=6`
- ReduceLROnPlateau: `patience=3`, `factor=0.5`

### Loss và weighting
- `_background_`: `0.05`
- `sign`: `8.0`

### Ý nghĩa
Vì grid nền nhiều hơn grid chứa biển báo, hệ thống phải tăng trọng số cho sign cells để tránh model học thiên về nền.

---

## 17. Artifact sau huấn luyện
Pipeline export ra:
- `traffic_sign_fomo_float32.tflite`
- `traffic_sign_fomo_int8.tflite`
- `model_data.h`
- `class_labels.txt`
- `fomo_summary.json`
- `fomo_eval_report.json`

### Kích thước hiện tại
- float32 TFLite: `37944` bytes
- int8 TFLite: `23832` bytes
- `model_data.h`: `237284` bytes
- `fomo_eval_report.json`: `6054` bytes

Đây là các bằng chứng quan trọng cho việc pipeline đã chạy thực sự chứ không chỉ là mô tả lý thuyết.

---

## 18. Toàn bộ kết quả huấn luyện hiện có
Theo `models/fomo_summary.json`:

### Final results
- Train loss: `0.0401`
- Val loss: `0.0384`
- Train sign-cell recall: `0.7368`
- Val sign-cell recall: `0.5839`

### History đáng chú ý
- categorical accuracy train ở cuối khoảng `0.9372`
- categorical accuracy val ở cuối khoảng `0.9491`
- sign-cell recall tăng dần qua các epoch
- loss giảm ổn định qua quá trình train

### Nhận xét
- mô hình có học được đặc trưng,
- nhưng sign-cell recall trên val còn thấp hơn train khá rõ,
- vẫn còn khoảng cách để tối ưu thêm.

---

## 19. Toàn bộ kết quả đánh giá và thử nghiệm hiện có
Theo `models/fomo_eval_report.json` và report pack:

### Canonical eval @ threshold 0.65
- Train accuracy: `0.5996`
- Val accuracy: `0.5900`
- Test accuracy: `0.5433`

### Domain breakdown trên test
- Print: `0.5300`
- Screen: `0.5567`

### Strict release gate
- Threshold: `0.7`
- Min votes: `2`
- Print: `0.4833`
- Screen: `0.5100`

### Per-class test metric nổi bật
- `stop` và `other_reg` đang khá hơn một số lớp khác
- `speed_limit` và `warning` còn dễ nhầm
- `_background_` vẫn còn false positive/false classification đáng kể

### Kết luận từ số liệu
Mô hình đã hoạt động và có thể đưa vào thử nghiệm hệ thống, nhưng chất lượng hiện tại vẫn chỉ ở mức trung bình, chưa phải mức sẵn sàng sản phẩm cuối.

---

## 20. Kết quả thử nghiệm phần cứng trong plan
Plan phần cứng chia làm 5 phase thử nghiệm:

### Phase 1. Chassis + power
- lắp khung 3 bánh,
- hoàn thiện hệ pin,
- chỉnh LM2596 về 5V,
- tạo nhánh nguồn riêng cho motor.

### Phase 2. Motor + L298N
- test tiến,
- test lùi,
- test rẽ trái,
- test rẽ phải,
- cân PWM nếu xe đi lệch.

### Phase 3. Sensor wiring
- test 3 cảm biến HC-SR04,
- test OLED,
- test MPU6050,
- test GPS ngoài trời.

### Phase 4. MCU + audio wiring
- test DFPlayer phát audio,
- test serial giữa ESP32-CAM và ESP32-S3,
- test 2 board giao tiếp được.

### Phase 5. Integration test
- chạy đồng thời 2 ESP32 + motor + sensor + audio + OLED + GPS,
- robot dừng khi vật cản phía trước <30cm,
- khi nhận sign từ ESP32-CAM thì cập nhật OLED và phát audio,
- target chạy liên tục 30 phút không reset,
- target pin >2 giờ.

---

## 21. Tốc độ phát hiện hiện tại nên trình bày thế nào
Hiện repo có:
- accuracy,
- confusion matrix,
- confidence,
- threshold,
- integration flow.

Nhưng repo **chưa có một benchmark FPS/latency end-to-end chuẩn hóa** trong docs cốt lõi hiện tại.

Vì vậy cách trình bày đúng là:
- hệ thống đã có khả năng nhận diện và thử nghiệm runtime,
- nhưng **tốc độ phát hiện chưa được công bố thành chỉ số chuẩn hóa trong tài liệu cốt lõi**,
- cần đo riêng nếu muốn đưa vào slide như một KPI chính thức.

---

## 22. Điểm mạnh của dự án
1. Là đồ án tích hợp đủ nhiều tầng: AI, nhúng, cảm biến, động cơ, âm thanh.
2. Có cấu trúc 2-board hợp lý: một board thị giác, một board điều khiển.
3. Có dữ liệu, pipeline train, artifact và report rõ ràng.
4. Có cơ chế tránh vật cản, không chỉ nhận diện biển báo.
5. Có định hướng hỗ trợ người dùng thực tế qua âm thanh và hiển thị.

---

## 23. Điểm hạn chế hiện tại
1. Accuracy test còn trung bình.
2. Strict release gate còn thấp.
3. Docs cũ và metadata cũ chưa đồng bộ hoàn toàn.
4. Chưa có benchmark tốc độ phát hiện chuẩn hóa.
5. Firmware production hoàn chỉnh chưa được chốt thành một source-of-truth duy nhất trong repo gốc.

---

## 24. Hướng đi tiếp theo
### Về mô hình
- cải thiện dataset thực tế,
- tăng ảnh ngoài môi trường thật,
- tối ưu decode threshold/min_votes,
- giảm nhầm giữa `speed_limit`, `warning`, `other_reg`.

### Về phần cứng
- xác nhận integration test thực tế,
- đo pin runtime thật,
- xử lý triệt để brownout và nhiễu khi motor chạy,
- hoàn thiện wiring ổn định để test dài hạn.

### Về hệ thống
- chuẩn hóa protocol serial giữa 2 board,
- liên kết chặt hơn giữa biển báo nhận diện được và hành vi robot,
- hoàn thiện cơ chế cảnh báo cho người dùng.

---

## 25. Kết luận
Dự án hiện đã có một nền tảng rất rõ về cả phần cứng lẫn phần mềm. Đây không còn là một bài toán train model đơn giản, mà là một hệ robot có camera AI, điều khiển chuyển động, cảm biến an toàn và phản hồi cho người dùng.

Về mặt AI, pipeline canonical hiện tại là FOMO với input `96x96`, output `12x12x5`, 5 nhãn chính và bộ artifact deploy rõ ràng. Về mặt phần cứng, plan lắp ráp đã mô tả đầy đủ nguồn, động cơ, cảm biến, audio, camera và luồng tích hợp 2 board.

Điểm cần tiếp tục là nâng chất lượng nhận diện, đo benchmark runtime chuẩn hóa và chốt firmware tích hợp cuối cùng. Nhưng xét trên nền tảng hiện có, đề tài đã có đủ chiều sâu kỹ thuật và giá trị ứng dụng để phát triển thành một báo cáo đồ án mạnh.