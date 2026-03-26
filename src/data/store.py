"""Module store - query dữ liệu từ curated parquet."""
from datetime import datetime
from pathlib import Path

import pandas as pd


def load_contractor_history(path: str | Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    for col in [
        "bidecontractorinputresultdtoopendate",
        "bidecontractorinputresultdtopublicdate",
        "bidecontractorinputresultdtodecisiondate",
    ]:
        if col in df.columns and df[col].dtype == "object":
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    return df


def load_tender_snapshot(path: str | Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    for col in [
        "bidecontractorinputresultdtoopendate",
        "bidecontractorinputresultdtopublicdate",
        "bidecontractorinputresultdtodecisiondate",
    ]:
        if col in df.columns and df[col].dtype == "object":
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    return df


class TenderStore:
    """Lớp truy vấn dữ liệu gói thầu từ tender_snapshot."""

    def __init__(self, snapshot_path: str | Path):
        self.df = load_tender_snapshot(snapshot_path)
        self._available_provinces: list[str] = sorted(
            self.df["provincename"].dropna().unique()
        )
        self._available_fields: list[str] = sorted(
            self.df["bidonotifycontractorminvestfield"].dropna().unique()
        )

    @property
    def available_provinces(self) -> list[str]:
        return self._available_provinces

    @property
    def available_fields(self) -> list[str]:
        return self._available_fields

    @property
    def all_notifynos(self) -> list[str]:
        return self.df["bidonotifycontractormnotifyno"].tolist()

    def filter_active_tenders(
        self,
        as_of: datetime | None = None,
        provinces: list[str] | None = None,
        fields: list[str] | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        text_filter: str = "",
    ) -> pd.DataFrame:
        """
        Lọc tender đang/còn hiệu lực dựa trên ngày quyết định/mở/công bố.

        Logic: COALESCE(decision_date, open_date, public_date) >= current_time
        """
        if as_of is None:
            as_of = datetime.now()

        df = self.df.copy()

        # Effective date = COALESCE(decision_date, open_date, public_date)
        df["_effective_date"] = df["bidecontractorinputresultdtodecisiondate"].fillna(
            df["bidecontractorinputresultdtoopendate"]
        )
        df["_effective_date"] = df["_effective_date"].fillna(
            df["bidecontractorinputresultdtopublicdate"]
        )

        # Drop rows where effective_date is missing/NaT (stale)
        df = df.dropna(subset=["_effective_date"])
        # Keep only future / current tenders
        df = df[df["_effective_date"] >= as_of]

        if provinces:
            df = df[df["provincename"].isin(provinces)]
        if fields:
            df = df[df["bidonotifycontractorminvestfield"].isin(fields)]
        if price_min is not None:
            df = df[df["bid_price"] >= price_min]
        if price_max is not None:
            df = df[df["bid_price"] <= price_max]
        if text_filter.strip():
            pattern = text_filter.strip().lower()
            mask = (
                df["bidonotifycontractormbidname"].str.lower().str.contains(pattern, na=False)
                | df["tender_text"].str.lower().str.contains(pattern, na=False)
            )
            df = df[mask]

        return df.drop(columns=["_effective_date"])

    def get_tender_by_notifyno(self, notifyno: str) -> pd.Series | None:
        rows = self.df[self.df["bidonotifycontractormnotifyno"] == notifyno]
        if rows.empty:
            return None
        return rows.iloc[0]


class ContractorStore:
    """Lớp truy vấn dữ liệu bidder từ contractor_history."""

    def __init__(self, history_path: str | Path):
        self.df = load_contractor_history(history_path)
        self._available_companies: list[str] = sorted(
            self.df["orgfullname"].dropna().unique()
        )

    @property
    def available_companies(self) -> list[str]:
        return self._available_companies

    def get_history(self, taxcode: str | None = None, orgfullname: str | None = None) -> pd.DataFrame:
        if taxcode:
            return self.df[self.df["taxcode"] == taxcode].copy()
        if orgfullname:
            return self.df[self.df["orgfullname"] == orgfullname].copy()
        return pd.DataFrame()

    def get_company_taxcode(self, orgfullname: str) -> str | None:
        rows = self.df[self.df["orgfullname"] == orgfullname]
        if rows.empty:
            return None
        return rows["taxcode"].iloc[0]

    def get_company_stats(self, orgfullname: str) -> dict:
        hist = self.get_history(orgfullname=orgfullname)
        if hist.empty:
            return {}
        total = len(hist)
        won = int(hist["is_winner"].sum())
        return {
            "participated_count": total,
            "won_count": won,
            "win_rate": round(won / total * 100, 1) if total > 0 else 0.0,
        }
