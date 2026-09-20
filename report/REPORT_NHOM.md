# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** C Sủi
**Thành viên:** Nguyễn Anh Trí, Phạm Minh Cương (cùng corpus chủ đề KTX; số liệu tham chiếu chéo từ repo Võ Đức Trí, Trần Cao Thắng, Đỗ Hoàng Nam Khánh — mỗi repo một corpus, ghi rõ nguồn)
**Ngày:** 19/09/2026

> **Nộp 1 bản / nhóm.** Phần cá nhân mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Ký túc xá — dịch vụ và quy định đại học (ĐHQG-HCM, Bách Khoa Hà Nội).

**Tại sao nhóm chọn chủ đề này?**
> KTX là mảng dịch vụ đại học có văn bản quy định rõ theo mục (phí, giờ giấc, thủ tục, kỷ luật) — lý tưởng để so sánh chunking theo section với chunking cố định. Cùng một câu hỏi ("mấy giờ đóng cổng?") có đáp án khác nhau theo trường và theo đối tượng, tạo điều kiện thật cho metadata filter — đúng ràng buộc K4-L3A.

### Danh sách tài liệu (Data Inventory)

Corpus `data/ky-tuc-xa/` (Trí): 6 tài liệu nền + 4 tài liệu stress-test tổng hợp (ghi rõ license). Cương bổ sung nhánh UIT + Thư viện Trung tâm + KTX ĐHQG-HCM (7 docs, xem repo Cương).

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | ktx-gioi-thieu-chung | https://ktx.vnuhcm.edu.vn | 2026-09-19 / not-stated | 1206 | audience=all, dept=student-services, category=overview, lang=vi |
| 2 | ktx-dang-ky-phong-sinh-vien | https://sv.ktxhcm.edu.vn | 2026-09-19 / not-stated | 1242 | audience=student, category=registration, lang=vi |
| 3 | ktx-muc-phi-sinh-vien | https://ktx.vnuhcm.edu.vn | 2026-09-19 / not-stated | 1014 | audience=student, dept=finance, category=fees, lang=vi |
| 4 | ktx-noi-quy-sinh-vien | https://huongdan.ktxhcm.edu.vn | 2026-09-19 / not-stated | 1198 | audience=student, category=rules, lang=vi |
| 5 | ktx-quy-dinh-can-bo-truc | https://ktx.vnuhcm.edu.vn | 2026-09-19 / not-stated | 1026 | audience=staff, dept=administration, category=rules, lang=vi |
| 6 | ktx-thu-tuc-giay-to | https://huongdan.ktxhcm.edu.vn | 2026-09-19 / not-stated | 1199 | audience=student, category=procedure, lang=vi |
| 7 | ktx-bieu-phi-cu-2023 (stress: biểu phí hết hiệu lực) | https://ktx.vnuhcm.edu.vn | 2026-09-19 / 2023-08-01 | 683 | audience=student, category=fees, synthetic-stress |
| 8 | ktx-noi-quy-hust (stress: trường khác, 23:00 vs 22:30) | https://ktx.hust.edu.vn | 2026-09-19 / not-stated | 776 | audience=student, category=rules, synthetic-stress |
| 9 | ktx-bang-tin-tho (stress: nhiễu menu/tin tức) | https://ktx.vnuhcm.edu.vn | 2026-09-19 / not-stated | 918 | audience=all, category=news, synthetic-stress |
| 10 | ktx-guest-house-faculty (stress: tiếng Anh) | https://ktx.hust.edu.vn | 2026-09-19 / not-stated | 802 | audience=faculty, lang=en, synthetic-stress |

