"""Module hybrid - ghép lexical + semantic + profile scoring."""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from settings import AppSettings
from ranking.lexical import LexicalIndexer
from ranking.semantic import SemanticIndexer


SCORE_INV_THRESHOLD = 1.0

# UI display thresholds for _build_why
LEXICAL_VERY_HIGH = 75
LEXICAL_MEDIUM = 40
SEMANTIC_HIGH = 60
RECENCY_VERY_HIGH = 80
RECENCY_MEDIUM = 50


@dataclass
class RankedTender:
    notifyno: str
    bid_name: str
    investor_name: str
    province: str
    field: str
    bid_price: float
    open_date: any
    decision_date: any
    participant_count: int
    winner_names: str
    lexical_score: float
    semantic_score: float
    historical_fit_score: float
    price_fit_score: float
    recency_score: float
    total_score: float
    why_recommended: str


class HybridRanker:
    """Hybrid ranker: lexical + semantic + profile heuristics."""

    def __init__(
        self,
        lexical: LexicalIndexer,
        semantic: SemanticIndexer,
        weights: dict[str, float],
    ):
        self.lexical = lexical
        self.semantic = semantic
        self.weights = weights
        self._semantic_ready = semantic.ready if semantic else False

    @property
    def semantic_ready(self) -> bool:
        return self._semantic_ready

    @classmethod
    def build(
        cls,
        tender_df: pd.DataFrame,
        settings: AppSettings,
    ) -> "HybridRanker":
        print("[Ranker] Bắt đầu build hybrid index...")

        lexical = LexicalIndexer.build(tender_df)
        print(f"  [Ranker] Lexical index: {lexical.matrix.shape}")

        semantic = (
            SemanticIndexer.build(tender_df, settings.semantic_model_name)
            if settings.semantic_enabled
            else SemanticIndexer.build(tender_df, settings.semantic_model_name)
        )
        print(f"  [Ranker] Semantic ready: {semantic.ready}")

        weights = settings.get_normalized_weights(semantic.ready)
        print(f"  [Ranker] Weights: {weights}")

        return cls(lexical, semantic, weights)

    def score(
        self,
        query_text: str,
        candidate_df: pd.DataFrame,
        profile: Optional[dict] = None,
    ) -> list[RankedTender]:
        """
        Score từng candidate tender và trả về danh sách đã xếp hạng.
        """
        tender_ids = candidate_df["bidonotifycontractormnotifyno"].tolist()

        # Lexical scores
        lex_scores = self.lexical.score(query_text)

        # Semantic scores
        sem_scores = self.semantic.score(query_text) if (self.semantic and self.semantic.ready) else {}

        results = []
        for _, row in candidate_df.iterrows():
            nid = row["bidonotifycontractormnotifyno"]

            # Normalize lexical (0-100)
            lex = lex_scores.get(nid, 0.0)
            lex = min(lex * 100.0, 100.0)

            # Normalize semantic (0-100)
            sem = sem_scores.get(nid, 0.0)
            sem = min(sem * 100.0, 100.0)

            # Profile-based scores
            hist_fit = 0.0
            price_fit = 0.0
            why_parts = []

            if profile:
                hist_fit, price_fit, why_parts = self._compute_profile_scores(row, profile)

            # Recency
            rec = self._compute_recency(row)

            # Weighted total
            total = (
                self.weights.get("lexical", 0) * lex
                + self.weights.get("semantic", 0) * sem
                + self.weights.get("historical", 0) * hist_fit
                + self.weights.get("price", 0) * price_fit
                + self.weights.get("recency", 0) * rec
            )

            why = self._build_why(lex, sem, hist_fit, price_fit, rec, why_parts)

            results.append(
                RankedTender(
                    notifyno=nid,
                    bid_name=str(row.get("bidonotifycontractormbidname", "")),
                    investor_name=str(row.get("bidonotifycontractorminvestorname", "")),
                    province=str(row.get("provincename", "")),
                    field=str(row.get("bidonotifycontractorminvestfield", "")),
                    bid_price=float(row.get("bid_price", 0)),
                    open_date=row.get("bidecontractorinputresultdtoopendate"),
                    decision_date=row.get("bidecontractorinputresultdtodecisiondate"),
                    participant_count=int(row.get("participant_count", 1)),
                    winner_names=str(row.get("winner_names", "")),
                    lexical_score=round(lex, 2),
                    semantic_score=round(sem, 2),
                    historical_fit_score=round(hist_fit, 2),
                    price_fit_score=round(price_fit, 2),
                    recency_score=round(rec, 2),
                    total_score=round(total, 2),
                    why_recommended=why,
                )
            )

        results.sort(key=lambda x: x.total_score, reverse=True)
        return results

    def _compute_profile_scores(
        self, tender_row: pd.Series, profile: dict
    ) -> tuple[float, float, list[str]]:
        why_parts = []

        # Historical fit: field + province overlap
        hist = 0.0
        tender_field = str(tender_row.get("bidonotifycontractorminvestfield", "")).strip()
        tender_province = str(tender_row.get("provincename", "")).strip()

        strong_fields = [str(f).strip() for f in profile.get("strong_fields", [])]
        strong_provinces = [str(p).strip() for p in profile.get("strong_provinces", [])]
        familiar_investors = [
            str(i).strip() for i in profile.get("familiar_investors", [])
        ]

        field_match = tender_field in strong_fields
        prov_match = tender_province in strong_provinces

        from settings import SETTINGS

        if field_match:
            hist += field_score
            why_parts.append("Đúng lĩnh vực mạnh")
        if prov_match:
            hist += province_score
            why_parts.append("Đúng địa bàn mạnh")

        investor = str(tender_row.get("bidonotifycontractorminvestorname", "")).strip()
        if investor in familiar_investors:
            hist += investor_score
            why_parts.append("Cùng chủ đầu tư quen")

        # Price fit
        price_fit = 0.0
        tender_price = float(tender_row.get("bid_price", 0))
        p_low = float(profile.get("price_low", 0))
        p_high = float(profile.get("price_high", 0))
        p_median = float(profile.get("median_price", 0))

        if p_low > 0 and p_high > 0:
            if p_low <= tender_price <= p_high:
                price_fit = 100.0
                why_parts.append("Nằm trong khung giá")
            elif tender_price > 0:
                # Partial score
                if tender_price < p_low:
                    price_fit = max(0, 100 - ((p_low - tender_price) / p_low * 100))
                else:
                    price_fit = max(0, 100 - ((tender_price - p_high) / p_high * 100))
                price_fit = min(price_fit, 100.0)

        return min(hist, 100.0), price_fit, why_parts

    def _compute_recency(self, tender_row: pd.Series) -> float:
        """Điểm recency: gói gần deadline được ưu tiên."""
        from settings import SETTINGS
        urgent_days = SETTINGS.recency_urgent_days
        good_days = SETTINGS.recency_good_days
        normal_days = SETTINGS.recency_normal_days

        date = tender_row.get("bidecontractorinputresultdtoopendate")
        if date is None or pd.isna(date):
            date = tender_row.get("bidecontractorinputresultdtodecisiondate")
        if date is None or pd.isna(date):
            return 50.0

        try:
            from datetime import datetime

            now = datetime.now()
            delta = (date - now).days
            if delta < 0:
                return 30.0
            elif delta <= urgent_days:
                return 100.0
            elif delta <= good_days:
                return 80.0
            elif delta <= normal_days:
                return 60.0
            else:
                return 40.0
        except Exception:
            return 50.0

    def _build_why(
        self,
        lex: float,
        sem: float,
        hist: float,
        price: float,
        rec: float,
        extra: list[str],
    ) -> str:
        parts = list(extra)
        if lex > LEXICAL_VERY_HIGH:
            parts.append("Chuyên môn rất sát")
        elif lex > LEXICAL_MEDIUM:
            parts.append("Đúng ngành nghề")
        if sem > SEMANTIC_HIGH:
            parts.append("Ngữ nghĩa trùng khớp cao")
        if rec > RECENCY_VERY_HIGH:
            parts.append("Sắp đóng thầu")
        elif rec > RECENCY_MEDIUM:
            parts.append("Thời gian hợp lý")
        if not parts:
            return "Phù hợp tiêu chuẩn"
        return " | ".join(parts)
