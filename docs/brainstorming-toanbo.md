# Brainstorming Toàn Bộ Dự Án

## 1. Tên đề tài
**Robot hỗ trợ nhận diện biển báo giao thông cho người dùng, định hướng triển khai trên ESP32-CAM và hệ robot 2 board ESP32.**

Mục tiêu của đề tài không chỉ là train model nhận diện biển báo, mà là xây dựng một **hệ thống robot hoàn chỉnh** gồm phần cứng, phần mềm nhúng, pipeline dữ liệu, mô hình AI, cơ chế cảnh báo và khả năng di chuyển cơ bản.

---

## 2. Bài toán thực tế
Robot cần hoạt động trong môi trường thực với các ràng buộc:
- camera nhúng có tài nguyên hạn chế,
- phần cứng giá rẻ,
- cần nhận diện biển báo từ ảnh thật,
- phải tránh vật cản khi di chuyển,
- cần phản hồi lại cho người dùng bằng âm thanh hoặc hiển thị,
- toàn hệ thống phải đủ gọn để đặt lên xe robot nhỏ.

Nói ngắn gọn, bài toán là kết hợp **AI nhận diện biển báo + điều khiển robot + cảm biến an toàn + phản hồi cho người dùng** trên nền tảng nhúng giá rẻ.

---

## 3. Mục tiêu chính của hệ thống
1. Nhận diện được các nhóm biển báo giao thông quan trọng.
2. Chạy được mô hình AI trên luồng camera phù hợp với ESP32-CAM.
3. Robot có thể di chuyển cơ bản: tiến, lùi, rẽ trái, rẽ phải.
4. Robot tự dừng hoặc hạn chế tiến khi gặp vật cản phía trước.
5. Khi nhận diện được biển báo, hệ thống có thể phát cảnh báo âm thanh và hiển thị thông tin.
6. Có pipeline train/eval rõ ràng để phục vụ báo cáo đồ án và cải tiến sau này.

---

## 4. Kiến trúc tổng thể của hệ thống
Hệ thống được chia thành 4 lớp chính:

### 4.1. Lớp nguồn và cơ khí
- Khung xe 3 bánh
- 2 motor TT + bánh xe
- 1 bánh caster
- Pin 18650 x2 nối tiếp
- Công tắc nguồn
- Buck LM2596 xuống 5V
- Tụ lọc nguồn

### 4.2. Lớp điều khiển chuyển động và cảm biến
- ESP32-S3 DevKitC-1: board điều khiển chính
- L298N: điều khiển 2 motor
- 3 cảm biến HC-SR04: trái, giữa, phải
- MPU6050: đo góc/nghiêng
- OLED SSD1306: hiển thị trạng thái
- GPS NEO-6M: lấy tọa độ
- DFPlayer Mini + loa: phát âm thanh cảnh báo

### 4.3. Lớp thị giác máy tính
- ESP32-CAM: board AI/camera
- Camera OV2640
- MicroSD trên ESP32-CAM
- Mô hình FOMO hoặc artifact AI deploy

### 4.4. Lớp dữ liệu và huấn luyện
- Dataset GTSRB raw
- Dataset đã lọc
- Tập `no_sign`
- Dataset FOMO với manifest
- Script train/evaluate/report
- Artifact `.tflite`, `model_data.h`, metadata

---

## 5. Toàn bộ phần cứng và tác dụng từng phần

### 5.1. Khung xe 3 bánh
- Là nền tảng cơ khí để gắn toàn bộ phần cứng.
- 2 bánh chủ động phía sau, 1 caster phía trước giúp xe quay linh hoạt.

### 5.2. Pin 18650 x2 nối tiếp
- Cung cấp nguồn chính khoảng 7.4V danh định.
- Dùng cho nhánh motor và cấp đầu vào cho mạch giảm áp.

### 5.3. Công tắc ON/OFF
- Bật/tắt toàn bộ hệ thống.
- Giúp thao tác an toàn khi lắp hoặc test.

