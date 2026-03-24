# Tài liệu giải thích Code — Hệ thống Gợi ý Gói Thầu VietinBank

> **Phiên bản:** 2.0.0 (modular, `src/project_dau_thau/`)
> **Ngày build artifact:** 2026-03-24
> **Ngôn ngữ chính:** Python 3
> **Giao diện:** Streamlit (web)

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc tổng thể](#2-kiến-trúc-tổng-thể)
3. [Cấu trúc thư mục](#3-cấu-trúc-thư-mục)
4. [Chi tiết từng file](#4-chi-tiết-từng-file)
   - [4.1 File gốc (root)](#41-file-gốc-root)
   - [4.2 Package `src/project_dau_thau/`](#42-package-srcproject_dau_thau)
5. [Luồng dữ liệu](#5-luồng-dữ-liệu)
6. [Giải thuật chính](#6-giải-thuật-chính)
7. [Cách chạy hệ thống](#7-cách-chạy-hệ-thống)

---

## 1. Tổng quan hệ thống

Hệ thống Gợi ý Gói Thầu VietinBank là ứng dụng web giúp **doanh nghiệp tìm kiếm các gói thầu phù hợp** và **phân tích đối thủ cạnh tranh**, dựa trên dữ liệu lịch sử đấu thầu. Hệ thống có hai phần:

- **v1 (legacy):** `app.py` — chạy độc lập, dùng thư viện cũ
- **v2 (hiện tại):** `src/project_dau_thau/` — kiến trúc modular, dễ mở rộng

Mục tiêu chính:
- Tìm các gói thầu phù hợp nhất cho một doanh nghiệp
- Gợi ý điểm mạnh/sở trường của doanh nghiệp (lĩnh vực, địa bàn, nhà đầu tư)
- Phân tích **Killer Score** — chỉ số đánh giá mức độ nguy hiểm của từng đối thủ

---

## 2. Kiến trúc tổng thể

Hệ thống v2 tuân theo mô hình **layered architecture** (kiến trúc phân lớp):

```
┌─────────────────────────────────────────────────────────────┐
│                    Giao diện người dùng                    │
│              Streamlit UI (ui/streamlit_app.py)             │
├─────────────────────────────────────────────────────────────┤
│                    Tầng dịch vụ (Services)                  │
│  RecommendationEngine  │  CompetitorAnalyzer  │  Profile    │
├─────────────────────────────────────────────────────────────┤
│                    Tầng xếp hạng (Ranking)                  │
│      HybridRanker ← LexicalIndexer + SemanticIndexer         │
├─────────────────────────────────────────────────────────────┤
│                    Tầng dữ liệu (Data)                      │
│        TenderStore  │  ContractorStore  │  ingest.py         │
└─────────────────────────────────────────────────────────────┘
```

**Luồng xử lý chính:**
1. CSV thô → `ingest.py` làm sạch → Parquet
2. Parquet → build index (lexical + semantic + profiles)
3. Người dùng nhập query → `RecommendationEngine` lọc + chấm điểm → trả kết quả
4. Người dùng chọn gói thầu → `analyze_competitors` tính Killer Score

---

## 3. Cấu trúc thư mục

```
DAUTHAUGITHUB/
├── main.py                        # CLI trung tâm (v2)
├── run.py                         # Wrapper → main.py run
├── convert_data.py                # Wrapper → main.py ingest
├── train_model.py                 # Wrapper → main.py build-index
├── serve.py                       # Wrapper → main.py serve
├── requirements.txt               # Thư viện Python
├── run_fast.bat                   # Shortcut Windows
├── generate_docx.py               # Tạo báo cáo .docx
├── review_code.txt                # Ghi chú review code
├── GIAI_THICH_CODE_THUAT_TOAN.md  # Giải thích thuật toán
│
├── src/project_dau_thau/          # Package chính (v2)
│   ├── __init__.py                # Khởi tạo package, version 2.0.0
│   ├── settings.py                # Cấu hình (đường dẫn, trọng số)
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── ingest.py              # CSV → Parquet pipeline
│   │   └── store.py               # TenderStore & ContractorStore
│   │
│   ├── ranking/
│   │   ├── __init__.py
│   │   ├── lexical.py             # TF-IDF indexer
│   │   ├── semantic.py           # Sentence-BERT indexer
│   │   └── hybrid.py             # Kết hợp tất cả tín hiệu chấm điểm
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── profile.py            # Xây dựng hồ sơ doanh nghiệp
│   │   ├── recommendation.py     # Engine gợi ý chính
│   │   └── competitor.py          # Phân tích Killer Score
│   │
│   └── ui/
│       ├── __init__.py
│       └── streamlit_app.py      # Giao diện web (3 tabs)
│
├── data/
│   └── dauthau_data.csv          # Dữ liệu thô (~16,800+ dòng)
│
└── artifacts/                    # Build artifact (sau khi chạy build-index)
    ├── tender_snapshot.parquet
    ├── contractor_history.parquet
    ├── company_profiles.parquet
    ├── lexical_index.joblib
    ├── semantic_index.joblib
    └── metadata.json
```

---

## 4. Chi tiết từng file

### 4.1. File gốc (root)

---

#### `main.py` — CLI điều phối trung tâm (v2)

Đây là **file chính** điều khiển toàn bộ hệ thống. Khi chạy `python main.py <command>`, nó sẽ:

| Lệnh | Chức năng |
|------|-----------|
| `setup` | Cài đặt thư viện từ `requirements.txt` |
| `ingest` | Chạy pipeline CSV → Parquet (`data.ingest.ingest()`) |
| `build-index` | Build TF-IDF + SBERT index + company profiles |
| `rebuild` | Auto-check: nếu CSV mới hơn artifact → chạy `ingest` + `build-index` |
| `serve` | Khởi động Streamlit UI |
| `run` | Tương đương `rebuild` + `serve` |
| `status` | In ra trạng thái: artifact tồn tại? timestamp? weights? |

**Hàm nội bộ chính:**

- `_pip_install()` — Cài thư viện từ `requirements.txt` bằng `subprocess`
- `_ensure_deps()` — Kiểm tra thư viện đã import được chưa, nếu chưa → gợi ý `setup`
- `_run_ingest()` — Gọi `ingest()` và lưu metadata (timestamp, row count)
- `_run_build_index()` — Gọi lần lượt:
  1. `build_all_profiles()` → `company_profiles.parquet`
  2. `LexicalIndexer().build()` → `lexical_index.joblib`
  3. `SemanticIndexer().build()` → `semantic_index.joblib`
  4. `HybridRanker().build()` → đóng gói toàn bộ
  5. Lưu `metadata.json` (số documents, vocabulary size, semantic status...)
- `_needs_rebuild()` — So sánh `mtime` của CSV vs. `metadata.json`; trả `True` nếu CSV mới hơn → cần rebuild
- `_run_serve()` — Launch Streamlit: `subprocess.run(["streamlit", "run", ...], env={...})` với `PYTHONPATH=src/`
- `_print_status()` — In ra bảng artifact, timestamps, current scoring weights

---

#### `run.py` — Wrapper cho `main.py run`

```python
import sys
import subprocess
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "main.py", "run"])
```

**Chức năng:** Giữ cho người dùng có thể chạy `python run.py` thay vì nhớ lệnh đầy đủ. Tự động chuyển working directory về thư mục chứa file.

---

#### `convert_data.py` — Wrapper cho `main.py ingest`

Tương tự `run.py`, gọi `main.py ingest` — chạy pipeline làm sạch và chuyển đổi dữ liệu từ CSV sang Parquet.

---

#### `train_model.py` — Wrapper cho `main.py build-index`

Gọi `main.py build-index` — build TF-IDF index, semantic index, và company profiles từ dữ liệu đã ingest.

---

#### `serve.py` — Wrapper cho `main.py serve`

Gọi `main.py serve` — khởi động giao diện Streamlit mà không chạy rebuild trước (giả định artifact đã tồn tại).

---

#### `requirements.txt` — Danh sách thư viện

```
streamlit>=1.28.0       # Web UI framework
pandas>=2.0.0            # Xử lý DataFrame
scikit-learn>=1.3.0      # TF-IDF vectorizer
numpy>=1.24.0            # Tính toán số học
xlsxwriter>=3.1.0        # Xuất Excel
pyarrow>=12.0.0          # Đọc/ghi Parquet
python-dotenv>=1.0.0     # Đọc .env file
joblib>=1.3.0            # Lưu/load artifact (index)
sentence-transformers>=2.2.0  # Semantic embedding
```

---

#### `generate_docx.py` — Tạo báo cáo Word

Script độc lập tạo file `BAO_CAO_DU_AN.docx` — báo cáo dự án bằng tiếng Việt, gồm các phần:

1. Trang bìa (logo, tiêu đề, thông tin dự án)
2. Tổng quan hệ thống
3. Công nghệ sử dụng
4. Mô hình dữ liệu
5. Giải thuật chính:
   - **TF-IDF (Lexical Retrieval):** đánh giá độ quan trọng của từ trong văn bản
   - **Hybrid Scoring:** kết hợp nhiều tín hiệu để chấm điểm gói thầu
   - **Killer Score:** đánh giá mức độ nguy hiểm của đối thủ
6. Pipeline xử lý dữ liệu
7. Kết quả kiểm thử
8. Cấu trúc dự án
9. Kết luận
10. Hướng dẫn cài đặt

Sử dụng thư viện `python-docx` với style tùy chỉnh (Times New Roman, header màu xanh, alternating row, đường kẻ ngang).

---

#### `run_fast.bat` — Shortcut Windows

Batch file chạy nhanh trên Windows:

```batch
@echo off
streamlit run src/project_dau_thau/ui/streamlit_app.py
pause
```

---

### 4.2. Package `src/project_dau_thau/`

---

#### `__init__.py` — Khởi tạo package

```python
__version__ = "2.0.0"
```

Định nghĩa version của package để tracking.

---

#### `settings.py` — Cấu hình ứng dụng

Class `AppSettings` chứa toàn bộ cấu hình, đọc từ environment variables (qua `python-dotenv`).

| Nhóm | Thuộc tính | Mô tả | Giá trị mặc định |
|------|-----------|-------|-----------------|
| **Paths** | `raw_csv_path` | Đường dẫn CSV thô | `data/dauthau_data.csv` |
| | `curated_dir` | Thư mục Parquet | `artifacts/` |
| | `artifacts_dir` | Thư mục artifact | `artifacts/` |
| | Computed properties | Tự tính đường dẫn `.parquet`, `.joblib` | — |
| **Semantic** | `semantic_enabled` | Bật/tắt SBERT | `True` |
| | `semantic_model_name` | Tên model SBERT | `BAAI/bge-m3` |
| **Top-K** | `top_k_results` | Số kết quả gợi ý | `20` |
| | `rerank_top_k` | Số candidates trước khi rerank | `50` |
| **Weights** | `lexical` | Trọng số TF-IDF | `0.35` |
| | `semantic` | Trọng số SBERT | `0.35` |
| | `historical` | Trọng số lịch sử | `0.15` |
| | `price` | Trọng số giá | `0.10` |
| | `recency` | Trọng số thời gian | `0.05` |

**Hàm quan trọng:**

- `get_normalized_weights(semantic_ready: bool)` — Khi SBERT không khả dụng, hệ thống tự động **re-normalize** trọng số để tổng = 1.0:
  - `lexical`: 0.35 → 0.54
  - `semantic`: bị loại bỏ
  - `historical`: 0.15 → 0.23
  - `price`: 0.10 → 0.15
  - `recency`: 0.05 → 0.08

---

#### `data/ingest.py` — Pipeline làm sạch dữ liệu

Chuyển đổi `dauthau_data.csv` thô thành hai file Parquet sạch.

**Hàm chính:**

| Hàm | Mô tả |
|-----|-------|
| `_detect_encoding()` | Tự động phát hiện encoding: `utf-8-sig` → `utf-8` → `cp1258` → `latin-1` |
| `_normalize_field(f)` | Map mã lĩnh vực: `HH` → `Hàng hóa`, `XL` → `Xây lắp`, `TV` → `Tư vấn`, `QL` → `Quản lý` |
| `_normalize_text_for_search(s)` | Xóa dấu tiếng Việt (NFKD → ASCII) để tăng khả năng tìm kiếm |
| `read_raw_csv()` | Đọc CSV với encoding đã detect |
| `validate_columns()` | Kiểm tra 8 cột bắt buộc có đủ không |
| `_build_tender_text(row)` | Ghép: bid_name + project_name + field + investor + province → 1 chuỗi search |
| `ingest()` | **Pipeline chính:** parse dates, parse prices, map fields, build tender_text, tạo flag `is_winner`, deduplicate, save Parquet |
| `_build_tender_snapshot(df)` | **Gộp dữ liệu:** Mỗi gói thầu gộp thành 1 dòng — lấy thông tin nhà thầu trúng thầu, số nhà thầu tham gia, giá median, giá bid_price |

**Output của `ingest()`:**

1. **`contractor_history.parquet`** — Mỗi dòng = 1 lần tham gia đấu thầu của 1 doanh nghiệp
   - Các cột: `notifyno`, `bidname`, `bid_result` (1=thắng, 0=thua), `bidprice`, các ngày, `taxcode`, `orgfullname`, `investorname`, `field`, `province`, `tender_text`, `tender_text_ascii`

2. **`tender_snapshot.parquet`** — Mỗi dòng = 1 gói thầu (đã gộp)
   - Các cột: `notifyno`, `bidname`, `projectname`, `investorname`, `field`, `province`, `winner_taxcode`, `winner_name`, `participant_count`, `median_price`, `bid_price`, `price_basis`, `effective_date`, `tender_text`, `tender_text_ascii`, `history` (danh sách participants)

**Quy tắc deduplicate:** `(notifyno, taxcode)` phải là duy nhất — nếu trùng, giữ dòng có `bid_result = 1` (thắng thầu) hoặc dòng đầu tiên.

---

#### `data/store.py` — Tầng truy xuất dữ liệu

Hai class chính:

**`TenderStore`** — Truy vấn thông tin gói thầu:

```python
tstore = TenderStore()
tstore.available_provinces      # Danh sách tỉnh/thành
tstore.available_fields         # Danh sách lĩnh vực
tstore.all_notifynos()          # Tất cả mã thông báo
tstore.filter_active_tenders(
    province=None,              # Lọc theo tỉnh
    field=None,                # Lọc theo lĩnh vực
    price_min=0, price_max=float('inf'),  # Lọc theo giá
    text_query=None            # Lọc theo từ khóa trong tender_text
)
tstore.get_tender_by_notifyno(notifyno)  # Lấy 1 gói thầu cụ thể
```

**`ContractorStore`** — Truy vấn lịch sử doanh nghiệp:

```python
cstore = ContractorStore()
cstore.available_companies       # Danh sách doanh nghiệp
cstore.get_history(orgfullname)  # Lịch sử đấu thầu của 1 công ty
cstore.get_company_taxcode(orgfullname)  # Tra mã số thuế
cstore.get_company_stats(orgfullname)    # Thống kê: participated, won, win_rate
```

**Quy tắc `effective_date`:** Ngày hiệu lực = COALESCE(`decision_date`, `open_date`, `public_date`) — dùng ngày nào có giá trị đầu tiên.

---

#### `ranking/lexical.py` — TF-IDF Indexer

Xây dựng index **TF-IDF (Term Frequency - Inverse Document Frequency)** để đánh giá độ quan trọng của từ trong văn bản.

**Class `LexicalIndexer`:**

| Phương thức | Mô tả |
|-------------|-------|
| `build(tender_df)` | Fit `TfidfVectorizer` trên `tender_text_ascii` với `ngram_range=(1,2)`, `min_df=2`, `max_df=0.95` |
| `score(query)` | Transform query, tính cosine similarity → dict `{notifyno: score}` |
| `save(path)` | Lưu vectorizer + ma trận TF-IDF bằng `joblib` |
| `load(path)` | Load vectorizer + ma trận TF-IDF bằng `joblib` |

**Cách hoạt động TF-IDF:**
- TF-IDF đánh giá một từ **quan trọng** khi nó xuất hiện **nhiều trong văn bản** nhưng **ít xuất hiện trong corpus**
- `ngram_range=(1,2)` nghĩa là đánh giá cả từ đơn ("xây") và cặp từ ("xây cầu")

---

#### `ranking/semantic.py` — Sentence-BERT Indexer

Xây dựng index **semantic** dựa trên **Sentence-BERT** để hiểu ý nghĩa ngữ nghĩa của câu.

**Class `SemanticIndexer`:**

| Phương thức | Mô tả |
|-------------|-------|
| `build(tender_df)` | Load `BAAI/bge-m3`, encode tất cả `tender_text` theo batch (64 records/lần) |
| `score(query)` | Encode query, tính dot product với ma trận embeddings (cosine similarity do đã normalize) |
| `save(path)` | Lưu model name + embeddings bằng `joblib` |
| `load(path)` | Load embeddings |

**Fallback graceful:** Nếu `sentence-transformers` chưa cài → `ready = False`, `score()` trả về dict rỗng. Hệ thống vẫn chạy được với TF-IDF thuần túy.

---

#### `ranking/hybrid.py` — Hybrid Ranker (chấm điểm kết hợp)

**Dataclass `RankedTender`** — Lưu kết quả chấm điểm:

| Thuộc tính | Mô tả |
|-----------|-------|
| `notifyno` | Mã thông báo |
| `bidname` | Tên gói thầu |
| `total_score` | Tổng điểm (0–100) |
| `lexical_score` | Điểm TF-IDF |
| `semantic_score` | Điểm SBERT |
| `historical_score` | Điểm lịch sử doanh nghiệp |
| `price_score` | Điểm phù hợp giá |
| `recency_score` | Điểm thời gian |
| `why` | Chuỗi giải thích tại sao gợi ý |
| ... | Các metadata khác |

**Class `HybridRanker`:**

| Phương thức | Mô tả |
|-------------|-------|
| `build()` | Gọi `LexicalIndexer.build()` + `SemanticIndexer.build()` + `HybridRanker.__init__()` |
| `score(query_text, candidate_df, profile)` | Chấm điểm từng candidate |

**Chi tiết cách chấm điểm 5 thành phần:**

| Thành phần | Max | Cách tính |
|-----------|-----|-----------|
| **Lexical** | 100 | `min(cosine × 100, 100)` |
| **Semantic** | 100 | `min(cosine × 100, 100)` |
| **Historical fit** | 100 | +50 nếu trùng lĩnh vực, +30 nếu trùng tỉnh, +20 nếu trùng nhà đầu tư |
| **Price fit** | 100 | 100 nếu giá trong `[price_low, price_high]`, partial nếu gần khoảng |
| **Recency** | 100 | 100 (≤7 ngày) → 30 (>1 năm) → 0 (quá hạn) |

**Tổng điểm:** `total = 0.35×lexical + 0.35×semantic + 0.15×historical + 0.10×price + 0.05×recency`

**`_build_why()`** — Tạo chuỗi giải thích tự nhiên bằng tiếng Việt, ví dụ: `"Phù hợp lĩnh vực Xây lắp, địa bàn Hà Nội, giá trong ngân sách"`

---

#### `services/profile.py` — Hồ sơ doanh nghiệp

Xây dựng **hồ sơ năng lực** của mỗi doanh nghiệp từ lịch sử đấu thầu.

**Hàm `build_company_profile(history_df, orgfullname)`** — Trả về dict:

```python
profile = {
    "text_profile": "...",       # Văn bản tổng hợp mô tả công ty
    "strong_fields": [...],     # Lĩnh vực thế mạnh (win_rate > 30%)
    "strong_provinces": [...],  # Địa bàn thế mạnh
    "familiar_investors": [...], # Nhà đầu tư đã từng thắng
    "median_price": float,       # Giá trung vị
    "price_low": float,          # Ngưỡng giá thấp
    "price_high": float,         # Ngưỡng giá cao
    "win_rate": float,           # Tỷ lệ thắng thầu
    "total_participated": int,  # Tổng số lần tham gia
    "total_won": int,            # Tổng số lần thắng
    "taxcode": str,             # Mã số thuế
}
```

**Hàm `build_all_profiles(history_df, output_path)`** — Xây dựng profiles cho **tất cả** doanh nghiệp cùng lúc bằng groupby vectorized, lưu ra `company_profiles.parquet`. Chạy một lần khi build-index.

---

#### `services/recommendation.py` — Recommendation Engine

Class `RecommendationEngine` là **API cấp cao** cho việc gợi ý.

```python
engine = RecommendationEngine()
results = engine.recommend(
    query="Xây dựng cầu đường",        # Text query
    company_name="Công ty ABC",        # Tên công ty (có thể None)
    province=None,                     # Lọc theo tỉnh
    field=None,                        # Lọc theo lĩnh vực
    price_min=0,                       # Lọc theo giá
    price_max=1_000_000_000_000,
    top_k=20                           # Số kết quả
)
# results: list[RankedTender], đã sort giảm dần theo total_score
```

**Luồng xử lý bên trong `recommend()`:**

```
1. Load TenderStore → filter theo province/field/price/text
2. Nếu company_name != None:
     → Load profiles → build profile dict
     → Load ContractorStore → kiểm tra công ty có trong dữ liệu không
3. Load HybridRanker → score() tất cả candidates
4. Sort theo total_score descending → lấy top_k
5. Return list[RankedTender]
```

---

#### `services/competitor.py` — Phân tích đối thủ cạnh tranh

**Dataclass `CompetitorInfo`** — Thông tin mỗi đối thủ:

```python
competitor = {
    "orgfullname": "Công ty XYZ",    # Tên công ty
    "taxcode": "0123456789",         # Mã số thuế
    "participated": 50,              # Số lần tham gia
    "won": 35,                       # Số lần thắng
    "win_rate": 0.70,               # Tỷ lệ thắng
    "avg_bid_price": 1_500_000_000, # Giá bid trung bình
    "strong_fields": [...],         # Lĩnh vực mạnh
    "strong_provinces": [...],       # Địa bàn mạnh
    "investor_win_rate": 0.75,       # Win rate cùng nhà đầu tư
    "province_win_rate": 0.60,       # Win rate cùng tỉnh
    "field_win_rate": 0.65,          # Win rate cùng lĩnh vực
    "price_win_rate": 0.55,          # Win rate cùng phân khúc giá
    "killer_score": 8.5,             # Tổng Killer Score (0–10)
    "killer_breakdown": {
        "investor": 2.5,
        "province": 2.5,
        "field": 2.5,
        "price": 1.0,
    }
}
```

**Hàm `analyze_competitors(history_df, notifyno, company_name, top_k=10)`** — Phân tích đối thủ cho một gói thầu cụ thể:

| Bước | Mô tả |
|------|-------|
| 1 | Xác định thông tin gói thầu: investor, field, province, giá |
| 2 | Tìm candidate competitors: cùng investor **HOẶC** cùng field **HOẶC** cùng province |
| 3 | Tính 4 Killer Score dimensions (mỗi cái × 2.5, max 10.0): |
| | - **Investor Win Rate:** win rate với cùng nhà đầu tư |
| | - **Province Win Rate:** win rate trên cùng địa bàn |
| | - **Field Win Rate:** win rate trong cùng lĩnh vực |
| | - **Price Win Rate:** win rate trong cùng phân khúc giá (±20%) |
| 4 | Filter: loại bỏ công ty hiện tại, yêu cầu participated ≥ 2 |
| 5 | Sort theo `killer_score` → trả top 10 |

**Ứng dụng thực tế:** Doanh nghiệp biết đối thủ nào nguy hiểm nhất, tránh tham gia gói thầu có đối thủ quá mạnh.

---

#### `ui/streamlit_app.py` — Giao diện Web (3 tabs)

Phiên bản giao diện **Streamlit v12.0**. Sử dụng `@st.cache_resource` để caching các resource nặng (chỉ load 1 lần).

**Tab 1 — Hồ sơ doanh nghiệp (`_render_profile_tab`):**

- Chọn công ty từ danh sách dropdown
- Hiển thị metrics: Tổng tham gia, Tổng thắng, Tỷ lệ thắng
- Hiển thị: Lĩnh vực thế mạnh, Địa bàn thế mạnh, Khoảng giá thường thắng, Nhà đầu tư quen thuộc
- Bảng lịch sử đầy đủ (có kết quả thắng/thua, giá, ngày)
- Nút **Download Excel** để xuất lịch sử

**Tab 2 — Gợi ý gói thầu (`_render_recommendation_tab`):**

- Radio: "Doanh nghiệp đã có" / "Doanh nghiệp mới"
- Thanh filter: Tỉnh/Thành, Lĩnh vực, Khoảng giá
- Input text để nhập mô tả/từ khóa
- Nút **Tìm kiếm gói thầu** → gọi `RecommendationEngine.recommend()`
- Hiển thị kết quả: thanh tiến trình cho mỗi thành phần điểm, tooltip giải thích, tổng điểm
- Chọn gói thầu → bật panel **Phân tích đối thủ**:
  - Toggle "Loại trừ doanh nghiệp của tôi"
  - Bảng Killer Score với màu sắc heatmap
  - Download Excel

**Tab 3 — Sức khỏe dữ liệu (`_render_health_tab`):**

- Số lượng gói thầu, số lượng lịch sử
- Trạng thái semantic (enabled/disabled)
- Nội dung `metadata.json`
- Các artifact files và timestamps
- Scoring weights hiện tại

---

## 5. Luồng dữ liệu

```
┌──────────────────────────────────────────────────────────────────┐
│                    1. INGEST (một lần khi có CSV mới)             │
│                                                                   │
│  dauthau_data.csv                                                │
│       │                                                           │
│       ▼                                                           │
│  ingest.py: detect encoding → normalize → deduplicate            │
│       │                                                           │
│       ├───► contractor_history.parquet  (mỗi dòng = 1 lần bid)   │
│       │                                                           │
│       └───► tender_snapshot.parquet    (mỗi dòng = 1 gói thầu)  │
│                                                                   │
├──────────────────────────────────────────────────────────────────┤
│                    2. BUILD INDEX (khi ingest xong)               │
│                                                                   │
│  contractor_history.parquet                                      │
│       │                                                           │
│       ▼                                                           │
│  profile.py: build_all_profiles() ──► company_profiles.parquet  │
│                                                                   │
│  tender_snapshot.parquet                                          │
│       │                                                           │
│       ├───► lexical.py: LexicalIndexer.build() ──► lexical_index.joblib
│       │                                                           │
│       └───► semantic.py: SemanticIndexer.build() ─► semantic_index.joblib
│                                                                   │
│  + metadata.json (số docs, vocab size, timestamps)               │
│                                                                   │
├──────────────────────────────────────────────────────────────────┤
│                    3. SERVE (Streamlit UI)                        │
│                                                                   │
│  User chọn Tab 2: Nhập "xây cầu" + chọn công ty XYZ              │
│       │                                                           │
│       ▼                                                           │
│  RecommendationEngine.recommend()                               │
│       │                                                           │
│       ├── TenderStore.filter_active_tenders() ── candidate_df    │
│       │                                                           │
│       ├── ProfileStore.get_profile("XYZ") ── profile_dict        │
│       │                                                           │
│       └── HybridRanker.score(query, candidate_df, profile)        │
│               │                                                   │
│               ├── LexicalIndexer.score() ── lexical_scores        │
│               ├── SemanticIndexer.score() ── semantic_scores     │
│               ├── Historical fit ── historical_scores             │
│               ├── Price fit ── price_scores                       │
│               ├── Recency ── recency_scores                       │
│               │                                                   │
│               └── Weighted sum ── RankedTender[] (top 20)        │
│                                                                   │
│  User chọn 1 gói thầu cụ thể                                     │
│       │                                                           │
│       ▼                                                           │
│  analyze_competitors(history_df, notifyno) ── CompetitorInfo[]  │
│       │                                                           │
│       └── Killer Score = 2.5×(investor + province + field + price)
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Giải thuật chính

### 6.1. TF-IDF (Lexical Retrieval)

**Mục đích:** Tìm gói thầu có **từ khóa** liên quan đến query.

**Công thức TF-IDF:**
```
TF(t,d) = Số lần từ t xuất hiện trong document d / Tổng từ trong d
IDF(t) = log(Tổng số docs / Số docs chứa t)
TF-IDF(t,d) = TF(t,d) × IDF(t)
```

**Ứng dụng trong hệ thống:**
- Mỗi gói thầu được biểu diễn bằng vector TF-IDF (1-gram + 2-gram)
- Query cũng được biến đổi thành vector TF-IDF
- Cosine similarity giữa query vector và document vector → điểm lexical

### 6.2. Sentence-BERT (Semantic Retrieval)

**Mục đích:** Hiểu **ý nghĩa** của query, không chỉ từ khóa.

**Cách hoạt động:**
- Model `BAAI/bge-m3` chuyển mỗi câu thành vector 1024 chiều
- Semantic similarity = dot product của 2 vector (đã normalize → tương đương cosine)

**Ví dụ:**
- Query: "xây cầu qua sông"
- TF-IDF: Cần có từ "cầu" và "sông" → bỏ qua gói "thi công cọc khoan nhồi"
- SBERT: Hiểu "cọc khoan nhồi" liên quan đến xây cầu → vẫn tìm thấy

### 6.3. Hybrid Scoring

Kết hợp 5 tín hiệu để đánh giá toàn diện:

```
Total = 0.35 × Lexical + 0.35 × Semantic + 0.15 × Historical
      + 0.10 × Price + 0.05 × Recency
```

| Tín hiệu | Ý nghĩa |
|----------|---------|
| **Lexical** | Văn bản gói thầu chứa từ khóa query |
| **Semantic** | Ý nghĩa gói thầu liên quan đến query |
| **Historical** | Doanh nghiệp có kinh nghiệm trong lĩnh vực/địa bàn này |
| **Price** | Giá gói thầu nằm trong ngân sách/thị trường của doanh nghiệp |
| **Recency** | Gói thầu còn hiệu lực / gần đây |

### 6.4. Killer Score

Đánh giá mức độ **nguy hiểm** của một đối thủ cạnh tranh (thang 0–10):

```
Killer Score = 2.5 × Investor Win Rate
             + 2.5 × Province Win Rate
             + 2.5 × Field Win Rate
             + 2.5 × Price Win Rate
```

- **Investor Win Rate:** Tỷ lệ thắng thầu khi cùng nhà đầu tư → cao → quen thuộc với investor này
- **Province Win Rate:** Tỷ lệ thắng trên địa bàn → cao → mạnh tại tỉnh này
- **Field Win Rate:** Tỷ lệ thắng trong lĩnh vực → cao → chuyên gia trong ngành
- **Price Win Rate:** Tỷ lệ thắng trong phân khúc giá ±20% → cao → cạnh tranh trực tiếp về giá

---

## 7. Cách chạy hệ thống

### Cách 1: Chạy nhanh (khuyến nghị)

```bash
python run.py
```

### Cách 2: Từng bước riêng lẻ

```bash
# Bước 1: Setup môi trường (chỉ cần chạy 1 lần)
python main.py setup

# Bước 2: Chuyển đổi dữ liệu CSV → Parquet
python main.py ingest

# Bước 3: Build index
python main.py build-index

# Bước 4: Khởi động giao diện web
python main.py serve
```

### Cách 3: Kiểm tra trạng thái

```bash
python main.py status
```

### Trên Windows (shortcut)

```batch
run_fast.bat
```

### Output

- Giao diện Streamlit: `http://localhost:8501`
- Artifact files: thư mục `artifacts/`
- Báo cáo Word: `BAO_CAO_DU_AN.docx` (chạy `python generate_docx.py`)

---

*Document được generate tự động bởi AI từ phân tích source code.*
*Version: 2.0.0 | Date: 2026-03-24*