**Trung thực crawl:** fetch trực tiếp 4 cổng KTX đều thất bại có ghi nhận (robots.txt treo, SSL invalid, trang render JS trả về rỗng) — đúng các failure mode codelab đã cảnh báo. 6 file nền được biên soạn từ cấu trúc công khai của các cổng (license `team-authored-from-public-portals`); 4 file stress ghi rõ `team-authored-synthetic-stress` để test giới hạn (version cũ, distractor liên trường, nhiễu, đa ngữ).

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc ngày hiệu lực) trong metadata.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| audience | enum student/faculty/staff/all | student | Lọc theo đối tượng — Q1 bắt buộc (22:30 SV vs 24/24 cán bộ) |
| department | string | student-services | Thu hẹp phạm vi nghiệp vụ (học vụ vs tài chính) |
| category | string | fees/rules/procedure | Lọc theo loại câu hỏi (tra phí vs tra thủ tục) |
| language | enum vi/en | en | Tách tài liệu tiếng Anh khỏi query tiếng Việt |
| document_version | date/not-stated | 2023-08-01 | Phân biệt biểu phí hết hiệu lực với biểu hiện hành (Q6) |
| source_url/retrieved_at | string/date | https://ktx.vnuhcm.edu.vn | Truy vết nguồn, kiểm độ mới |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

### Phân tích đường cơ sở (Baseline Analysis)

`ChunkingStrategyComparator().compare()` trên `ktx-noi-quy-sinh-vien.md` (chunk_size=500):

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| ktx-noi-quy-sinh-vien | FixedSizeChunker (`fixed_size`) | 2 | 474.5 | Trung bình — có thể cắt giữa câu/điều khoản |
| ktx-noi-quy-sinh-vien | SentenceChunker (`by_sentences`) | 4 | 235.0 | Tốt — mỗi chunk là câu hoàn chỉnh, nhưng mất cấu trúc mục |
| ktx-noi-quy-sinh-vien | RecursiveChunker (`recursive`) | 2 | 469.0 | Tốt nhất baseline — giữ ranh giới mục/đoạn |

### Chiến lược của từng thành viên

**Thành viên 1 — Nguyễn Anh Trí**
- **Loại chiến lược:** RecursiveChunker (chunk_size=500) + sidecar Graph RAG (LLM triple extraction qua DeepSeek-compatible API, graph adjacency-list, cache `data/graph_triples.json`).
- **Mô tả & lý do chọn cho chủ đề này:** Văn bản quy định KTX biên soạn theo mục (`##`) — recursive giữ ranh giới mục mà không vỡ vụn. Graph sidecar để kiểm chứng giả thuyết: quan hệ tường minh (phòng→phí, cổng→giờ→đối tượng) truy xuất tốt hơn similarity ở câu hỏi đa sự kiện.

**Thành viên 2 — Phạm Minh Cương**
- **Loại chiến lược:** HeadingChunker(300) — tách theo tiêu đề, gắn tiêu đề tài liệu + mục vào mọi mảnh con.
- **Mô tả & lý do chọn:** Corpus quy định UIT/VNULIB/KTX có cấu trúc mục chặt; mỗi section là đơn vị ngữ nghĩa trọn vẹn do người soạn chia sẵn. Chạy trên 7 docs → 23 chunks, avg 221.1. Đáp ứng yêu cầu "ít nhất 1 thành viên chunk theo heading".
- **Code snippet (nếu custom):**
```python
class HeadingChunker:
    """Tach theo tieu de Markdown, gan tieu de vao moi manh con."""
    def __init__(self, max_len: int = 300): ...
    def chunk(self, text: str) -> list[str]: ...
```

**Tham chiếu chéo (repo bạn, corpus khác — không tính vào so sánh cùng-corpus):**
- **Võ Đức Trí** — RecursiveChunker(500) trên corpus KTX riêng (7 docs: kỷ luật, PCCC, biểu phí...), mock embedder, tổng 3/10; Q5 dùng filter audience=student (100% kết quả đúng đối tượng).
- **Trần Cao Thắng** — chunker built-in (FixedSize/Recursive) trên corpus học vụ (ĐKHP, học bổng, phúc khảo, thư viện), 4/5 câu có chunk liên quan top-3; Q3 cứu bằng filter audience=student.
- **Đỗ Hoàng Nam Khánh** — HeadingChunker(max_len=600, chuyển đổi được fixed/recursive) trên corpus VinUni (8 files/43 chunks), mock: 1/5 ở mức keyword nhưng 3/5 ở mức doc_id.

