# Hướng dẫn demo và phỏng vấn

## Giới thiệu trong 45 giây

“Sentinel Event Hub là prototype backend xử lý metadata sự kiện camera. Em tách thành domain rules, persistence và API. Camera giả lập gửi sự kiện qua REST; server kiểm tra dữ liệu, phân loại mức độ và lưu SQLite. Dashboard cho phép lọc và xác nhận cảnh báo. Em tập trung vào tính đúng khi gửi trùng, transaction, kiểm thử đồng thời và CI. Project chưa chạy mô hình Computer Vision; đó là thành phần producer có thể tích hợp sau.”

Đây là bản khởi đầu có AI hỗ trợ tạo. Trước khi đưa vào CV, hãy tự chạy, đọc ba module và sửa ít nhất một tính năng bạn hiểu; trình bày trung thực phần bạn đã thực sự làm và kiểm chứng.

## Demo 3–5 phút

1. Khởi động theo README, mở dashboard và nhập API key.
2. Bấm Generate demo events: 12 sự kiện, 3 camera, 2 cảnh báo critical.
3. Chọn severity `critical`; giải thích ngưỡng `>= 0.8`, zone `restricted` và loại `intrusion`.
4. Acknowledge một cảnh báo: critical/open giảm từ 2 còn 1; sự kiện vẫn còn trong lịch sử.
5. Mở `/docs` để giới thiệu schema và HTTP status codes.
6. Chạy simulator hai lần cùng `--run-id`: tổng chỉ tăng trong lần đầu.
7. Chạy `pytest -q` và giới thiệu file mẫu GitHub Actions (CI chưa kích hoạt do quyền token).

Nếu demo đã có dữ liệu, số lượng sẽ cộng dồn. Mỗi lần bấm Generate tạo batch mới; simulator cùng run ID mới kiểm tra được retry.

## Kiến thức thể hiện

| Kiến thức | Bằng chứng trong code | Điều cần giải thích |
|---|---|---|
| Python, enum, type hints | domain.py | Tách logic thuần để dễ kiểm thử |
| HTTP/REST | main.py | 201 vs 200 vs 409 vs 422, GET không đổi trạng thái |
| SQL và index | store.py | Primary key, parameter binding, index và transaction |
| Đồng thời | ingest, test_concurrent_retries | Race condition và lý do khoá trước khi đọc |
| Kiểm thử | tests/test_api.py | Biên ngưỡng, luồng lỗi, retry, persistence |
| Bảo mật cơ bản | authenticate, dashboard | Không có key thì fail closed; textContent tránh chèn HTML |
| Observability | middleware, /health | Request ID để liên kết request; readiness có đọc DB |
| Docker/Linux | Dockerfile, compose.yaml | Non-root, volume, loopback port, environment |
| Git/CI | docs/ci/github-actions.yml | Workflow mẫu: push → lint → test → build image |
| CV pipeline integration | EventIn | Nhận output detector, chưa thực hiện inference |

## Các câu hỏi nên tự trả lời

**Vì sao SQLite?** Một service local và volume nhỏ, không cần vận hành database server. Đổi lại chỉ có một writer tại một thời điểm; không phù hợp nhiều replica cùng dùng file qua network filesystem.

**Hai request cùng event_id đến cùng lúc thì sao?** BEGIN IMMEDIATE lấy write lock trước khi đọc. Một request ghi trước; request sau nhìn thấy record đã commit và trả duplicate hoặc conflict. Primary key là lớp bảo vệ cuối.

**Có exactly-once không?** Không phải bảo đảm end-to-end exactly-once. Đây là deduplication tại storage khi producer dùng ID ổn định. Nếu producer sinh ID mới cho cùng một sự kiện vật lý, server vẫn coi là hai sự kiện.

**Vì sao acknowledge dùng POST?** Là thao tác thay đổi trạng thái; implementation vẫn idempotent nên có thể retry an toàn. Có thể thiết kế PATCH với schema trạng thái nếu workflow mở rộng.

**confidence 95% có nghĩa model đúng 95% không?** Không. Đây là số giả lập; threshold là rule demo. Thực tế cần calibration, dữ liệu gán nhãn và precision/recall theo camera, ánh sáng, khu vực.

**Nhiều camera gửi dữ liệu rất nhanh thì sao?** Đo throughput và latency trước. Nếu nghẽn writer, chuyển PostgreSQL; broker giúp hấp thụ burst và tách producer/consumer nhưng cần retry, dead-letter và giám sát backlog.

**Security còn thiếu gì?** API key chung không có danh tính operator, RBAC, TLS, rotation, rate limit và chống sửa audit. Prototype chỉ bind localhost.

**Nếu người dùng gửi SQL injection?** Giá trị đều đi qua parameter binding; tên cột trong filter do code cố định. Dashboard render dữ liệu bằng textContent.

**Test persistence đã chứng minh gì?** Một file SQLite được đọc lại khi tạo app mới; chưa phải test mất điện hay khôi phục backup.

## CV — chỉ dùng sau khi tự chạy và hiểu code

**Sentinel Event Hub — Camera Event Triage Prototype** | Python, FastAPI, SQLite, Docker, pytest, GitHub Actions

- Developed a camera-event triage prototype with validated REST ingestion, priority rules, operator acknowledgement, and transactional audit history.
- Implemented storage-level deduplication and conflict detection, with automated tests for concurrent retries, authorization, validation boundaries, and persistence.
- Added a lightweight operations dashboard, container configuration, and a CI workflow template for linting, tests, and image builds.

Không ghi “AI detection system”, “production-ready”, “real-time high performance” hoặc số throughput/accuracy nếu chưa tự đo. Nếu được hỏi, nói rõ đây là prototype có AI hỗ trợ và nêu phần bạn đã tự chỉnh sửa.

## Bài tập mở rộng để thực sự làm chủ

- Thêm trạng thái `resolved` với quy tắc chỉ được resolve sau acknowledge, kèm test transition sai.
- Thêm camera_id filter: cập nhật query, UI và test.
- Thêm test confidence đúng 0 và 1; giải thích vì sao chúng hợp lệ.
- Thêm detector adapter đọc metadata từ video thật và một bộ clip gán nhãn trước khi tính precision/recall.
