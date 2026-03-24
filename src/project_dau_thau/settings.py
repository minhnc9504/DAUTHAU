"""Cấu hình ứng dụng - đọc từ biến môi trường và settings."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass
class AppSettings:
    """Trọng số và cấu hình cho hệ thống gợi ý."""

    raw_csv_path: str = field(default_factory=lambda: _env("DAUTHAU_RAW_CSV_PATH", "data/dauthau_data.csv"))
    curated_dir: str = field(default_factory=lambda: _env("DAUTHAU_CURATED_DIR", "data/curated"))
    artifacts_dir: str = field(default_factory=lambda: _env("DAUTHAU_ARTIFACTS_DIR", "artifacts"))

    semantic_enabled: bool = field(default_factory=lambda: _env_bool("DAUTHAU_SEMANTIC_ENABLED", False))
    semantic_model_name: str = field(default_factory=lambda: _env("DAUTHAU_SEMANTIC_MODEL_NAME", "BAAI/bge-m3"))

    top_k_results: int = field(default_factory=lambda: _env_int("DAUTHAU_TOP_K_RESULTS", 20))
    rerank_top_k: int = field(default_factory=lambda: _env_int("DAUTHAU_RERANK_TOP_K", 50))

    lexical_weight: float = 0.35
    semantic_weight: float = 0.35
    historical_weight: float = 0.15
    price_weight: float = 0.10
    recency_weight: float = 0.05

    @property
    def contractor_history_path(self) -> Path:
        return Path(self.curated_dir) / "contractor_history.parquet"

    @property
    def tender_snapshot_path(self) -> Path:
        return Path(self.curated_dir) / "tender_snapshot.parquet"

    @property
    def company_profiles_path(self) -> Path:
        return Path(self.artifacts_dir) / "company_profiles.parquet"

    @property
    def lexical_index_path(self) -> Path:
        return Path(self.artifacts_dir) / "lexical_index.joblib"

    @property
    def semantic_index_path(self) -> Path:
        return Path(self.artifacts_dir) / "semantic_index.joblib"

    @property
    def hybrid_index_path(self) -> Path:
        """Legacy path - giữ tương thích nếu UI cũ dùng."""
        return Path(self.artifacts_dir) / "hybrid_index.joblib"

    @property
    def metadata_path(self) -> Path:
        return Path(self.artifacts_dir) / "metadata.json"

    def ensure_dirs(self) -> None:
        Path(self.curated_dir).mkdir(parents=True, exist_ok=True)
        Path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)

    def get_normalized_weights(self, semantic_ready: bool) -> dict[str, float]:
        """Trả về trọng số đã chuẩn hóa, loại bỏ semantic nếu chưa sẵn sàng."""
        if semantic_ready:
            return {
                "lexical": self.lexical_weight,
                "semantic": self.semantic_weight,
                "historical": self.historical_weight,
                "price": self.price_weight,
                "recency": self.recency_weight,
            }

        total = (
            self.lexical_weight
            + self.historical_weight
            + self.price_weight
            + self.recency_weight
        )
        if total == 0:
            return {"lexical": 1.0, "historical": 0.0, "price": 0.0, "recency": 0.0}
        return {
            "lexical": self.lexical_weight / total,
            "semantic": 0.0,
            "historical": self.historical_weight / total,
            "price": self.price_weight / total,
            "recency": self.recency_weight / total,
        }


SETTINGS = AppSettings()
