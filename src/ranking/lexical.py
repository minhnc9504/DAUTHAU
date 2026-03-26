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
        matrix = vectorizer.fit_transform(texts)

        return cls(vectorizer, matrix, tender_ids)

    def score(self, query: str) -> dict[str, float]:
        """Tính lexical similarity score cho query."""
        q_vec = self.vectorizer.transform([query.lower()])
        scores = (q_vec @ self.matrix.T).toarray().flatten()
        if self.matrix.shape[0] == 0:
            return {}

        score_map = {}
        for i, tid in enumerate(self.tender_ids):
            score_map[tid] = float(scores[i])
        return score_map

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
