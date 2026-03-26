# Hệ Thống Gợi Ý Gói Thầu — VietinBank DauThau

> Hệ thống gợi ý gói thầu **offline** chạy trên Streamlit, sử dụng dữ liệu lịch sử đấu thầu nội bộ để xếp hạng và gợi ý gói thầu phù hợp cho doanh nghiệp, kèm phân tích đối thủ cạnh tranh.

---

## Mục lục

- [Tổng quan](#tổng-quan)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Mô hình ML](#mô-hình-ml)
- [Cài đặt](#cài-đặt)
- [Sử dụng](#sử-dụng)
- [Cấu trúc project](#cấu-trúc-project)
- [Cấu hình](#cấu-hình)
- [Dữ liệu & Artifact](#dữ-liệu--artifact)
- [Định hướng phát triển](#định-hướng-phát-triển)

---

## Tổng quan

### Hệ thống làm gì?

Cho một **doanh nghiệp** muốn tìm gói thầu phù hợp:

1. **Xem hồ sơ** — dashboard lịch sử tham gia, tỉ lệ trúng, lĩnh vực/địa bàn mạnh, khung giá thường thắng.
2. **Gợi ý gói thầu** — hybrid retrieval xếp hạng top-K gói thầu phù hợp nhất, có giải thích điểm số.
3. **Phân tích đối thủ** — với mỗi gói thầu được gợi ý, hiển thị đối thủ mạnh và lý do họ đáng ngại.

### Tính năng chính

| Tính năng | Mô tả |
|---|---|
| **Hybrid Retrieval** | Kết hợp lexical (TF-IDF) + semantic (Sentence-BERT) để tìm gói thầu phù hợp |
| **Company Profile** | Tự động xây dựng hồ sơ doanh nghiệp từ lịch sử đấu thầu |
| **Personalization** | Điểm historical fit, price fit, recency dựa trên profile doanh nghiệp |
| **Competitor Analysis** | Phân tích đối thủ theo 4 chiều: chủ đầu tư, địa bàn, lĩnh vực, phân khúc giá |
| **Graceful Degradation** | Semantic retrieval tự tắt nếu chưa cài `sentence-transformers` |
| **Offline-first** | Build artifact 1 lần, query nhanh không cần rebuild |

---

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────┐
│                     USER INTERFACE                       │
│                  Streamlit Web App (UI)                   │
└────────────────────────┬──────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │    Recommendation Engine     │
          │   (recommendation.py)        │
          └──────────────┬──────────────┘
                         │
          ┌──────────────┴──────────────┐
          │       HybridRanker          │
          │  Hybrid Scoring (5 thành phần)
          └──────────────┬──────────────┘
                         │
     ┌───────────────────┼───────────────────┐
     │                   │                   │
┌────▼────┐        ┌─────▼─────┐     ┌──────▼──────┐
│ Lexical │        │ Semantic  │     │  Profile &   │
│  TF-IDF │        │ Sentence  │     │  Heuristics  │
│ (35%)   │        │ Transformer│    │  (30%)       │
└─────────┘        │ (35%)     │     └──────────────┘
                   └───────────┘
                         │
          ┌──────────────┴──────────────┐
          │       Data Store            │
          │  TenderStore / ContractorStore│
          └─────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │       Ingest Pipeline       │
          │  CSV → Parquet (curated)    │
          └─────────────────────────────┘
```

### Luồng dữ liệu

```
data/dauthau_data.csv (CSV gốc)
        │
        ▼  python main.py rebuild
data/curated/
  ├── contractor_history.parquet   (bidder-level, mỗi row = 1 lần tham gia)
  └── tender_snapshot.parquet      (tender-level, mỗi row = 1 gói thầu)
        │
        ▼  python main.py build-index
artifacts/
  ├── company_profiles.parquet    (profile tổng hợp từng doanh nghiệp)
  ├── lexical_index.joblib        (TF-IDF vectorizer + ma trận)
  ├── semantic_index.joblib       (Sentence-BERT embeddings)
  ├── hybrid_index.joblib         (gói gộp cả 2 index)
  └── metadata.json               (thông tin audit: số lượng, timestamp…)
```

---

## Mô hình ML

Hệ thống sử dụng **Hybrid Retrieval** với 5 thành phần điểm số:

### 1. Lexical Score (35%) — TF-IDF

TF-IDF (Term Frequency × Inverse Document Frequency) từ `sklearn`:

```
score = cosine_similarity( query_vector , document_vector )
```

- **Cấu hình:** `ngram_range=(1,2)`, `max_features=25,000`, `sublinear_tf=True`
- **Input:** `tender_text_ascii` (text đã bỏ dấu tiếng Việt)
- **Ưu điểm:** Nhanh, khớp từ chính xác, không cần GPU
- **Nhược điểm:** Không hiểu ngữ cảnh, nhạy với từ hiếm/từ đồng nghĩa

### 2. Semantic Score (35%) — Sentence Transformer

Model `paraphrase-multilingual-MiniLM-L12-v2` từ `sentence-transformers`:

- **Embedding:** 384 chiều, pre-trained, hỗ trợ **50+ ngôn ngữ** (bao gồm tiếng Việt)
- **Nguyên lý:** Câu cùng nghĩa → vector gần nhau (cosine similarity)
- **Input:** `tender_text` (giữ dấu tiếng Việt)
- **Cấu hình:** `batch_size=256`, `normalize_embeddings=True`

> **Ví dụ:** Query "thi công xây dựng cầu đường" sẽ tìm được cả gói thầu có tiêu đề "xây cầu giao thông" vì cả 2 cùng vector space.

### 3. Historical Fit (15%) — Heuristic

Dựa trên hồ sơ doanh nghiệp:

| Tiêu chí | Điểm |
|---|---|
| Trùng lĩnh vực mạnh (top 5 lĩnh vực thắng nhiều nhất) | +50 |
| Trùng địa bàn mạnh (top 5 địa phương thắng nhiều nhất) | +30 |
| Trùng chủ đầu tư quen (đã từng tham gia) | +20 |

### 4. Price Fit (10%) — Heuristic

- **100 điểm:** Giá gói thầu nằm trong khung `[price_low, price_high]` (IQR 25%-75%)
- **Partial score:** Giá ngoài khung → tính khoảng cách tương đối
- **0 điểm:** Giá không hợp lệ hoặc không có dữ liệu

### 5. Recency Score (5%) — Heuristic

| Số ngày đến deadline | Điểm |
|---|---|
| ≤ 7 ngày (khẩn cấp) | 100 |
| 8–30 ngày | 80 |
| 31–90 ngày | 60 |
| > 90 ngày | 40 |
| Quá hạn | 30 |

### Công thức tổng

```
total_score = 0.35 * lexical
            + 0.35 * semantic    (nếu có)
            + 0.15 * historical_fit
            + 0.10 * price_fit
            + 0.05 * recency
```

Khi semantic chưa sẵn sàng, trọng số được **re-normalize** tự động.

---

## Cài đặt

### Yêu cầu

- Python 3.10+
- Windows (đã test), macOS/Linux tương thích

### Bước 1: Tạo virtual environment

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Bước 2: Chuẩn bị dữ liệu

Đặt file CSV gốc tại:

```
data/dauthau_data.csv
```

File cần các cột bắt buộc:

| Cột | Ý nghĩa |
|---|---|
| `bidonotifycontractormnotifyno` | Mã gói thầu |
| `bidonotifycontractormbidname` | Tên gói thầu |
| `orgfullname` | Tên doanh nghiệp |
| `taxcode` | Mã số thuế |
| `bidresult` | Kết quả: `1`/`10` = thắng |
| `provincename` | Tỉnh/thành |
| `bidonotifycontractorminvestfield` | Lĩnh vực (HH/XL/TV/PTV/HON_HOP) |
| `bidecontractorinputresultdtobidprice` | Giá dự thầu |
| `bidecontractorinputresultdtoopendate` | Ngày mở thầu |

---

## Sử dụng

### Các lệnh chính

```bash
# Chạy đầy đủ: ingest + build + mở UI
python main.py

# Chỉ mở UI (đã có artifact)
python main.py serve

# Chạy pipeline nhưng không mở UI
python main.py run --no-serve

# Cài dependencies
python main.py setup

# Chỉ ingest CSV → curated parquet
python main.py ingest

# Chỉ build profiles + index (cần curated data)
python main.py build-index

# Ingest + build toàn bộ
python main.py rebuild

# In trạng thái artifact
python main.py status
```

### Luồng khuyến nghị trên UI

1. Chọn **tab "Hồ sơ doanh nghiệp"** → tìm và chọn doanh nghiệp
2. Xem dashboard: tỉ lệ trúng, lĩnh vực/địa bàn mạnh, khung giá
3. Bấm **"Gợi ý gói thầu"** → nhảy sang tab gợi ý với profile đã chọn
4. Xem kết quả: top-K gói thầu, điểm chi tiết từng thành phần, phân tích đối thủ
5. Tùy chỉnh: lọc theo tỉnh, lĩnh vực, khoảng giá, số lượng K

---

## Cấu trúc project

```
DAUTHAUGITHUB/
├── main.py                          # Entry point, CLI commands
├── requirements.txt                  # Python dependencies
├── .env                             # Environment variables (tùy chọn)
│
├── data/
│   ├── dauthau_data.csv             # Dữ liệu gốc (do người dùng cung cấp)
│   └── curated/
│       ├── contractor_history.parquet # Mỗi row = 1 lần tham gia đấu thầu
│       └── tender_snapshot.parquet   # Mỗi row = 1 gói thầu
│
├── artifacts/
│   ├── company_profiles.parquet     # Profile tổng hợp từng doanh nghiệp
│   ├── lexical_index.joblib          # TF-IDF vectorizer + ma trận
│   ├── semantic_index.joblib         # Sentence-BERT embeddings
│   ├── hybrid_index.joblib           # Gói gộp cả 2 index
│   └── metadata.json                 # Audit info
│
├── src/
│   ├── settings.py                  # Cấu hình, trọng số, đường dẫn
│   │
│   ├── data/
│   │   ├── ingest.py                # CSV → curated parquet pipeline
│   │   └── store.py                 # TenderStore & ContractorStore
│   │
│   ├── ranking/
│   │   ├── lexical.py               # TF-IDF LexicalIndexer
│   │   ├── semantic.py              # Sentence-BERT SemanticIndexer
│   │   └── hybrid.py                # HybridRanker (5 thành phần scoring)
│   │
│   ├── services/
│   │   ├── profile.py               # Xây dựng company profiles
│   │   ├── recommendation.py        # RecommendationEngine
│   │   └── competitor.py            # Phân tích đối thủ
│   │
│   └── ui/
│       └── streamlit_app.py         # Giao diện Streamlit
```

---

## Cấu hình

### Biến môi trường (`.env`)

```env
# Đường dẫn dữ liệu
DAUTHAU_RAW_CSV_PATH=data/dauthau_data.csv
DAUTHAU_CURATED_DIR=data/curated
DAUTHAU_ARTIFACTS_DIR=artifacts

# Semantic (tùy chọn)
DAUTHAU_SEMANTIC_ENABLED=false
DAUTHAU_SEMANTIC_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2

# Retrieval
DAUTHAU_TOP_K_RESULTS=20

# Trọng số scoring
DAUTHAU_LEXICAL_WEIGHT=0.35
DAUTHAU_SEMANTIC_WEIGHT=0.35
DAUTHAU_HISTORICAL_WEIGHT=0.15
DAUTHAU_PRICE_WEIGHT=0.10
DAUTHAU_RECENCY_WEIGHT=0.05

# UI
DAUTHAU_APP_TITLE=Hệ thống Gợi ý gói thầu phù hợp cho Doanh nghiệp
```

### Tham số scoring (trong `settings.py`)

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `recency_urgent_days` | 7 | Số ngày coi là khẩn cấp |
| `recency_good_days` | 30 | Số ngày coi là hợp lý |
| `recency_normal_days` | 90 | Số ngày coi là bình thường |
| `historical_field_score` | 50 | Điểm khi trùng lĩnh vực mạnh |
| `historical_province_score` | 30 | Điểm khi trùng địa bàn mạnh |
| `historical_investor_score` | 20 | Điểm khi trùng chủ đầu tư quen |
| `competitor_rate_multiplier` | 2.5 | Hệ số nhân tính điểm đối thủ |
| `competitor_min_join` | 2 | Số lần tham gia tối thiểu để là đối thủ |

---

## Dữ liệu & Artifact

### Artifact là gì?

Artifact là các file **đã build** lưu trên disk, cho phép query nhanh mà không cần chạy lại ML pipeline mỗi lần.

| Artifact | Ý nghĩa | Khi nào rebuild |
|---|---|---|
| `contractor_history.parquet` | Mỗi row = 1 lần tham gia đấu thầu | Khi CSV gốc thay đổi |
| `tender_snapshot.parquet` | Mỗi row = 1 gói thầu | Khi CSV gốc thay đổi |
| `company_profiles.parquet` | Profile tổng hợp từng doanh nghiệp | Khi `contractor_history` thay đổi |
| `lexical_index.joblib` | TF-IDF vectorizer + ma trận | Khi `tender_snapshot` thay đổi |
| `semantic_index.joblib` | Sentence-BERT embeddings | Khi `tender_snapshot` thay đổi |

### Rebuild tự động

Khi chạy `python main.py` (lệnh `run`):

1. Kiểm tra timestamp `dauthau_data.csv` vs artifact
2. Nếu CSV mới hơn → tự động chạy `ingest` + `build-index`
3. Nếu artifact đã sẵn sàng → bỏ qua, mở thẳng UI

---

