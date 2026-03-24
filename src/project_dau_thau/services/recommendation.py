"""Module recommendation - engine gợi ý gói thầu."""
from typing import Optional

import pandas as pd

from ..data.store import TenderStore
from ..ranking.hybrid import HybridRanker, RankedTender
from .profile import get_profile, load_profiles


class RecommendationEngine:
    """Engine gợi ý gói thầu phù hợp cho doanh nghiệp."""

    def __init__(
        self,
        tender_store: TenderStore,
        ranker: HybridRanker,
        profiles_path: Optional[str] = None,
    ):
        self.tender_store = tender_store
        self.ranker = ranker
        self._profiles_df = None
        if profiles_path:
            try:
                self._profiles_df = load_profiles(profiles_path)
            except Exception:
                pass

    def recommend(
        self,
        query_text: str,
        orgfullname: Optional[str] = None,
        top_k: int = 20,
        provinces: list[str] | None = None,
        fields: list[str] | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
    ) -> list[RankedTender]:
        """
        Gợi ý top-K gói thầu phù hợp.

        Args:
            query_text: text để retrieval (từ profile hoặc user input)
            orgfullname: tên doanh nghiệp (nếu đã có lịch sử)
            top_k: số lượng kết quả trả về
            provinces, fields, price_min, price_max: bộ lọc
        """
        # Lấy profile nếu có
        profile = None
        if orgfullname and self._profiles_df is not None:
            profile = get_profile(self._profiles_df, orgfullname)
            if profile and not query_text:
                query_text = profile.get("text_profile", "")

        # Lấy candidate từ tender store
        candidates = self.tender_store.filter_active_tenders(
            provinces=provinces,
            fields=fields,
            price_min=price_min,
            price_max=price_max,
        )

        if candidates.empty:
            return []

        # Score và rank
        ranked = self.ranker.score(query_text, candidates, profile=profile)
        return ranked[:top_k]

    def get_company_profile_text(
        self, orgfullname: Optional[str] = None
    ) -> Optional[dict]:
        if not orgfullname or self._profiles_df is None:
            return None
        return get_profile(self._profiles_df, orgfullname)
