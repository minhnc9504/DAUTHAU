# GIẢI THÍCH CODE & THUẬT TOÁN
## Hệ thống Gợi ý Gói Thầu VietinBank

> Tài liệu giải thích chi tiết code, thuật toán, và công thức tính toán.
> Phiên bản: v2.0 | Ngày: 24/03/2026

---

## MỤC LỤC

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Luồng dữ liệu tổng thể](#2-luồng-dữ-liệu-tổng-thể)
3. [Thuật toán TF-IDF](#3-thuật-toán-tf-idf)
4. [Thuật toán Cosine Similarity](#4-thuật-toán-cosine-similarity)
5. [Thuật toán Semantic (Sentence-BERT)](#5-thuật-toán-semantic-sentence-bert)
6. [Thuật toán Hybrid Scoring](#6-thuật-toán-hybrid-scoring)
7. [Thuật toán Killer Score (Phân tích đối thủ)](#7-thuật-toán-killer-score-phân-tích-đối-thủ)
8. [Thuật toán Profile Builder](#8-thuật-toán-profile-builder)
9. [Các hàm xử lý dữ liệu](#9-các-hàm-xử-lý-dữ-liệu)
10. [Pipeline điều phối (main.py)](#10-pipeline-điều-phối-mainpy)

---

## 1. Tổng quan kiến trúc

### 1.1 Hai phiên bản song song

Dự án có **2 phiên bản** chạy song song:

| Phiên bản | File chính | Đặc điểm |
|-----------|-----------|-----------|
| **v1 (Legacy)** | `app.py` | Đơn giản, dùng TF-IDF cơ bản, hybrid score đơn giản |
| **v2 (Mới)** | `src/project_dau_thau/ui/streamlit_app.py` | Module hóa, hỗ trợ semantic, nhiều trọng số |

### 1.2 Kiến trúc module v2

```
main.py (Orchestrator)
│
├── ingest ──► src/project_dau_thau/data/ingest.py
│                  ├── _detect_encoding()     # Tự động nhận diện encoding
│                  └── ingest()               # CSV → curated parquet
│
├── build-index ──► ranking/lexical.py
│                      ├── TfidfVectorizer    # TF-IDF index
│                      └── LexicalIndexer      # Tra cứu lexical
│
│                  ranking/semantic.py
│                      ├── SentenceTransformer # BAAI/bge-m3
│                      └── SemanticIndexer     # Semantic embedding
│
│                  services/profile.py
│                      ├── build_company_profile()  # Profile 1 doanh nghiệp
│                      └── build_all_profiles()    # Profile tất cả
│
│                  ranking/hybrid.py
│                      ├── HybridRanker        # Ghép điểm tổng hợp
│                      └── RankedTender        # Kết quả xếp hạng
│
└── serve ──► src/project_dau_thau/ui/streamlit_app.py
```

---

## 2. Luồng dữ liệu tổng thể

### 2.1 Từ CSV thô đến Parquet (Ingest Pipeline)

**File:** `src/project_dau_thau/data/ingest.py`

```
CSV (dauthau_data.csv)
    │
    ├── _detect_encoding()
    │      Thử lần lượt: utf-8-sig → utf-8 → cp1258 → latin-1
    │      → Chọn encoding đầu tiên đọc được
    │
    ├── pd.read_csv(encoding=enc)
    │
    ├── clean_columns()
    │      • Bỏ cột NaN hoàn toàn
    │      • Điền giá trị mặc định cho thiếu
    │      • Chuẩn hóa kiểu dữ liệu
    │
    ├── Split thành 2 bảng:
    │      ├── contractor_history.parquet  (lịch sử nhà thầu)
    │      │      Mỗi dòng = 1 lần tham gia đấu thầu
    │      │      Có cờ is_winner (True/False)
    │      │
    │      └── tender_snapshot.parquet     (ảnh chụp các gói thầu)
    │             Mỗi dòng = 1 gói thầu
    │             Có tender_text = bidname + projectname (ASCII)
```

### 2.2 Từ Parquet đến Model (Build Index Pipeline)

```
tender_snapshot.parquet
    │
    ├── LexicalIndexer.build()
    │      TfidfVectorizer.fit_transform(tender_text_ascii)
    │      → Lưu: lexical_index.joblib
    │
    ├── SemanticIndexer.build() (nếu có model)
    │      SentenceTransformer.encode(tender_text)
    │      → Lưu: semantic_index.joblib
    │
    └── company_profiles.parquet
           build_all_profiles(contractor_history)
           → Mỗi doanh nghiệp: strong_fields, strong_provinces,
             familiar_investors, price_range, win_rate
```

---

## 3. Thuật toán TF-IDF

### 3.1 Công thức toán học

TF-IDF gán trọng số cho mỗi từ trong tài liệu:

```
TF-IDF(t, d) = TF(t, d) × IDF(t)

Trong đó:
  • TF(t, d) = Số lần từ t xuất hiện trong tài liệu d
  • IDF(t)   = log(N / df(t))
  • N        = Tổng số tài liệu trong corpus
  • df(t)    = Số tài liệu chứa từ t
```

### 3.2 Ý nghĩa

- **TF cao**: Từ xuất hiện nhiều trong tài liệu → quan trọng với tài liệu đó
- **IDF cao**: Từ hiếm trong corpus → mang nhiều ý nghĩa phân biệt
- **TF-IDF cao**: Từ vừa xuất hiện nhiều trong tài liệu, vừa hiếm trong corpus → keyword tốt

### 3.3 Cài đặt trong code

```python
# File: src/project_dau_thau/ranking/lexical.py (dòng 22)
vectorizer = TfidfVectorizer(
    ngram_range=(1, 2),   # Unigrams + Bigrams
    min_df=2,             # Bỏ từ xuất hiện < 2 tài liệu
    max_df=0.95           # Bỏ từ xuất hiện > 95% tài liệu (quá phổ biến)
)
```

**Giải thích tham số:**

| Tham số | Giá trị | Tại sao |
|---------|---------|---------|
| `ngram_range=(1,2)` | Unigram + Bigram | "xây lắp" (unigram) và "xây lắp công trình" (bigram) đều quan trọng |
| `min_df=2` | Bỏ từ quá hiếm | Từ xuất hiện 1 lần không đáng tin cậy |
| `max_df=0.95` | Bỏ từ quá phổ biến | Loại bỏ stopwords tự động (VD: "và", "của") |

### 3.4 Minh họa

```
Tài liệu 1: "Mua sắm thiết bị văn phòng"
Tài liệu 2: "Thiết bị y tế nhập khẩu"
Tài liệu 3: "Vật tư xây dựng"

Query: "thiết bị"

TF-IDF("thiết bị", Doc1) = TF(1, Doc1) × log(3/2) = 1 × 0.176 = 0.176
TF-IDF("thiết bị", Doc2) = TF(1, Doc2) × log(3/2) = 1 × 0.176 = 0.176
TF-IDF("thiết bị", Doc3) = TF(0, Doc3) × log(3/1) = 0 × 0.477 = 0
```

---

## 4. Thuật toán Cosine Similarity

### 4.1 Công thức toán học

Cosine Similarity đo góc giữa 2 vector trong không gian nhiều chiều:

```
Cosine(A, B) = (A · B) / (||A|| × ||B||)
             = Σ(Aᵢ × Bᵢ) / (√ΣAᵢ² × √ΣBᵢ²)

Trong đó:
  • A · B     = Dot product (tích vô hướng)
  • ||A||     = L2 norm của vector A
```

### 4.2 Ý nghĩa hình học

```
Vector A = [0.5, 0.3, 0.8]   (Query)
Vector B = [0.4, 0.2, 0.9]   (Document)

Cosine(A, B) gần 1 → Hai vector cùng hướng → Similar
Cosine(A, B) = 0    → Hai vector vuông góc → Không liên quan
Cosine(A, B) < 0    → Hai vector ngược hướng → Trái nghĩa
```

### 4.3 Cài đặt trong code

```python
# File: src/project_dau_thau/ranking/lexical.py (dòng 27-37)
def score(self, query: str) -> dict[str, float]:
    # Bước 1: Chuyển query thành vector TF-IDF
    q_vec = self.vectorizer.transform([query.lower()])
    
    # Bước 2: Tính cosine similarity hàng loạt
    # q_vec shape: (1, vocab_size)
    # self.matrix.T shape: (vocab_size, n_docs)
    # Result shape: (1, n_docs)
    scores = (q_vec @ self.matrix.T).toarray().flatten()
    
    # Bước 3: Map về dict {tender_id: score}
    score_map = {}
    for i, tid in enumerate(self.tender_ids):
        score_map[tid] = float(scores[i])
    return score_map
```

**Tại sao dùng matrix multiplication?**

```
Thay vì tính từng cặp:
  for query in queries:
      for doc in documents:
          similarity = cosine(query, doc)  # O(n×m) lần

Dùng ma trận:
  similarities = Q @ D.T                      # O(1) phép nhân ma trận
  → Hiệu năng nhanh gấp 100-1000 lần với 16,000+ tài liệu
```

---

## 5. Thuật toán Semantic (Sentence-BERT)

### 5.1 Khác biệt với TF-IDF

| TF-IDF | Semantic (SBERT) |
|--------|-----------------|
| Đếm từ (bag-of-words) | Hiểu ý nghĩa ngữ cảnh |
| "xe hơi" ≠ "ô tô" | "xe hơi" ≈ "ô tô" (rất gần) |
| Nhanh, không cần GPU | Chậm hơn, cần GPU (hoặc CPU) |
| Không cần pretrained model | Cần model đã huấn luyện |

### 5.2 Công thức

Sentence-BERT encode văn bản thành vector 1024 chiều (với BAAI/bge-m3):

```
embedding = model.encode(text)
# Output: vector normalized có độ dài = 1 (L2 normalized)

Cosine(emb_query, emb_doc) = emb_query @ emb_doc.T
# Vì đã normalize → Không cần chia cho norm
```

### 5.3 Cài đặt

```python
# File: src/project_dau_thau/ranking/semantic.py (dòng 27-44)
model = SentenceTransformer("BAAI/bge-m3")  # 1024 chiều
embeddings = model.encode(
    texts,                  # Danh sách tender_text
    batch_size=64,          # Xử lý 64 văn bản/lần
    show_progress_bar=True,
    normalize_embeddings=True  # Quan trọng: để cosine = dot product
)
```

### 5.4 So sánh ví dụ

```
Query: "cung cấp vật liệu xây dựng"

TF-IDF scores:
  Doc A: "mua bán vật liệu xây dựng"     → Score: 0.85  ✓
  Doc B: "thiết bị công nghệ cao"         → Score: 0.12  ✗

Semantic scores:
  Doc A: "mua bán vật liệu xây dựng"     → Score: 0.92  ✓✓
  Doc B: "thiết bị công nghệ cao"         → Score: 0.15  ✗
  Doc C: "cung ứng VLXD cho công trình"   → Score: 0.89  ✓✓
```

---

## 6. Thuật toán Hybrid Scoring

### 6.1 Tổng quan

Hybrid Scoring kết hợp nhiều tín hiệu để xếp hạng gói thầu:

```
Total Score = w₁×Lexical + w₂×Semantic + w₃×Historical + w₄×Price + w₅×Recency
```

### 6.2 Trọng số cấu hình

**File:** `src/project_dau_thau/settings.py`

```python
# Khi SEMANTIC DISABLED (mặc định):
lexical_weight      = 0.35
semantic_weight     = 0.35
historical_weight   = 0.15
price_weight        = 0.10
recency_weight      = 0.05

# Hàm normalize loại bỏ semantic (vì không dùng):
get_normalized_weights(semantic_ready=False)
→ Kết quả: lexical=0.54, historical=0.23, price=0.15, recency=0.08

# Khi SEMANTIC ENABLED:
→ Kết quả: lexical=0.35, semantic=0.35, historical=0.15, price=0.10, recency=0.05
```

### 6.3 Chi tiết từng thành phần

#### 6.3.1 Lexical Score (0-100)

```python
# File: src/project_dau_thau/ranking/hybrid.py (dòng 96-98)
lex = lex_scores.get(nid, 0.0)
lex = min(lex * 100.0, 100.0)  # TF-IDF score × 100, max = 100
```

**Input:** Cosine similarity từ TF-IDF vectorizer (0.0 - 1.0)  
**Output:** Score 0-100

#### 6.3.2 Semantic Score (0-100)

```python
# File: src/project_dau_thau/ranking/hybrid.py (dòng 100-102)
sem = sem_scores.get(nid, 0.0)
sem = min(sem * 100.0, 100.0)  # SBERT cosine × 100
```

#### 6.3.3 Historical Fit Score (0-100)

```python
# File: src/project_dau_thau/ranking/hybrid.py (dòng 156-180)
hist = 0.0

# Đúng lĩnh vực mạnh → +50 điểm
if tender_field in strong_fields:
    hist += 50.0

# Đúng địa bàn mạnh → +30 điểm
if tender_province in strong_provinces:
    hist += 30.0

# Cùng chủ đầu tư quen → +20 điểm
if investor in familiar_investors:
    hist += 20.0

hist = min(hist, 100.0)  # Max = 100
```

**Giải thích:**
- Lĩnh vực mạnh: Doanh nghiệp từng THẮNG trong lĩnh vực đó
- Địa bàn mạnh: Tỉnh/thành doanh nghiệp từng thắng
- Chủ đầu tư quen: Đã từng tham gia với CĐT này

#### 6.3.4 Price Fit Score (0-100)

```python
# File: src/project_dau_thau/ranking/hybrid.py (dòng 182-199)
tender_price = tender_row['bid_price']

# Nằm trong khoảng [price_low, price_high] → 100 điểm
if price_low <= tender_price <= price_high:
    price_fit = 100.0
else:
    # Tính điểm partial (càng xa khoảng, điểm càng giảm)
    if tender_price < price_low:
        price_fit = max(0, 100 - (price_low - tender_price) / price_low × 100)
    else:
        price_fit = max(0, 100 - (tender_price - price_high) / price_high × 100)
```

**Ví dụ:**
```
Doanh nghiệp thường tham gia: 1-5 tỷ
Gói thầu A: 3 tỷ      → Price Fit = 100 (trong khoảng)
Gói thầu B: 500 triệu → Price Fit = 50   (thấp hơn)
Gói thầu C: 20 tỷ     → Price Fit = 20   (cao hơn nhiều)
```

#### 6.3.5 Recency Score (0-100)

```python
# File: src/project_dau_thau/ranking/hybrid.py (dòng 203-227)
delta = (date - now).days

if delta < 0:           # Đã đóng thầu rồi
    return 30.0
elif delta <= 7:        # Trong 7 ngày tới
    return 100.0        # Cơ hội vàng!
elif delta <= 30:       # Trong 1 tháng
    return 80.0
elif delta <= 90:       # Trong 3 tháng
    return 60.0
else:                   # > 3 tháng
    return 40.0
```

**Ý nghĩa:** Gói thầu sắp đóng được ưu tiên cao hơn (khẩn cấp hơn).

### 6.4 Tổng hợp điểm

```python
# File: src/project_dau_thau/ranking/hybrid.py (dòng 115-122)
total = (
    weights["lexical"]     × lex +
    weights["semantic"]    × sem +
    weights["historical"]  × hist_fit +
    weights["price"]       × price_fit +
    weights["recency"]     × rec
)
```

**Ví dụ tính toán:**

```
Giả sử (semantic disabled):
  weights = {lexical: 0.54, historical: 0.23, price: 0.15, recency: 0.08}

Một gói thầu có:
  Lexical    = 85.0   (TF-IDF cao - đúng ngành)
  Hist Fit   = 80.0   (đúng lĩnh vực + địa bàn)
  Price Fit  = 100.0  (trong khoảng giá)
  Recency    = 80.0   (sắp đóng trong 30 ngày)

Total = 0.54×85 + 0.23×80 + 0.15×100 + 0.08×80
      = 45.90 + 18.40 + 15.00 + 6.40
      = 85.70
```

### 6.5 So sánh với app.py v1 (Legacy)

| Thành phần | v1 (app.py) | v2 (hybrid.py) |
|------------|-------------|----------------|
| Lexical | TF-IDF × 0.60 | TF-IDF × 0.54 |
| Semantic | Không có | SBERT × 0.35 |
| Historical | Không có | 50+30+20 điểm |
| Price | 100 (hard filter) | Partial score × 0.15 |
| Recency | max(50, 100-2×days) | Phân lớp 100/80/60/40/30 |
| Max score | ~85 | ~100 |

---

## 7. Thuật toán Killer Score (Phân tích đối thủ)

### 7.1 Mục đích

Killer Score đánh giá **mức độ nguy hiểm** của từng đối thủ tiềm năng, dựa trên lịch sử cạnh tranh của họ.

### 7.2 Công thức

```python
# File: app.py (dòng 476-483)

# Điểm cho mỗi chiều:
score_inv   = (win_inv   / join_inv)   × 2.5   # Chủ đầu tư
score_prov  = (win_prov  / join_prov)  × 2.5   # Tỉnh/thành
score_field = (win_field / join_field) × 2.5   # Lĩnh vực
score_seg   = (win_seg   / join_seg)   × 2.5   # Phân khúc giá

# Tổng Killer Score:
killer_score = score_inv + score_prov + score_field + score_seg

# Max = 2.5 × 4 = 10.0 điểm
```

### 7.3 Giải thích từng chiều

| Chiều | Giải thích | Ví dụ |
|-------|-----------|-------|
| **Chủ đầu tư** | Tỷ lệ thắng với CĐT này | Thắng 5/10 gói của CĐT X → Score = 1.25 |
| **Tỉnh/thành** | Tỷ lệ thắng tại tỉnh này | Thắng 8/10 gói tại HCM → Score = 2.0 |
| **Lĩnh vực** | Tỷ lệ thắng trong lĩnh vực | Thắng 3/5 gói Xây lắp → Score = 1.5 |
| **Phân khúc** | Tỷ lệ thắng trong khoảng giá ±50% | Thắng 4/6 gói 1-5 tỷ → Score = 1.67 |

### 7.4 Điều kiện lọc

```python
# File: app.py (dòng 486-489)

# Đối thủ phải tham gia đủ nhiều để đáng tin cậy
res['Tổng tham gia'] = join_inv + join_prov + join_f + join_seg
res = res[res['Tổng tham gia'] >= 2]  # Ít nhất 2 lần tham gia
```

**Ý nghĩa:** Nếu đối thủ chỉ tham gia 1 lần và thắng → Chưa đủ dữ liệu, không đáng lo ngại.

### 7.5 Ví dụ tính toán

```
Công ty ABC:
  • Tham gia với CĐT X: 10 lần, thắng: 6  → score = 1.50
  • Tham gia tại HCM: 8 lần, thắng: 5     → score = 1.56
  • Tham gia lĩnh vực Xây lắp: 12 lần, thắng: 7 → score = 1.46
  • Tham gia phân khúc 1-5 tỷ: 6 lần, thắng: 4  → score = 1.67

Killer Score = 1.50 + 1.56 + 1.46 + 1.67 = 6.19 / 10.0
→ ABC là đối thủ TƯƠNG ĐỐI nguy hiểm
```

---

## 8. Thuật toán Profile Builder

### 8.1 Mục đích

Profile Builder tạo "hồ sơ năng lực" cho mỗi doanh nghiệp dựa trên lịch sử đấu thầu của họ.

### 8.2 Công thức tính Profile

```python
# File: src/project_dau_thau/services/profile.py

# 1. Strong Fields (Lĩnh vực mạnh)
# = Top 5 lĩnh vực THẮNG (ưu tiên), hoặc top 5 tham gia
field_won = won_df['investfield'].value_counts().head(5)
field_all = company_df['investfield'].value_counts().head(5)
strong_fields = field_won if field_won else field_all

# 2. Strong Provinces (Địa bàn mạnh)
prov_won = won_df['province'].value_counts().head(5)
prov_all = company_df['province'].value_counts().head(5)
strong_provinces = prov_won if prov_won else prov_all

# 3. Familiar Investors (Chủ đầu tư quen)
familiar_investors = company_df['investorname'].value_counts().head(5)

# 4. Price Range
median_price = prices.median()
price_low    = prices.quantile(0.25)   # 25th percentile
price_high   = prices.quantile(0.75)   # 75th percentile

# 5. Win Rate
win_rate = won_count / participated_count × 100
```

### 8.3 Ví dụ

```
Doanh nghiệp XYZ:

Lịch sử:
  - Tổng tham gia: 47 gói
  - Tổng thắng: 23 gói
  - Tỷ lệ thắng: 48.9%

Strong Fields (thắng nhiều):
  1. Xây lắp (15 thắng)
  2. Tư vấn (5 thắng)
  3. Hàng hóa (3 thắng)

Strong Provinces:
  1. Hà Nội (12 thắng)
  2. TP HCM (8 thắng)
  3. Đà Nẵng (3 thắng)

Price Range:
  - Median: 3 tỷ
  - Low (25%): 1 tỷ
  - High (75%): 8 tỷ

→ Profile này dùng để tính Historical Fit và Price Fit khi gợi ý
```

---

## 9. Các hàm xử lý dữ liệu

### 9.1 Encoding Detection

```python
# File: src/project_dau_thau/data/ingest.py

def _detect_encoding(csv_path: str) -> str:
    encodings = ['utf-8-sig', 'utf-8', 'cp1258', 'latin-1']
    for enc in encodings:
        try:
            with open(csv_path, encoding=enc) as f:
                f.read(1024)  # Đọc thử 1KB
            return enc
        except UnicodeDecodeError:
            continue
    return 'utf-8'  # Fallback
```

**Tại sao cần nhiều encoding?**
- File CSV từ nhiều nguồn có thể lưu bằng encoding khác nhau
- Vietnamese dùng cp1258 (Windows), utf-8 (Linux/Mac), utf-8-sig (Excel export)

### 9.2 Date Formatting

```python
# File: app.py (dòng 59-63)

def format_date_series(series):
    """Vectorized date formatting - nhanh hơn apply() nhiều lần"""
    return pd.to_datetime(series, dayfirst=True, errors='coerce') \
             .dt.strftime('%d/%m/%Y') \
             .fillna('Chưa cập nhật')
```

**Tại sao dùng `dayfirst=True`?**
- Dữ liệu đấu thầu Việt Nam định dạng ngày là `DD/MM/YYYY`
- Pandas mặc định hiểu MM/DD/YYYY → Cần đảo lại

### 9.3 Currency Formatting

```python
# File: app.py (dòng 52-56)

def format_currency(value):
    try:
        if pd.isna(value) or value == 0: return "0"
        return "{:,.0f}".format(float(value)).replace(",", ".")
    except: return "0"

# Ví dụ:
# 1500000000  → "1.500.000.000"
# 5000000000  → "5.000.000.000"
```

### 9.4 Field Name Cleaning

```python
# File: app.py (dòng 65-75)

def clean_field_name(field):
    mapping = {
        'HH': 'Hàng hóa',
        'HON_HOP': 'Hỗn hợp',
        'PTV': 'Phi tư vấn',
        'TV': 'Tư vấn',
        'XL': 'Xây lắp',
    }
    return mapping.get(str(field).strip(), field)
```

**Tại sao cần mapping?**
- Dữ liệu gốc lưu code (HH, XL, TV), cần chuyển sang tên tiếng Việt

### 9.5 Region Filtering

```python
# File: app.py (dòng 31-41)

MIEN_BAC = ['Hà Nội', 'Hải Phòng', ...]   # 25 tỉnh/thành
MIEN_TRUNG = ['Thanh Hóa', 'Nghệ An', ...] # 20 tỉnh/thành
MIEN_NAM = ['TP Hồ Chí Minh', 'Bình Dương', ...] # 19 tỉnh/thành

# Sử dụng regex pattern để lọc:
if target_location == "Miền Bắc":
    pattern = '|'.join(MIEN_BAC)
    res_df = res_df[res_df['province'].str.contains(pattern, case=False, na=False)]
```

---

## 10. Pipeline điều phối (main.py)

### 10.1 Các lệnh CLI

```bash
python main.py setup        # Cài dependencies
python main.py ingest       # CSV → curated parquet
python main.py build-index  # Build profiles + indexes
python main.py rebuild      # ingest + build-index
python main.py serve        # Mở Streamlit UI
python main.py run          # Auto check + rebuild + serve
python main.py status       # Xem trạng thái
```

### 10.2 Logic tự động rebuild

```python
# File: main.py (dòng 202-230)

def _needs_rebuild(settings):
    # So sánh timestamp:
    # CSV mới hơn curated parquet → Cần ingest lại
    # CSV mới hơn artifacts       → Cần build lại
    
    raw_mtime      = Path(csv).stat().st_mtime
    curated_mtime  = max(contractor_history_mtime, tender_snapshot_mtime)
    artifacts_mtime = hybrid_index_mtime
    
    return raw_mtime > curated_mtime or raw_mtime > artifacts_mtime
```

**Ý nghĩa:** Không rebuild nếu không cần, tiết kiệm thời gian.

### 10.3 Flow của lệnh `run`

```
python main.py run
│
├── _needs_rebuild() → True?
│      │
│      ├── YES:
│      │      1. ingest()         → contractor_history.parquet
│      │                           → tender_snapshot.parquet
│      │      2. build_index()
│      │                           → company_profiles.parquet
│      │                           → lexical_index.joblib
│      │                           → semantic_index.joblib (nếu có)
│      │                           → hybrid_index.joblib
│      │
│      └── NO:
│             "Artifact đã sẵn sàng — bỏ qua đồng bộ CSV và huấn luyện AI."
│
└── serve() → Mở Streamlit UI
```

---

## 11. Cache Strategy

### 11.1 Streamlit Cache

```python
# File: app.py

@st.cache_resource          # Cache vĩnh viễn (không có TTL)
def load_assets():
    # TF-IDF model, matrix
    # → Load 1 lần, dùng mãi mãi trong session

@st.cache_data(ttl=3600)   # Cache 1 giờ
def load_data():
    # Parquet data
    # → Refresh mỗi giờ nếu có dữ liệu mới
```

### 11.2 Tại sao khác nhau?

| Asset | Cache | Lý do |
|-------|-------|-------|
| TF-IDF model (.pkl) | Vĩnh viễn | Không thay đổi trong phiên, load lại tốn thời gian |
| Data (parquet) | 1 giờ | Dữ liệu có thể được cập nhật ngoài ứng dụng |

---

## 12. Performance Optimizations

### 12.1 Vectorized Operations

```python
# ❌ Chậm: Dùng apply() cho từng dòng
hist_raw['Giá Dự Thầu'] = hist_raw['price'].apply(format_currency)

# ✅ Nhanh: Vectorized string formatting
hist_raw['Giá Dự Thầu'] = hist_raw['price'].apply(format_currency)  # Vẫn OK
# Hoặc:
hist_raw['Ngày Mở'] = format_date_series(hist_raw['opendate'])  # Vectorized
```

### 12.2 Sparse Matrix

```python
# TF-IDF matrix là sparse (phần lớn = 0)
# Lưu dạng CSR format → Tiết kiệm RAM 90%+

# Nhân ma trận sparse:
scores = (q_vec @ self.matrix.T).toarray()
# → Chỉ tính phần tử khác 0 → Nhanh
```

### 12.3 GroupBy Aggregation

```python
# ❌ Chậm: Tính từng công ty
for company in companies:
    profile = build_company_profile(history_df, company)

# ✅ Nhanh: Dùng groupby vectorized
stats = history_df.groupby("orgfullname").agg({
    'is_winner': ['count', 'sum'],
    'price': 'median',
})
```

---

## 13. Kết luận

### 13.1 Tóm tắt thuật toán

| Bước | Thuật toán | Input | Output |
|------|-----------|-------|--------|
| 1 | Encoding Detection | CSV bytes | Encoding string |
| 2 | TF-IDF | Văn bản | Ma trận sparse (vocab × docs) |
| 3 | Cosine Similarity | 2 vectors | Score 0-1 |
| 4 | SBERT Embedding | Văn bản | Vector 1024 chiều |
| 5 | Hybrid Scoring | 5 thành phần | Total score 0-100 |
| 6 | Killer Score | Lịch sử đối thủ | Threat level 0-10 |
| 7 | Profile Build | Lịch sử doanh nghiệp | Profile dict |

### 13.2 Điểm mạnh

- **Hybrid approach**: Kết hợp lexical + semantic + heuristic
- **Graceful degradation**: Semantic không có → vẫn chạy lexical
- **Performance**: Vectorized, sparse matrix, caching thông minh
- **Modular**: Tách biệt data, ranking, services, UI

### 13.3 Điểm cần cải thiện

- Chưa có A/B testing để validate trọng số
- Chưa có feedback loop từ người dùng
- Semantic model cần GPU để chạy hiệu quả

---

*Tài liệu được tạo ngày 24/03/2026*
*Author: minhnche180504*
