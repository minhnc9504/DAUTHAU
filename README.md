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

### Yêu cầu hệ thống

- Python 3.8 trở lên
- pip (trình quản lý thư viện Python)

### Các thư viện cần cài đặt

Các thư viện cần thiết để chạy ứng dụng:

| Thư viện | Phiên bản tối thiểu | Mục đích |
|----------|---------------------|----------|
| streamlit | >=1.28.0 | Tạo giao diện web |
| pandas | >=2.0.0 | Xử lý và phân tích dữ liệu |
| scikit-learn | >=1.3.0 | Machine learning (TF-IDF, Cosine Similarity) |
| numpy | >=1.24.0 | Tính toán số học |
| xlsxwriter | >=3.1.0 | Xuất file Excel |

### Các bước cài đặt chi tiết

**Bước 1: Tải xuống mã nguồn**
```bash
git clone <repository-url>
cd <project-folder>
```

**Bước 2: Tạo môi trường ảo (khuyến nghị)**
```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt môi trường ảo
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

**Bước 3: Cài đặt các thư viện từ requirements.txt**
```bash
pip install -r requirements.txt
```

**Bước 4: Cài đặt từng thư viện (thay thế)**
Nếu không dùng requirements.txt, có thể cài đặt từng thư viện:
```bash
pip install streamlit
pip install pandas
pip install scikit-learn
pip install numpy
pip install xlsxwriter
```

## Cách chạy ứng dụng

### Cách 1: Chạy trực tiếp bằng Streamlit
```bash
streamlit run app.py
```

### Cách 2: Chạy bằng file run.py
```bash
python run.py
```

### Cách 3: Chạy bằng file run_fast.bat (Windows)
```bash
run_fast.bat
```

### Sau khi chạy thành công

- Ứng dụng sẽ tự động mở trên trình duyệt tại địa chỉ: `http://localhost:8501`
- Nếu không tự mở, hãy mở trình duyệt và truy cập địa chỉ trên

## Xử lý sự cố

### Lỗi không tìm thấy module
```bash
# Cài đặt lại tất cả thư viện
pip install --upgrade -r requirements.txt
```

### Lỗi xung đột phiên bản
```bash
# Gỡ cài đặt và cài đặt lại
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### Lỗi không tìm thấy file dữ liệu
- Đảm bảo thư mục `data/` chứa file `dauthau_data.csv`
- Đảm bảo thư mục `models/` chứa các file `.pkl`

## Tính năng

- Tìm kiếm gói thầu theo tên/danh mục
- Lọc theo vùng miền (Miền Bắc, Miền Trung, Miền Nam)
- Lọc theo tỉnh/thành phố
- Lọc theo ngày đăng tải
- Gợi ý gói thầu phù hợp với doanh nghiệp dựa trên năng lực
- Xuất kết quả ra file Excel

## Tác giả

Hệ thống được phát triển bởi VietinBank
