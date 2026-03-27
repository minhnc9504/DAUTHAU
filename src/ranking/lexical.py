"""Module lexical - TF-IDF vectorizer cho retrieval."""
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


class LexicalIndexer:
    """TF-IDF lexical retrieval."""

    def __init__(self, vectorizer: TfidfVectorizer, matrix, tender_ids: list[str]):
        self.vectorizer = vectorizer
        self.matrix = matrix
        self.tender_ids = tender_ids

    @classmethod
    def build(cls, tender_df: pd.DataFrame) -> "LexicalIndexer":
        texts = tender_df["tender_text_ascii"].fillna("").tolist()
        tender_ids = tender_df["bidonotifycontractormnotifyno"].tolist()

        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.95, max_features=25000, sublinear_tf=True)
        # ngram_range=(1, 2),    # Học cả từ đơn ("máy") và cụm từ ("máy tính")
        # min_df=2,              # Từ nào chỉ xuất hiện đúng 1 lần trong cả nghìn gói thầu -> Loại (tránh nhiễu)
        # max_df=0.95,           # Từ nào xuất hiện ở >95% gói thầu (như "thầu", "công ty") -> Loại (vì không giúp phân loại)
        # max_features=25000,    # Chỉ giữ lại 25.000 từ quan trọng nhất để ma trận không quá nặng
        # sublinear_tf=True      # Dùng log(TF) để kìm hãm các gói thầu lặp từ khóa quá nhiều lần
        matrix = vectorizer.fit_transform(texts) # Thực thi tính toán: Biến văn bản thành ma trận điểm số

        return cls(vectorizer, matrix, tender_ids)
          

    def score(self, query: str) -> dict[str, float]:
        """Tính lexical similarity score cho query."""
        # 1. Chuyển câu tìm kiếm của người dùng thành vector số (dựa trên từ điển đã học)
        q_vec = self.vectorizer.transform([query.lower()])
        # 2. Phép nhân ma trận (CỰC KỲ NHANH)
        # q_vec (1 x 25000) nhân với matrix chuyển vị (25000 x N gói thầu)
        # Kết quả trả về một mảng chứa điểm tương đồng của query với TẤT CẢ gói thầu
        scores = (q_vec @ self.matrix.T).toarray().flatten()
        # 3. Kiểm tra rỗng để tránh lỗi
        if self.matrix.shape[0] == 0:
            return {}
        # 4. Gom kết quả: Ghép cặp [Mã gói thầu] : [Điểm số]
        score_map = {}
        for i, tid in enumerate(self.tender_ids):
            score_map[tid] = float(scores[i])
        return score_map
    # Dùng joblib để nén 3 thành phần cốt lõi vào 1 file duy nhất, dễ dàng lưu trữ và tải lại sau này.
    def save(self, path: str | Path) -> None:
        joblib.dump(
            {
                "vectorizer": self.vectorizer,
                "matrix": self.matrix,
                "tender_ids": self.tender_ids,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "LexicalIndexer":
        data = joblib.load(path)
        return cls(
            vectorizer=data["vectorizer"],
            matrix=data["matrix"],
            tender_ids=data["tender_ids"],
        )
