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
    semantic_model_name: str = field(default_factory=lambda: _env("DAUTHAU_SEMANTIC_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2"))

    top_k_results: int = field(default_factory=lambda: _env_int("DAUTHAU_TOP_K_RESULTS", 20))
    rerank_top_k: int = field(default_factory=lambda: _env_int("DAUTHAU_RERANK_TOP_K", 50))

    lexical_weight: float = field(default_factory=lambda: _env_float("DAUTHAU_LEXICAL_WEIGHT", 0.35))
    semantic_weight: float = field(default_factory=lambda: _env_float("DAUTHAU_SEMANTIC_WEIGHT", 0.35))
    historical_weight: float = field(default_factory=lambda: _env_float("DAUTHAU_HISTORICAL_WEIGHT", 0.15))
    price_weight: float = field(default_factory=lambda: _env_float("DAUTHAU_PRICE_WEIGHT", 0.10))
    recency_weight: float = field(default_factory=lambda: _env_float("DAUTHAU_RECENCY_WEIGHT", 0.05))

    app_title: str = field(default_factory=lambda: _env("DAUTHAU_APP_TITLE", "Hệ thống Gợi ý gói thầu phù hợp cho Doanh nghiệp"))

    price_map: dict = field(default_factory=lambda: {
        "0": 0, "1 Tỷ": 1e9, "5 Tỷ": 5e9, "10 Tỷ": 10e9,
        "30 Tỷ": 30e9, "50 Tỷ": 50e9, "100 Tỷ": 100e9, "200 Tỷ": 200e9,
        "300 Tỷ": 300e9, "400 Tỷ": 400e9, "500 Tỷ": 500e9,
        "600 Tỷ": 600e9, "700 Tỷ": 700e9, "800 Tỷ": 800e9, "900 Tỷ": 900e9,
        "1000 Tỷ": 1e12, "Trên 1000 Tỷ": 1e15,
    })

    recency_urgent_days: int = 7
    recency_good_days: int = 30
    recency_normal_days: int = 90

    historical_field_score: int = 50
    historical_province_score: int = 30
    historical_investor_score: int = 20

    competitor_rate_multiplier: float = 2.5
    competitor_min_join: int = 2

    mien_bac: list = field(default_factory=lambda: [
        "Hà Nội", "Hải Phòng", "Hà Giang", "Cao Bằng", "Bắc Kạn", "Tuyên Quang",
        "Lào Cai", "Yên Bái", "Thái Nguyên", "Lạng Sơn", "Quảng Ninh", "Bắc Giang",
        "Phú Thọ", "Vĩnh Phúc", "Bắc Ninh", "Hải Dương", "Hưng Yên", "Thái Bình",
        "Hà Nam", "Nam Định", "Ninh Bình", "Điện Biên", "Lai Châu", "Sơn La", "Hòa Bình",
    ])
    mien_trung: list = field(default_factory=lambda: [
        "Thanh Hóa", "Nghệ An", "Hà Tĩnh", "Quảng Bình", "Quảng Trị", "Thừa Thiên Huế",
        "Đà Nẵng", "Quảng Nam", "Quảng Ngãi", "Bình Định", "Phú Yên", "Khánh Hòa",
        "Ninh Thuận", "Bình Thuận", "Kon Tum", "Gia Lai", "Đắk Lắk", "Đắk Nông", "Lâm Đồng",
    ])
    mien_nam: list = field(default_factory=lambda: [
        "TP Hồ Chí Minh", "Bình Dương", "Đồng Nai", "Bà Rịa - Vũng Tàu", "Bình Phước",
        "Tây Ninh", "Long An", "Tiền Giang", "Bến Tre", "Trà Vinh", "Vĩnh Long",
        "Đồng Tháp", "An Giang", "Kiên Giang", "Cần Thơ", "Hậu Giang", "Sóc Trăng",
        "Bạc Liêu", "Cà Mau",
    ])

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
