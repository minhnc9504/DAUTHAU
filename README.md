# Hệ thống Gợi ý gói thầu phù hợp cho Doanh nghiệp

Hệ thống gợi ý gói thầu phù hợp cho doanh nghiệp sử dụng thuật toán TF-IDF và Cosine Similarity để tìm kiếm các gói thầu phù hợp nhất với năng lực của doanh nghiệp.

## Công nghệ sử dụng

- **Streamlit**: Framework tạo giao diện web
- **Pandas**: Xử lý dữ liệu
- **Scikit-learn**: Machine learning (TF-IDF, Cosine Similarity)
- **Xlsxwriter**: Xuất file Excel

## Cấu trúc thư mục

```
├── app.py                 # Ứng dụng Streamlit chính
├── requirements.txt       # Các thư viện cần thiết
├── README.md             # File này
├── data/
│   └── dauthau_data.csv  # Dữ liệu gói thầu
├── models/
│   ├── tfidf_model.pkl   # Model TF-IDF đã train
│   └── tfidf_matrix.pkl  # Ma trận TF-IDF
├── train_model.py        # Script train model
├── convert_data.py       # Script chuyển đổi dữ liệu
└── run.py                # Script chạy ứng dụng
```

## Cách cài đặt

1. Tạo môi trường ảo:
```bash
python -m venv venv
```

2. Kích hoạt môi trường ảo:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. Cài đặt các thư viện:
```bash
pip install -r requirements.txt
```

## Cách chạy

Chạy ứng dụng Streamlit:
```bash
streamlit run app.py
```

Hoặc chạy file run.py:
```bash
python run.py
```

## Tính năng

- Tìm kiếm gói thầu theo tên/danh mục
- Lọc theo vùng miền (Miền Bắc, Miền Trung, Miền Nam)
- Lọc theo tỉnh/thành phố
- Lọc theo ngày đăng tải
- Gợi ý gói thầu phù hợp với doanh nghiệp dựa trên năng lực
- Xuất kết quả ra file Excel

## Tác giả

Hệ thống được phát triển bởi VietinBank