### So Sánh Giữa Các Thành Viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Anh Trí | RecursiveChunker + Graph sidecar (KTX, semantic) | 8/10 (Q1–Q5); graph 2/16 | Giữ cấu trúc mục; graph phơi bày xung đột liên văn bản | Distractor cùng chủ đề khác trường vẫn chen top-1 |
| Minh Cương | HeadingChunker(300) (UIT/VNULIB/KTX) | 2/5 evidence top-3 | Section = đơn vị ngữ nghĩa trọn vẹn; có bằng chứng chunk-level | Mock embedder kéo top-1 sai 3/5 câu |
| V. Đức Trí (tham chiếu) | RecursiveChunker(500) (KTX riêng, mock) | 3/10 | Filter audience chuẩn xác | Mock làm top-1 sai 4/5 câu |
| C. Thắng (tham chiếu) | Built-in chunkers (học vụ, mock) | 4/5 top-3 | Pre-filter cứu Q3 | Q2/Q5 top-1 nhiễu mock |
| N. Khánh (tham chiếu) | HeadingChunker(600) (VinUni, mock) | 1/5 keyword, 3/5 doc | Phát hiện "đúng doc ≠ đúng chunk" | Chấm doc-level thổi phồng kết quả |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> Recursive/Heading thắng FixedSize trên văn bản quy định vì ranh giới mục do người soạn chia sẵn chính là ranh giới ngữ nghĩa — chunk trùng section giữ trọn điều khoản + số liệu đi cùng nhau. Nhưng chunking chỉ là một tầng: cả 5 repo đều cho thấy mock embedder phá hỏng top-1 bất kể chunker nào, và distractor liên trường (22:30 vs 23:00) chỉ giải được bằng metadata/audience hoặc quan hệ tường minh — không chunker nào tự giải được. Vì vậy "tốt nhất" = heading/recursive + filter + embedder ngữ nghĩa, không phải một chunker đơn lẻ.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

Bộ 8 query `bench.py` (5 câu chung Q1–Q5 + 3 câu stress Q6–Q8):

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | Cổng KTX đóng lúc mấy giờ? (filter audience=student) | 22 giờ 30 đối với sinh viên | ktx-noi-quy-sinh-vien#Gio-ra-vao-cong |
| 2 | Phòng 4 SV giá bao nhiêu/tháng? | 450.000đ/sinh viên/tháng | ktx-muc-phi-sinh-vien#Bang-phi |
| 3 | Hồ sơ nhận phòng gồm giấy tờ gì? | 4 loại: CCCD sao, giấy báo nhập học/thẻ SV, đơn theo mẫu, biên lai cọc 500k | ktx-thu-tuc-giay-to#Ho-so |
| 4 | Quy trình đăng ký mấy bước, khi nào có kết quả? | 4 bước, kết quả trong 7 ngày làm việc | ktx-dang-ky-phong-sinh-vien#Quy-trinh |
| 5 | Vi phạm lần 3 bị xử lý thế nào? | Chấm dứt hợp đồng ở KTX | ktx-noi-quy-sinh-vien#Xu-ly |
| 6 | Phí phòng 8 SV hiện tại bao nhiêu? (stress version) | 250.000đ (biểu cũ 2023 nói 200.000đ) | ktx-muc-phi-sinh-vien (vs ktx-bieu-phi-cu-2023) |
| 7 | SV Bách Khoa HN phải về trước mấy giờ? (stress liên trường) | 23 giờ | ktx-noi-quy-hust |
| 8 | Giặt ủi khu B mở đến mấy giờ? (stress nhiễu) | 20 giờ | ktx-bang-tin-tho#Dich-vu |

