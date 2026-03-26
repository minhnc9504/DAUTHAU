"""Module semantic - Sentence transformer encoder."""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


class SemanticIndexer:
    """Sentence-transformer semantic retrieval. Gracefully degrades if model unavailable."""

    _instance: "SemanticIndexer | None" = None

    def __init__(
        self,
        model_name: str,
        embeddings: np.ndarray,
        tender_ids: list[str],
        ready: bool,
    ):
        self.model_name = model_name
        self.embeddings = embeddings
        self.tender_ids = tender_ids
        self.ready = ready

    @classmethod
    def build(cls, tender_df: pd.DataFrame, model_name: str = "BAAI/bge-m3") -> "SemanticIndexer":
        try:
            from sentence_transformers import SentenceTransformer

            texts = tender_df["tender_text"].fillna("").tolist()
            tender_ids = tender_df["bidonotifycontractormnotifyno"].tolist()

            print(f"  [Semantic] Đang tải model: {model_name}")
            model = SentenceTransformer(model_name)
            print(f"  [Semantic] Đang encode {len(texts)} tender...")
            embeddings = model.encode(
                texts,
                batch_size=64,
                show_progress_bar=True,
                normalize_embeddings=True,
            )
            print(f"  [Semantic] Hoàn tất. Shape: {embeddings.shape}")
            return cls(model_name, embeddings, tender_ids, ready=True)
        except ImportError:
            print(
                "  [Semantic] sentence-transformers chưa được cài. "
                "Semantic retrieval sẽ bị tắt."
            )
            return cls(model_name, np.empty((0,)), [], ready=False)

    def score(self, query: str) -> dict[str, float]:
        """Tính cosine similarity score cho query."""
        if not self.ready or self.embeddings.shape[0] == 0:
            return {}

        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name)
            q_emb = model.encode([query], normalize_embeddings=True)
            sims = (q_emb @ self.embeddings.T).flatten()

            score_map = {}
            for i, tid in enumerate(self.tender_ids):
                score_map[tid] = float(sims[i])
            return score_map
        except Exception:
            return {}

    def save(self, path: str | Path) -> None:
        joblib.dump(
            {
                "model_name": self.model_name,
                "embeddings": self.embeddings,
                "tender_ids": self.tender_ids,
                "ready": self.ready,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "SemanticIndexer":
        data = joblib.load(path)
        return cls(
            model_name=data["model_name"],
            embeddings=data["embeddings"],
            tender_ids=data["tender_ids"],
            ready=data.get("ready", False),
        )