### 5.4. LM2596 buck converter
- Hạ điện áp pin xuống 5V ổn định.
- Cấp nguồn cho ESP32-CAM, ESP32-S3, logic L298N và các module ngoại vi.

### 5.5. Tụ lọc 470µF và 100µF
- Giảm sụt áp và nhiễu nguồn.
- Rất quan trọng khi motor khởi động để tránh brownout reset ESP32.

### 5.6. L298N motor driver
- Nhận lệnh điều khiển từ ESP32-S3.
- Khuếch dòng để điều khiển 2 motor DC trái/phải.
- Cho phép tiến, lùi, rẽ trái, rẽ phải và chỉnh tốc độ PWM.

### 5.7. 2 motor TT
- Tạo chuyển động cho robot.
- Motor trái và phải được điều khiển độc lập để đổi hướng di chuyển.

### 5.8. ESP32-S3 DevKitC-1
- Là bộ điều khiển trung tâm của robot.
- Nhiệm vụ:
  - đọc cảm biến,
  - nhận dữ liệu từ ESP32-CAM,
  - điều khiển motor,
  - cập nhật OLED,
  - kích hoạt âm thanh,
  - phối hợp toàn bộ luồng hoạt động.

### 5.9. ESP32-CAM
- Là board chuyên trách camera và phần AI inference.
- Chụp ảnh từ OV2640, xử lý và gửi kết quả nhận diện về ESP32-S3 qua serial.

### 5.10. 3 cảm biến HC-SR04
- Gồm trái, giữa, phải.
- Dùng để phát hiện vật cản.
- Vai trò chính:
  - cảm biến giữa: quyết định dừng khi vật cản gần,
  - cảm biến trái/phải: hỗ trợ định hướng tránh vật cản.

### 5.11. OLED SSD1306
- Hiển thị trạng thái hệ thống.
- Có thể hiển thị kết quả nhận diện, trạng thái test hoặc thông báo ngắn.

### 5.12. MPU6050
- Đo góc nghiêng và trạng thái chuyển động của robot.
- Hỗ trợ ổn định và có thể dùng cho phân tích hướng/dao động khi di chuyển.

### 5.13. GPS NEO-6M
- Cung cấp thông tin vị trí ngoài trời.
- Có giá trị cho hướng mở rộng hệ thống định vị hoặc ghi log lộ trình.

### 5.14. DFPlayer Mini + loa 3W
- Phát file âm thanh cảnh báo khi phát hiện biển báo.
- Đây là cầu nối giữa kết quả AI và phản hồi thực tế cho người dùng.

---

## 6. Luồng hoạt động phần cứng
Luồng hoạt động tổng quát của robot như sau:

**Pin 18650**
→ cấp nguồn cho **LM2596** và **L298N**
→ LM2596 tạo ra 5V cho các board và sensor
→ **ESP32-CAM** thu ảnh, chạy AI, gửi kết quả qua serial
→ **ESP32-S3** nhận kết quả AI + đọc cảm biến khoảng cách
→ ESP32-S3 quyết định:
- cập nhật OLED,
- phát âm thanh bằng DFPlayer,
- cho motor chạy hoặc dừng,
- phản ứng theo vật cản phía trước.

Có thể mô tả ngắn:

**Camera nhìn biển báo → AI nhận diện → ESP32-S3 xử lý → robot phản ứng + cảnh báo người dùng**

---

## 7. Các phần cứng tương tác với nhau như thế nào
### Luồng chính
1. ESP32-CAM chụp ảnh từ camera.
2. Mô hình AI xử lý ảnh.
3. Kết quả nhận diện được gửi qua UART sang ESP32-S3.
4. ESP32-S3 nhận chuỗi kết quả nhận diện.
5. ESP32-S3 đồng thời đọc khoảng cách từ HC-SR04.
6. Nếu có vật cản gần phía trước thì robot dừng.
7. Nếu nhận diện có biển báo thì:
   - OLED hiển thị nội dung,
   - DFPlayer phát file âm thanh,
   - hệ thống có thể kết hợp với logic điều hướng sau này.
