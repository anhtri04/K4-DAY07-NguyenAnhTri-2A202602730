# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Nguyễn Anh Trí
**Nhóm:** C Sủi
**Ngày:** 19/09/2026

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
> Hai đoạn văn bản có cosine cao nghĩa là vector embedding của chúng cùng hướng — tức cùng ý nghĩa — dù từ vựng bề mặt có thể khác nhau. Retrieval sẽ xếp chúng gần nhau trong top-k.

**Ví dụ có độ tương tự CAO:**
- Câu A: "Sinh viên đăng ký phòng ở ký túc xá trên cổng trực tuyến."
- Câu B: "Việc đặt chỗ ở KTX cho sinh viên được thực hiện qua website."
- Tại sao tương đồng: khác từ vựng nhưng cùng một ý (đăng ký chỗ ở KTX online) — embedding tốt phải bắt được điều này chứ không so khớp từ.

**Ví dụ có độ tương tự THẤP:**
- Câu A: "Tiền phòng đóng theo học kỳ, 5 tháng một lần."
- Câu B: "Khách không được ở lại qua đêm trong phòng sinh viên."
- Tại sao khác: hai chủ đề không liên quan (học phí vs quy định khách thăm) — vector chỉ về hai hướng khác nhau.

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
> Cosine chỉ đo góc giữa hai vector nên miễn nhiễm với độ dài văn bản (chunk dài có norm lớn hơn nhưng không bị phạt); khoảng cách Euclid bị chi phối bởi norm nên chunk dài luôn "xa" mọi query dù cùng chủ đề. Vì store trong lab chuẩn hoá vector (||v||=1), dot product chính là cosine.

### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> Công thức: `ceil((10000 - 50) / (500 - 50)) = ceil(9950 / 450) = ceil(22.11) = 23 chunks`.
> Kiểm lại bằng code có sẵn: `FixedSizeChunker(500, 50).chunk('a'*10000)` → **23 chunks** (khớp công thức).
> *Đáp án: 23 chunks.*

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
> `ceil((10000 - 100) / (500 - 100)) = ceil(9900 / 400) = ceil(24.75) = 25 chunks` (code kiểm chứng cũng ra 25). Overlap lớn giữ câu/ý bị cắt ở biên chunk xuất hiện ở cả hai chunk kề nhau, tăng khả năng retrieval bắt được thông tin — đánh đổi bằng nhiều chunk hơn (tốn store + embedding).

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`** — hướng tiếp cận:
> Dùng `re.split(r"(?<=[.!?])\s+", ...)` — lookbehind tách *sau* dấu câu nên giữ được dấu `.`/`!`/`?` (split thô `[.!?]\s+` sẽ nuốt dấu và tạo câu cụt). Gom tối đa `max_sentences_per_chunk` câu/chunk, strip whitespace; text rỗng → `[]`. Edge case đã biết và chấp nhận: chữ viết tắt (`TS.`, `v.v.`) và số thập phân bị cắt sai thành "câu" giả.

**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
> Hai chiều: (1) đệ quy *xuống* — thử separator theo thứ tự `["\n\n", "\n", ". ", " ", ""]`, mảnh nào còn dài hơn `chunk_size` thì gọi lại `_split` với separator nhỏ hơn; (2) *gom lên* — nối các mảnh nhỏ liền kề cho tới sát `chunk_size`, nếu thiếu bước này file nhiều dòng ngắn sẽ vỡ thành hàng trăm chunk vụn. Base case: text ≤ `chunk_size` → giữ nguyên; `separators == []` hoặc `""` → cắt cứng theo `chunk_size` (test `test_empty_separators_falls_back_gracefully` bắt buộc nhánh này).

### Lớp EmbeddingStore

**`add_documents` + `search`** — hướng tiếp cận:
> Chỉ dùng in-memory (`_use_chroma = False` cứng — nhánh Chroma chưa cài đặt và không test nào cần). `_make_record` copy metadata (không giữ reference của caller) và backfill `metadata["doc_id"]` từ `doc.id` khi thiếu; `add_documents` embed từng content và append record. `search` embed query rồi chấm dot product (đúng bằng cosine vì vector đã chuẩn hoá), sắp xếp giảm dần, loại `embedding` khỏi output để terminal sạch.

**`search_with_filter` + `delete_document`** — hướng tiếp cận:
> Lọc **trước**, search sau: prefilter exact-match trên metadata rồi cho tập ứng viên chạy chung qua `_search_records` (nhờ đó `test_no_filter_returns_all_candidates` đúng hiển nhiên; lọc sau top-k sẽ mất kết quả hợp lệ vì slot đã bị chiếm). `delete_document` xoá mọi record có `metadata["doc_id"]` khớp, trả `True/False` theo có xoá được gì không.

### Tác tử KnowledgeBaseAgent

**`answer`** — hướng tiếp cận:
> Ba nhịp retrieve → prompt → `llm_fn`: lấy top-k, dựng context đánh số `[1]/[2]/[3]` kèm `source` (doc_id) từng chunk, yêu cầu model chỉ dùng context và trích dẫn số chunk (đạt tiêu chí Source Traceability), chống bịa ("không có trong context thì nói rõ"). Store rỗng hoặc không có kết quả → trả `"No relevant documents found in the knowledge base."` mà không gọi LLM.

---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

```
tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists PASSED
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further PASSED
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED
============================== 42 passed in 0.03s ==============================
```

**Số lượng bài test vượt qua (pass):** 42 / 42

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

Chạy `compute_similarity` trên vector của `_mock_embed` (mặc định của lab, không key). Dự đoán trước khi chạy.

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Sinh vien dang ky phong o ky tuc xa | Dang ky cho o KTX danh cho sinh vien | cao (cùng nghĩa, khác từ) | -0.2380 | ❌ Sai |
| 2 | Tien phong dong theo hoc ky nam thang | Khach khong duoc o lai qua dem trong phong | thấp (khác chủ đề) | 0.0606 | ✅ Đúng (gần 0) |
| 3 | Cong dong luc 22 gio 30 | Gio dong cong la 22 gio 30 phut | cao (gần như giống nhau) | -0.0308 | ❌ Sai |
| 4 | Phong 4 sinh vien gia 450000 dong | Dich vu giat ui mo cua den 20 gio | thấp | 0.1346 | ✅ Đúng hướng |
| 5 | Sinh vien ve muon bi lap bien ban nhac nho | Sinh vien vi pham bi cham dut hop dong | trung bình-cao (cùng chủ đề kỷ luật) | -0.0381 | ❌ Sai |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
> Cặp 1 và 3 bất ngờ nhất: hai câu gần như đồng nghĩa (thậm chí trùng từ) lại cho điểm âm/gần 0. Nguyên nhân: `_mock_embed` băm MD5 toàn chuỗi rồi sinh số giả ngẫu nhiên — nó không mã hoá ngữ nghĩa nên mọi dự đoán dựa trên "nghĩa" đều vô nghĩa. Bài học: điểm cosine chỉ đáng tin khi embedder thật sự hiểu ngôn ngữ; benchmark chạy bằng mock (như run 0/10 của nhóm) đo độ nhiễu chứ không đo retrieval.

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Chiến lược của tôi: `RecursiveChunker(chunk_size=500)` trên corpus `data/ky-tuc-xa/` (10 docs → 21 chunks), embedder ngữ nghĩa thay mock để đo đúng retrieval. Chấm content-level: 2đ = snippet đáp án ở chunk top-1, 1đ = ở top-2/3, 0đ = vắng mặt.

| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Cong ky tuc xa dong luc may gio? (filter audience=student) | ktx-noi-quy-hust: "Cong KTX Bach Khoa Ha Noi dong luc 23 gio..." | 0.450 | Một phần (đúng chủ đề, sai trường — gold VNU 22:30 đứng #2) | Agent cần filter + phân biệt trường mới trả lời đúng |
| 2 | Phong 4 sinh vien co muc phi bao nhieu mot thang? | ktx-muc-phi-sinh-vien: "Phong 4 sinh vien: 450000 dong..." | 0.661 | Có, top-1 chứa đáp án | 450000 đồng/sinh viên/tháng [1] |
| 3 | Ho so nhan phong gom nhung giay to gi? | ktx-thu-tuc-giay-to: "Ho so gom 4 loai giay to: CCCD, giay bao nhap hoc..." | 0.576 | Có, top-1 chứa đáp án | 4 loại giấy tờ [1] |
| 4 | Quy trinh dang ky may buoc, khi nao co ket qua? | ktx-dang-ky-phong-sinh-vien: "Buoc 1... ket qua trong 7 ngay lam viec" | 0.491 | Có, top-1 chứa đáp án | 4 bước, kết quả sau 7 ngày làm việc [1] |
| 5 | Vi pham lan thu ba bi xu ly nhu the nao? | ktx-noi-quy-hust: "Vi pham lan ba bi tam dung cho o mot hoc ky" | 0.588 | Một phần (rule của HUST; gold VNU "cham dut hop dong" đứng #2) | Cần ghi rõ trường mới trả lời đúng |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** 5 / 5 (Q2–Q4 đạt 2đ top-1; Q1, Q5 đạt 1đ vì distractor cùng chủ đề khác trường chen lên top-1 — xem phân tích lỗi ở REPORT_NHOM mục 4).

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
> Từ thí nghiệm sidecar Graph RAG: cùng 8 query, vector đạt 13/16 còn graph (LLM extraction, 125 triples) chỉ 2/16 — không phải vì triple kém mà vì entity linking sập trên hub node ("Sinh vien"). Bài học: retrieval tốt cần cả ba tầng (chunk sạch, embedding có ngữ nghĩa, linking/filter chính xác); chỉ sửa một tầng thì điểm không nhúc nhích. Chi tiết so sánh xem `ket_qua_graph_benchmark.txt` và demo `compare.py`.

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 10 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 8 / 10 |
| **Tổng phần cá nhân** | **58 / 60** |
