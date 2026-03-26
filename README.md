# Hệ thống Gợi ý gói thầu VietinBank v2.0

Hệ thống gợi ý gói thầu offline chạy trên Streamlit, sử dụng dữ liệu lịch sử đấu thầu nội bộ để gợi ý gói thầu phù hợp và phân tích đối thủ cho doanh nghiệp.

## Tính năng chính

- **Hồ sơ doanh nghiệp** — Dashboard lịch sử đấu thầu, tỉ lệ trúng, lĩnh vực/địa bàn mạnh. Từ đây bấm "Gợi ý gói thầu" để nhảy sang tab gợi ý với tên doanh nghiệp đã chọn.
- **Gợi ý gói thầu** — Hybrid scoring: lexical + historical fit + price fit + recency. Mỗi gói đề xuất đi kèm phân tích đối thủ ngay bên dưới.
- **Sức khỏe dữ liệu** — Trạng thái artifact, metadata, trọng số scoring.

## Cài đặt

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Các lệnh

| Lệnh | Mô tả |
|------|--------|
| `python main.py` | Auto ingest + build + mở UI |
| `python main.py setup` | Cài dependencies |
| `python main.py ingest` | CSV → curated parquet |
| `python main.py build-index` | Build profiles + TF-IDF index |
| `python main.py rebuild` | Ingest + build toàn bộ |
| `python main.py serve` | Chỉ mở UI (đã có artifact) |
| `python main.py run` | Auto check + rebuild nếu cần + mở UI |
| `python main.py status` | Trạng thái artifact |

## Cấu trúc source code

```
src/project_dau_thau/
├── settings.py            # Cấu hình, trọng số, paths
├── data/
│   ├── ingest.py        # CSV → curated parquet
│   └── store.py         # TenderStore + ContractorStore
├── ranking/
│   ├── lexical.py       # TF-IDF vectorizer
│   ├── semantic.py      # Sentence-transformer (optional)
│   └── hybrid.py        # Hybrid ranker
├── services/
│   ├── profile.py       # Company profiles
│   ├── recommendation.py # Recommendation engine
│   └── competitor.py    # Competitor analysis
└── ui/
    └── streamlit_app.py  # Streamlit UI
```

## Artifact

| File | Ý nghĩa |
|------|---------|
| `data/curated/contractor_history.parquet` | Dữ liệu bidder-level đã chuẩn hóa |
| `data/curated/tender_snapshot.parquet` | Dữ liệu tender-level (mỗi gói 1 dòng) |
| `artifacts/company_profiles.parquet` | Profile tổng hợp từng doanh nghiệp |
| `artifacts/hybrid_index.joblib` | TF-IDF matrix |
| `artifacts/metadata.json` | Thông tin audit |

## Trọng số scoring (mặc định)

| Thành phần | Trọng số |
|------------|-----------|
| Lexical (TF-IDF) | 54% |
| Historical fit | 23% |
| Price fit | 15% |
| Recency | 8% |

Khi bật semantic (cài `sentence-transformers`): lexical + semantic mỗi thành phần chiếm 35%.

## Cấu hình `.env`

```env
DAUTHAU_RAW_CSV_PATH=data/dauthau_data.csv
DAUTHAU_CURATED_DIR=data/curated
DAUTHAU_ARTIFACTS_DIR=artifacts
DAUTHAU_SEMANTIC_ENABLED=false
DAUTHAU_SEMANTIC_MODEL_NAME=BAAI/bge-m3
DAUTHAU_TOP_K_RESULTS=20

# Trọng số scoring
DAUTHAU_LEXICAL_WEIGHT=0.35
DAUTHAU_SEMANTIC_WEIGHT=0.35
DAUTHAU_HISTORICAL_WEIGHT=0.15
DAUTHAU_PRICE_WEIGHT=0.10
DAUTHAU_RECENCY_WEIGHT=0.05

# Tiêu đề ứng dụng
DAUTHAU_APP_TITLE=Hệ thống Gợi ý gói thầu phù hợp cho Doanh nghiệp
```

## Tham số cấu hình (trong settings.py)

| Tham số | Mặc định | Ý nghĩa |
|---------|-----------|---------|
| `recency_urgent_days` | 7 | Số ngày để coi là khẩn cấp |
| `recency_good_days` | 30 | Số ngày để coi là hợp lý |
| `recency_normal_days` | 90 | Số ngày để coi là bình thường |
| `historical_field_score` | 50 | Điểm khi trùng lĩnh vực mạnh |
| `historical_province_score` | 30 | Điểm khi trùng địa bàn mạnh |
| `historical_investor_score` | 20 | Điểm khi trùng chủ đầu tư quen |
| `competitor_rate_multiplier` | 2.5 | Hệ số nhân cho tính điểm đối thủ |
| `competitor_min_join` | 2 | Số lần tham gia tối thiểu để xem là đối thủ |