8. L298N nhận lệnh từ ESP32-S3 để điều khiển 2 motor.

### Giao tiếp giữa 2 board
- ESP32-CAM TX(GPIO1) → ESP32-S3 RX(GPIO41)
- ESP32-CAM RX(GPIO3) ← ESP32-S3 TX(GPIO42)
- GND 2 board nối chung

Đây là kênh trao đổi dữ liệu AI giữa board camera và board điều khiển.

---

## 8. Robot di chuyển như thế nào
Robot di chuyển nhờ 2 motor DC được điều khiển riêng qua L298N.

### Các trạng thái cơ bản
- **Tiến**: cả 2 motor quay cùng chiều tiến
- **Lùi**: cả 2 motor quay cùng chiều lùi
- **Rẽ trái**: motor trái và phải quay khác hướng hoặc chênh tốc độ
- **Rẽ phải**: tương tự phía ngược lại
- **Dừng**: PWM về 0

### Điều kiện dừng vì an toàn
Theo integration test trong plan phần cứng:
- nếu cảm biến giữa đo được vật cản gần hơn khoảng 30cm,
- ESP32-S3 dừng motor để tránh va chạm.

### Ý nghĩa
Như vậy robot không chỉ nhận diện biển báo mà còn có tầng hành vi cơ bản:
- di chuyển,
- giám sát vật cản,
- phản hồi theo môi trường.

---

## 9. Hai pipeline AI đang tồn tại
### 9.1. Baseline classifier
- input: ảnh crop `96x96`
- output: vector 5 lớp
- vai trò: baseline, debug, đối chiếu

### 9.2. Canonical FOMO
- input: `[1,96,96,3]`
- output: `[1,12,12,5]`
- schema: `fomo-grid-v2`
- vai trò: pipeline chính hiện tại

Kết luận kỹ thuật hiện nay của repo là:
- **FOMO là hướng triển khai chính**
- classifier là nhánh phụ để so sánh và hỗ trợ nghiên cứu.

---

## 10. Mapping nhãn hiện tại
Theo contract canonical, 5 nhãn hiện tại là:
- `_background_`
- `stop`
- `speed_limit`
- `warning`
- `other_reg`

### Ý nghĩa mapping
- `_background_`: không có biển báo
- `stop`: biển dừng
- `speed_limit`: nhóm biển giới hạn tốc độ
- `warning`: nhóm biển cảnh báo
- `other_reg`: nhóm biển hiệu lệnh/quy định khác

### Lưu ý về mapping cũ
`docs/dataset_mapping.md` vẫn chứa mapping 15 lớp theo kiểu legacy GTSRB. Phần đó có giá trị lịch sử, nhưng **không phải mapping canonical hiện tại**.

---

## 11. Cách chia dữ liệu train / val / test
Theo `models/fomo_summary.json` và report pack hiện có:

### Split canonical hiện tại
Mỗi lớp đều cân bằng:
- **Train**: 480 mẫu / lớp
- **Val**: 120 mẫu / lớp
- **Test**: 120 mẫu / lớp

Với 5 lớp tổng cộng:
- Train: 2400 mẫu
- Val: 600 mẫu
- Test: 600 mẫu

### Ý nghĩa
- dữ liệu được chia cân bằng,
- tránh lệch lớp quá mạnh,
- thuận lợi cho việc đánh giá công bằng giữa các nhóm biển báo.

---

## 12. Manifest dữ liệu FOMO gồm gì
Manifest canonical có các cột:
- `image_path`
- `domain`
- `split`
- `label`
- `x1`
- `y1`
- `x2`
- `y2`