### Tổng hợp chất lượng truy xuất của nhóm

Chấm content-level (snippet đáp án trong chunk, không chỉ doc_id):

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|-------------------------------|-------------------------------|---------|
| 1 | Giờ đóng cổng | Recursive + filter (Trí, 1đ @2) | Có | Distractor HUST 23:00 chen top-1 cả vector lẫn graph |
| 2 | Phí phòng 4 | Vector-semantic (2đ @1, 0.661) | Có | Graph cũng trả đúng triple nhưng đồng hạng với biểu cũ |
| 3 | Hồ sơ nhận phòng | Vector-semantic (2đ @1) | Có | Graph-regex miss (entity linker không có node "hồ sơ") |
| 4 | Quy trình đăng ký | Vector-semantic (2đ @1) | Có | Graph chỉ đúng doc, sai chunk |
| 5 | Vi phạm lần 3 | Vector-semantic (1đ @2) | Có | Rule HUST ("tạm dừng 1 học kỳ") chen top-1 |
| 6 | Phí phòng 8 hiện tại | Hòa (cả hai 1đ) | Có | **Cả hai đều xếp biểu cũ 2023 lên #1** — similarity không đọc version |
| 7 | Giờ về HUST | Vector-semantic (2đ @1, 0.661) | Có | Graph miss (không có node "Bach Khoa Ha Noi") |
| 8 | Giặt ủi khu B | Cả hai 2đ @1 | Có | Query trùng tên entity → graph hit; vector cũng hit |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> Có, ở Q1 (Trí), Q3 (Thắng), Q5 (Đức Trí), Q1 (Cương): filter `audience=student` loại toàn bộ văn bản cán bộ/khách (cổng 24/24, phòng khách) khỏi top-k — A/B có/không filter cho top-3 khác nhau hoàn toàn. Nhưng filter không thay thế hiểu câu hỏi: Q1 vẫn lẫn HUST vs VNU (cùng audience), Q6 vẫn thua biểu cũ (cùng audience) — đó là giới hạn cần version-aware ranking hoặc quan hệ tường minh.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
> 1. Cùng code, cùng corpus, chỉ đổi embedder: mock 0/10 → semantic 13/16 — embedder là biến số lớn nhất, không phải chunker.
> 2. Chênh lệch chấm doc-level vs content-level (Khánh: 3/5 doc nhưng 1/5 keyword) — "đúng tài liệu ≠ trả lời được".
> 3. Graph RAG với 125 triple LLM vẫn chỉ 2/16: extraction tốt không cứu được entity linking kém (hub node "Sinh vien" nuốt mọi query) — demo live bằng `compare.py` (query trên, Vector trái / Graph phải).

**Bài học rút ra khi so sánh trong nhóm:**
> Cùng tài liệu, chiến lược khác nhau cho top-3 khác nhau rõ rệt: heading/recursive giữ đáp án nguyên vẹn trong một chunk (Q2–Q4 hit @1), fixed-size và mock-query để đáp án vỡ hoặc lẫn distractor. Nhưng khác corpus thì không so điểm thô được — nhóm chuẩn hoá bằng cách chấm content-level và báo cáo A/B filter thay vì khoe điểm tuyệt đối.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
> (1) Crawl sớm bằng máy cá nhân thay vì môi trường lab (4 cổng KTX chặn fetch tự động); (2) tách file theo audience ngay từ đầu thay vì để hai đáp án chung một trang; (3) gắn `document_version` thật cho mọi biểu phí và thêm trường `academic_year`/`campus` để Q6–Q7 có chiều lọc version và liên trường ngay từ ingest.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | 9 / 10 |
| Thiết kế chiến lược (Strategy Design) | 13 / 15 |
| Chất lượng truy xuất (Retrieval Quality) | 8 / 10 |
| Thuyết trình (Demo) | 4 / 5 |
| **Tổng phần nhóm** | **34 / 40** |
