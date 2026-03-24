"""Module competitor - phân tích đối thủ cạnh tranh trên từng gói thầu."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data.store import ContractorStore


@dataclass
class CompetitorInfo:
    taxcode: str
    orgfullname: str
    join_investor: int
    win_investor: int
    join_province: int
    win_province: int
    join_field: int
    win_field: int
    join_segment: int
    win_segment: int
    score_investor: float
    score_province: float
    score_field: float
    score_segment: float
    total_score: float
    avg_won_price: float
    why_strong: str


def analyze_competitors(
    history_df: pd.DataFrame,
    notifyno: str,
    current_taxcode: str = "",
    current_company: str = "",
    price_lower_pct: float = 0.5,
    price_upper_pct: float = 1.5,
) -> list[CompetitorInfo]:
    """
    Phân tích đối thủ mạnh cho một gói thầu cụ thể.

    Args:
        history_df: contractor_history DataFrame
        notifyno: mã gói thầu cần phân tích
        current_taxcode: MST công ty hiện tại (để loại trừ)
        current_company: tên công ty hiện tại (để loại trừ)
        price_lower_pct, price_upper_pct: khoảng giá để xác định cùng phân khúc
    """
    # Lấy thông tin gói thầu
    tender_rows = history_df[
        history_df["bidonotifycontractormnotifyno"] == notifyno
    ]
    if tender_rows.empty:
        return []

    first_row = tender_rows.iloc[0]
    p_investor = str(first_row.get("bidonotifycontractorminvestorname", "")).strip()
    p_field = str(first_row.get("bidonotifycontractorminvestfield", "")).strip()
    p_province = str(first_row.get("provincename", "")).strip()
    p_price = float(first_row.get("bidecontractorinputresultdtobidprice", 0))

    lower_b, upper_b = p_price * price_lower_pct, p_price * price_upper_pct

    # Lọc candidate đối thủ
    mask = (
        (history_df["bidonotifycontractorminvestorname"] == p_investor)
        | (history_df["bidonotifycontractorminvestfield"] == p_field)
        | (history_df["provincename"] == p_province)
    )
    comp_df = history_df[mask].copy()

    # Loại trừ công ty hiện tại
    if current_taxcode:
        comp_df = comp_df[comp_df["taxcode"] != current_taxcode]
    if current_company:
        comp_df = comp_df[comp_df["orgfullname"] != current_company]

    if comp_df.empty:
        return []

    # Tính các chỉ số
    is_won = comp_df["is_winner"]

    comp_df["at_inv"] = comp_df["bidonotifycontractorminvestorname"] == p_investor
    comp_df["at_prov"] = comp_df["provincename"] == p_province
    comp_df["at_field"] = comp_df["bidonotifycontractorminvestfield"] == p_field
    comp_df["at_seg"] = (
        (comp_df["bidecontractorinputresultdtobidprice"] >= lower_b)
        & (comp_df["bidecontractorinputresultdtobidprice"] <= upper_b)
    )

    comp_df["win_inv"] = comp_df["at_inv"] & is_won
    comp_df["win_prov"] = comp_df["at_prov"] & is_won
    comp_df["win_f"] = comp_df["at_field"] & is_won
    comp_df["win_seg"] = comp_df["at_seg"] & is_won
    comp_df["won_price"] = comp_df["bidecontractorinputresultdtobidprice"].where(is_won)

    def safe_rate_col(series_win, series_join) -> pd.Series:
        nums_win = pd.to_numeric(series_win, errors="coerce").fillna(0)
        nums_join = pd.to_numeric(series_join, errors="coerce").replace(0, 1)
        vals = nums_win / nums_join
        return vals.clip(upper=1.0) * 2.5

    res = comp_df.groupby(["taxcode", "orgfullname"]).agg(
        join_inv=("at_inv", "sum"),
        win_inv=("win_inv", "sum"),
        join_prov=("at_prov", "sum"),
        win_prov=("win_prov", "sum"),
        join_f=("at_field", "sum"),
        win_f=("win_f", "sum"),
        join_seg=("at_seg", "sum"),
        win_seg=("win_seg", "sum"),
        avg_won_price=("won_price", "mean"),
    ).reset_index()

    res["score_inv"] = safe_rate_col(res["win_inv"], res["join_inv"])
    res["score_prov"] = safe_rate_col(res["win_prov"], res["join_prov"])
    res["score_f"] = safe_rate_col(res["win_f"], res["join_f"])
    res["score_seg"] = safe_rate_col(res["win_seg"], res["join_seg"])
    res["total_score"] = (
        res["score_inv"]
        + res["score_prov"]
        + res["score_f"]
        + res["score_seg"]
    )

    # Lọc: tổng tham gia >= 2
    res["total_join"] = (
        res["join_inv"] + res["join_prov"] + res["join_f"] + res["join_seg"]
    )
    res = res[res["total_join"] >= 2]

    # Top 10
    top = res.sort_values("total_score", ascending=False).head(10)

    competitors = []
    for _, row in top.iterrows():
        why_parts = []
        if row["score_inv"] > 1.0:
            why_parts.append(f"CĐT mạnh ({int(row['win_inv'])}/{int(row['join_inv'])})")
        if row["score_prov"] > 1.0:
            why_parts.append(f"Tỉnh mạnh ({int(row['win_prov'])}/{int(row['join_prov'])})")
        if row["score_f"] > 1.0:
            why_parts.append(f"Lĩnh vực mạnh ({int(row['win_f'])}/{int(row['join_f'])})")
        if row["score_seg"] > 1.0:
            why_parts.append(f"Giá cạnh tranh ({int(row['win_seg'])}/{int(row['join_seg'])})")

        competitors.append(
            CompetitorInfo(
                taxcode=str(row["taxcode"]),
                orgfullname=str(row["orgfullname"]),
                join_investor=int(row["join_inv"]),
                win_investor=int(row["win_inv"]),
                join_province=int(row["join_prov"]),
                win_province=int(row["win_prov"]),
                join_field=int(row["join_f"]),
                win_field=int(row["win_f"]),
                join_segment=int(row["join_seg"]),
                win_segment=int(row["win_seg"]),
                score_investor=round(float(row["score_inv"]), 2),
                score_province=round(float(row["score_prov"]), 2),
                score_field=round(float(row["score_f"]), 2),
                score_segment=round(float(row["score_seg"]), 2),
                total_score=round(float(row["total_score"]), 2),
                avg_won_price=float(row["avg_won_price"]) if not pd.isna(row["avg_won_price"]) else 0.0,
                why_strong=" | ".join(why_parts) if why_parts else "Nguy hiểm tiềm ẩn",
            )
        )

    return competitors