### Ý nghĩa từng trường
- `image_path`: đường dẫn ảnh
- `domain`: loại dữ liệu, ví dụ `print` hoặc `screen`
- `split`: train/val/test
- `label`: nhãn mục tiêu
- `x1,y1,x2,y2`: bounding box của biển báo

### Quy tắc xử lý
- Nếu là `_background_` thì không cần bbox.
- Nếu không phải `_background_` mà thiếu bbox thì bị loại khỏi manifest canonical.

---

## 13. Mô hình huấn luyện hiện tại
Theo `scripts/train_esp32cam_fomo.py`, mô hình canonical là CNN nhỏ gọn cho FOMO:
- Conv2D 16 filters, stride 2
- SeparableConv2D 24
- MaxPooling
- SeparableConv2D 32
- MaxPooling
- SeparableConv2D 48
- SeparableConv2D 64
- Conv2D 1x1 tạo logits theo số lớp
- Softmax ở đầu ra

### Đặc điểm mô hình
- thiết kế nhẹ,
- phù hợp bài toán grid detection,
- phù hợp hơn với thiết bị nhúng so với model lớn.

---

## 14. Cách huấn luyện
### Thiết lập huấn luyện
- Optimizer: Adam
- Learning rate: `1e-3`
- Epoch mặc định trong script: `30`
- Batch size mặc định: `32`
- EarlyStopping: patience `6`
- ReduceLROnPlateau: patience `3`, factor `0.5`

### Loss
Dùng **weighted grid loss** để tăng trọng số cho ô có biển báo:
- `_background_`: `0.05`
- `sign`: `8.0`

### Lý do
Trong bài toán FOMO, số ô nền luôn nhiều hơn ô có biển báo. Vì vậy nếu không tăng trọng số cho sign cells, model dễ thiên về dự đoán nền.

---

## 15. Artifact sau khi train
Pipeline hiện export ra:
- `traffic_sign_fomo_float32.tflite`
- `traffic_sign_fomo_int8.tflite`
- `model_data.h`
- `class_labels.txt`
- `fomo_summary.json`
- `fomo_eval_report.json`

### Kích thước artifact hiện có
- float32 TFLite: `37944` bytes
- int8 TFLite: `23832` bytes
- `model_data.h`: `237284` bytes

Điều này cho thấy mô hình tương đối nhỏ và hướng đến triển khai embedded.

---

## 16. Toàn bộ kết quả huấn luyện hiện có
Theo `models/fomo_summary.json`:

### Final metrics
- Final train loss: `0.0401`
- Final val loss: `0.0384`
- Final train sign-cell recall: `0.7368`
- Final val sign-cell recall: `0.5839`

### Diễn biến huấn luyện
- loss giảm dần qua các epoch
- sign-cell recall tăng dần từ gần 0 lên mức ~0.73 ở train và ~0.58 ở val
- learning rate giữ ở `0.001` trong history hiện có

### Nhận xét
- model học được tín hiệu nhận diện,
- nhưng recall ở val còn chênh so với train,
- cho thấy chất lượng tổng thể chưa quá mạnh.

---

## 17. Toàn bộ kết quả đánh giá hiện có
Theo `models/fomo_eval_report.json` và report pack:

### Canonical eval ở threshold 0.65
- Train overall accuracy: `0.5996`
- Val overall accuracy: `0.5900`
- Test overall accuracy: `0.5433`

### Test theo domain
- Print: `0.5300`
- Screen: `0.5567`

### Strict release gate
- Threshold: `0.7`
- Min votes: `2`
- Print accuracy: `0.4833`
- Screen accuracy: `0.5100`

### Nhận xét
- mô hình đã hoạt động được,
- nhưng độ chính xác test vẫn ở mức trung bình,
- strict gate còn thấp,
- nghĩa là chưa nên khẳng định hệ thống đã sẵn sàng production.

---

## 18. Thử nghiệm phần cứng và tích hợp hiện có trong plan
Plan phần cứng mô tả đầy đủ các bài test:

