import pandas as pd
import pickle
import os
from sklearn.feature_extraction.text import TfidfVectorizer

def train():
    parquet_path = 'data/dauthau_data.parquet'
    model_dir = 'models'
    
    # Tự động tạo thư mục models nếu chưa có
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)

    if not os.path.exists(parquet_path):
        print("❌ Chưa có dữ liệu Parquet. Vui lòng chạy convert_data.py trước.")
        return

    print("🧠 AI đang học dữ liệu mới (Huấn luyện lại)...")
    df = pd.read_parquet(parquet_path)
    
    # Lấy tên gói thầu, làm sạch và chuyển về chữ thường
    data_text = df['bidonotifycontractormbidname'].fillna('').astype(str).str.lower()
    
    tfidf = TfidfVectorizer(ngram_range=(1, 2))
    tfidf_matrix = tfidf.fit_transform(data_text)
    
    # Lưu mô hình vào thư mục models
    with open(os.path.join(model_dir, 'tfidf_model.pkl'), 'wb') as f:
        pickle.dump(tfidf, f)
    with open(os.path.join(model_dir, 'tfidf_matrix.pkl'), 'wb') as f:
        pickle.dump(tfidf_matrix, f)
        
    print("✅ Model đã được huấn luyện thành công và lưu vào thư mục 'models'!")

if __name__ == "__main__":
    train()