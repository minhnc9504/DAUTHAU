import pandas as pd
import pickle
import os
from sklearn.feature_extraction.text import TfidfVectorizer

def train():
    parquet_path = 'data/dauthau_data.parquet'
    model_dir = 'models'
    
    # 1. Tự động tạo thư mục models nếu chưa có
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
        print(f"📁 Đã tạo thư mục: {model_dir}")

    # 2. Kiểm tra dữ liệu đầu vào
    if not os.path.exists(parquet_path):
        print("❌ LỖI: Chưa có dữ liệu Parquet. Vui lòng chạy convert_data.py trước.")
        return

    print("🧠 AI đang học dữ liệu mới (Huấn luyện lại)...")
    try:
        df = pd.read_parquet(parquet_path)
        
        # Kiểm tra xem cột có tồn tại không để tránh crash
        if 'bidonotifycontractormbidname' not in df.columns:
            print("❌ LỖI: Không tìm thấy cột 'bidonotifycontractormbidname' trong dữ liệu.")
            return

        # Lấy tên gói thầu, làm sạch
        data_text = df['bidonotifycontractormbidname'].fillna('').astype(str).str.lower()
        
        # 3. Huấn luyện TF-IDF
        tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=2) # Thêm min_df=2 để giảm nhiễu và dung lượng file
        tfidf_matrix = tfidf.fit_transform(data_text)
        
        # 4. Xóa file cũ trước khi lưu mới (Tránh lỗi load key cũ)
        model_path = os.path.join(model_dir, 'tfidf_model.pkl')
        matrix_path = os.path.join(model_dir, 'tfidf_matrix.pkl')
        
        for p in [model_path, matrix_path]:
            if os.path.exists(p):
                os.remove(p)

        # 5. Lưu mô hình (Dùng wb cực kỳ quan trọng)
        with open(model_path, 'wb') as f:
            pickle.dump(tfidf, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(matrix_path, 'wb') as f:
            pickle.dump(tfidf_matrix, f, protocol=pickle.HIGHEST_PROTOCOL)
            
        print(f"✅ Thành công! Kích thước Matrix: {tfidf_matrix.shape}")
        print(f"💾 File đã lưu tại: {model_dir}")

    except Exception as e:
        print(f"❌ Lỗi trong quá trình huấn luyện: {e}")

if __name__ == "__main__":
    train()