### Test motor
- tiến
- lùi
- rẽ trái
- rẽ phải

### Test cảm biến
- 3 HC-SR04 trả khoảng cách thay đổi
- OLED hiển thị text
- MPU6050 trả góc nghiêng
- GPS lock tín hiệu ngoài trời

### Test audio
- DFPlayer phát âm thanh từ file MP3 trong thẻ nhớ

### Test giao tiếp 2 board
- ESP32-CAM gửi chuỗi nhận diện qua serial
- ESP32-S3 nhận và in ra serial monitor

### Test tích hợp cuối
- robot chạy đồng thời motor, sensor, OLED, audio, GPS, 2 board ESP32
- khi có vật cản gần phía trước thì dừng
- khi có kết quả nhận diện thì hiển thị + phát âm thanh
- target integration test: chạy liên tục 30 phút không reset
- target pin: trên 2 giờ

---

## 19. Tốc độ phát hiện hiện tại nói thế nào cho đúng
Trong repo hiện có:
- có metric accuracy,
- có threshold,
- có confidence,
- có flow integration,
- nhưng **chưa có benchmark FPS hoặc latency end-to-end chuẩn hóa** trong bộ docs cốt lõi hiện tại.

Vì vậy khi viết báo cáo, nên nói trung thực:
- hệ thống đã có cơ chế nhận diện và thử nghiệm runtime,
- nhưng **tốc độ phát hiện theo FPS/độ trễ chưa được báo cáo thành chỉ số chuẩn hóa trong repo hiện tại**.

Không nên tự ghi một con số FPS nếu chưa có log đo rõ ràng.

---

## 20. Điểm mạnh của đề tài
1. Có cả phần cứng và phần AI, không chỉ là mô hình đơn lẻ.
2. Có thiết kế 2-board rõ ràng: ESP32-CAM cho thị giác, ESP32-S3 cho điều khiển.
3. Có cảm biến an toàn và cơ chế dừng tránh vật cản.
4. Có âm thanh và hiển thị để tương tác với người dùng.
5. Có pipeline train/eval/report phục vụ nghiên cứu bài bản.

---

## 21. Hạn chế hiện tại
1. Kết quả nhận diện chưa đủ mạnh để xem là production-ready.
2. Một số docs và metadata còn mang dấu vết legacy.
3. Chưa có benchmark latency/FPS chuẩn hóa trong docs lõi.
4. Tích hợp firmware production cuối cùng chưa được chốt hoàn toàn trong repo gốc.

---

## 22. Hướng đi tiếp theo
### Về AI
- cải thiện chất lượng dữ liệu thực tế,
- tăng độ đa dạng môi trường,
- tối ưu threshold/decode,
- nâng accuracy test và strict gate.

### Về phần cứng
- hoàn thiện integration test thật,
- đo pin runtime thực tế,
- giảm brownout,
- tăng độ ổn định khi motor và AI cùng chạy.

### Về hệ thống
- thống nhất protocol serial giữa 2 board,
- gắn chặt hơn giữa sign detection và logic điều hướng,
- hoàn thiện trải nghiệm cảnh báo cho người dùng.

---

## 23. Thông điệp chốt cho báo cáo
> Đây là một hệ robot nhận diện biển báo giao thông tích hợp cả AI, cảm biến và điều khiển chuyển động. Hệ thống dùng ESP32-CAM làm khối thị giác máy tính và ESP32-S3 làm bộ điều khiển trung tâm để đọc cảm biến, điều khiển động cơ, hiển thị và phát cảnh báo. Về mặt AI, pipeline canonical hiện tại là FOMO với đầu vào 96x96 và đầu ra grid 12x12x5. Hệ thống đã có dữ liệu, script huấn luyện, artifact mô hình, báo cáo đánh giá và plan tích hợp phần cứng, tạo thành nền tảng hoàn chỉnh cho đồ án và cho các bước tối ưu tiếp theo.