# Design Guidelines

## Goal
Giữ bộ tài liệu và pipeline naming của repo dễ hiểu cho người mới, đặc biệt trong bối cảnh repo đang chứa cả baseline classifier lẫn canonical FOMO.

## Documentation Design Rules
1. Luôn nói rõ một trong hai trạng thái:
   - `baseline classifier`
   - `canonical FOMO`
2. Nếu tài liệu nhắc `fomo_*` artifact, phải kiểm tra metadata trước khi mô tả.
3. Không dùng từ `release` cho classifier nếu không có quyết định mới được ghi nhận.
4. Legacy docs phải được xem là reference/historical nếu mâu thuẫn với docs cốt lõi.

## Terminology

| Term | Use when |
|---|---|
| Canonical FOMO | nói về release path hiện tại theo artifact/contract |
| Baseline classifier | nói về path đối chứng/debug |
| Legacy docs | nói về tài liệu cũ còn hữu ích nhưng không còn authoritative |
| Canonical manifest | nói về `data/esp32cam-fomo/fomo_manifest.csv` sau bước chuẩn hóa |

## Naming Guidance
- Ưu tiên tên phản ánh đúng bản chất model thay vì chỉ dựa vào tên file lịch sử.
- Khi một file tên `fomo_*` nhưng metadata là classifier, phải ghi rõ đó là incompatibility lịch sử.
- Giữ label names đúng exact string, không dịch nhãn canonical trong artifact.

## Diagram / Table Preference
- Ưu tiên bảng ngắn và flow đơn giản hơn đoạn văn dài.
- Khi mô tả pipeline, tách baseline và canonical thành hai lane rõ ràng.

## UX for New Contributors
Một người mới nên đọc theo thứ tự:
1. `README.md`
2. `docs/project-overview-pdr.md`
3. `docs/system-architecture.md`
4. `docs/deployment-guide.md`
5. chỉ sau đó mới đọc tài liệu legacy

## Anti-Patterns to Avoid
- Trộn classifier và FOMO trong cùng một hướng dẫn mà không gắn nhãn.
- Nói `Edge Impulse` là đường chính nếu artifact hiện tại không chứng minh điều đó.
- Đưa mapping 15 lớp vào chỗ đang mô tả canonical 5 lớp.

## Content Style
- Súc tích trước, bối cảnh sau.
- Chỉ ghi metric có bằng chứng file.
- Nếu chưa chắc, dùng wording bảo thủ như `artifact hiện có cho thấy` hoặc `repo hiện ghi nhận`.

## Unresolved Questions
- Có nên đổi tên một số artifact/metadata trong tương lai để giảm technical debt về naming không?