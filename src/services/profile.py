"""Module profile - xây dựng hồ sơ doanh nghiệp từ lịch sử đấu thầu."""
from pathlib import Path
from typing import Optional

import pandas as pd


def build_company_profile(history_df: pd.DataFrame, orgfullname: str) -> dict:
    """
    Xây dựng profile tổng hợp cho một doanh nghiệp dựa trên lịch sử tham gia.
    """
    company_df = history_df[history_df["orgfullname"] == orgfullname].copy()

    if company_df.empty:
        return {}

    won_df = company_df[company_df["is_winner"]]
    participated_names = company_df["bidonotifycontractormbidname"].fillna("").tolist()
    won_names = won_df["bidonotifycontractormbidname"].fillna("").tolist()

    seen = set(won_names)
    text_parts = list(won_names) + [n for n in participated_names if n not in seen]
    text_profile = " ".join(text_parts)

    if "bidonotifycontractorminvestfield" in company_df.columns:
        field_won = won_df["bidonotifycontractorminvestfield"].value_counts().head(5).index.tolist()
        field_all = company_df["bidonotifycontractorminvestfield"].value_counts().head(5).index.tolist()
        strong_fields = field_won if field_won else field_all
    else:
        strong_fields = []

    if "provincename" in company_df.columns:
        prov_won = won_df["provincename"].value_counts().head(5).index.tolist()
        prov_all = company_df["provincename"].value_counts().head(5).index.tolist()
        strong_provinces = prov_won if prov_won else prov_all
    else:
        strong_provinces = []

    if "bidonotifycontractorminvestorname" in company_df.columns:
        familiar_investors = (
            company_df["bidonotifycontractorminvestorname"]
            .value_counts().head(5).index.tolist()
        )
    else:
        familiar_investors = []

    prices = company_df["bidecontractorinputresultdtobidprice"].dropna()
    prices = prices[prices > 0]
    if not prices.empty:
        median_price = float(prices.median())
        price_low = float(prices.quantile(0.25))
        price_high = float(prices.quantile(0.75))
    else:
        median_price = price_low = price_high = 0.0

    participated_count = len(company_df)
    won_count = int(company_df["is_winner"].sum())
    win_rate = round(won_count / participated_count * 100, 1) if participated_count > 0 else 0.0

    taxcode = ""
    if "taxcode" in company_df.columns:
        tc = company_df["taxcode"].dropna()
        if not tc.empty:
            taxcode = str(tc.iloc[0])

    return {
        "orgfullname": orgfullname,
        "taxcode": taxcode,
        "text_profile": text_profile,
        "strong_fields": strong_fields,
        "strong_provinces": strong_provinces,
        "familiar_investors": familiar_investors,
        "median_price": median_price,
        "price_low": price_low,
        "price_high": price_high,
        "win_rate": win_rate,
        "participated_count": participated_count,
        "won_count": won_count,
    }


def build_all_profiles(history_df: pd.DataFrame, output_path: str | Path) -> pd.DataFrame:
    """
    Xây dựng profiles cho tất cả doanh nghiệp dùng groupby vectorized (nhanh).
    """
    print("  [Profile] Đang groupby dữ liệu...", flush=True)

    # Basic stats per company
    grp = history_df.groupby("orgfullname", sort=False)

    # Counts
    stats = grp.agg(
        participated_count=("is_winner", "count"),
        won_count=("is_winner", "sum"),
        price_median=("bidecontractorinputresultdtobidprice", "median"),
        price_low=("bidecontractorinputresultdtobidprice", lambda x: x.dropna()[x.dropna() > 0].quantile(0.25) if (x.dropna() > 0).any() else 0),
        price_high=("bidecontractorinputresultdtobidprice", lambda x: x.dropna()[x.dropna() > 0].quantile(0.75) if (x.dropna() > 0).any() else 0),
    ).reset_index()

    # ── Gộp tất cả groupby.apply() thành 1 lần duy nhất ──
    print("  [Profile] Đang xây dựng text profile + metadata (gộp 1 pass)...", flush=True)

    def _profile_one_group(g):
        names = g["bidonotifycontractormbidname"].fillna("").astype(str).tolist()
        winners_mask = g["is_winner"].values
        won_names = [n for n, w in zip(names, winners_mask) if w]
        seen = set(won_names)
        all_names = [n for n in names if n]
        deduped = list(dict.fromkeys(won_names + [n for n in all_names if n not in seen]))
        text = " ".join(deduped)

        taxcode = next(
            (str(v) for v in g["taxcode"].dropna() if str(v).strip()),
            "",
        )
        strong_fields = (
            g["bidonotifycontractorminvestfield"].value_counts().head(5).index.tolist()
        )
        strong_provinces = (
            g["provincename"].value_counts().head(5).index.tolist()
        )
        familiar_investors = (
            g["bidonotifycontractorminvestorname"].value_counts().head(5).index.tolist()
        )
        return pd.Series({
            "taxcode": taxcode,
            "text_profile": text,
            "strong_fields": strong_fields,
            "strong_provinces": strong_provinces,
            "familiar_investors": familiar_investors,
        })

    extra = grp.apply(_profile_one_group, include_groups=False).reset_index(drop=True)
    stats = pd.concat([stats, extra], axis=1)

    # Win rate
    stats["win_rate"] = (
        stats["won_count"] / stats["participated_count"] * 100
    ).round(1).fillna(0.0)

    # Fill 0 for missing prices
    stats["price_median"] = stats["price_median"].fillna(0.0)
    stats["price_low"] = stats["price_low"].fillna(0.0)
    stats["price_high"] = stats["price_high"].fillna(0.0)

    # Rename columns
    stats = stats.rename(columns={
        "price_median": "median_price",
    })

    # Ensure correct column order
    cols = [
        "orgfullname", "taxcode", "text_profile",
        "strong_fields", "strong_provinces", "familiar_investors",
        "median_price", "price_low", "price_high",
        "win_rate", "participated_count", "won_count",
    ]
    stats = stats[[c for c in cols if c in stats.columns]]

    import os
    os.makedirs(os.path.dirname(str(output_path)) or ".", exist_ok=True)
    stats.to_parquet(str(output_path), compression="snappy", index=False)
    print(f"  [Profile] Đã lưu {len(stats)} profiles -> {output_path}", flush=True)
    return stats


def load_profiles(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def get_profile(profiles_df: pd.DataFrame, orgfullname: str) -> Optional[dict]:
    rows = profiles_df[profiles_df["orgfullname"] == orgfullname]
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()
