"""Module ingest - đọc CSV gốc, chuẩn hóa schema, tạo curated parquet."""
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd


REQUIRED_COLS = [
    "bidonotifycontractormnotifyno",
    "bidonotifycontractormbidname",
    "provincename",
    "taxcode",
    "orgfullname",
    "bidresult",
]

DATE_COLS = [
    "bidecontractorinputresultdtoopendate",
    "bidecontractorinputresultdtopublicdate",
    "bidecontractorinputresultdtodecisiondate",
]

PRICE_COL = "bidecontractorinputresultdtobidprice"

FIELD_MAPPING = {
    "HH": "Hàng hóa",
    "HON_HOP": "Hỗn hợp",
    "PTV": "Phi tư vấn",
    "TV": "Tư vấn",
    "XL": "Xây lắp",
}


def _detect_encoding(csv_path: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            df = pd.read_csv(csv_path, nrows=10, encoding=enc, low_memory=False)
            return enc
        except Exception:
            continue
    return "utf-8"


def _normalize_field(val) -> str:
    if pd.isna(val):
        return "Khác"
    f = str(val).strip().upper()
    return FIELD_MAPPING.get(f, str(val).strip())


def _normalize_text_for_search(text: Optional[str]) -> str:
    if pd.isna(text):
        return ""
    text = str(text).strip().lower()
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_text


def read_raw_csv(csv_path: str, *, verbose: bool = True) -> pd.DataFrame:
    enc = _detect_encoding(csv_path)
    if verbose:
        print(f"  [Ingest] Đọc CSV với encoding: {enc}")
    df = pd.read_csv(csv_path, low_memory=False, encoding=enc)
    return df


def validate_columns(df: pd.DataFrame) -> bool:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Thiếu cột bắt buộc: {missing}")
    return True


def _build_tender_text(row) -> str:
    parts = [
        str(row.get("bidonotifycontractormbidname", "")) or "",
        str(row.get("bidonotifycontractormprojectname", "")) or "",
        str(row.get("bidonotifycontractorminvestfield", "")) or "",
        str(row.get("bidonotifycontractorminvestorname", "")) or "",
        str(row.get("provincename", "")) or "",
    ]
    return " | ".join(p for p in parts if p)


def ingest(
    csv_path: str,
    curated_dir: str,
    *,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full ingest pipeline: đọc CSV gốc -> chuẩn hóa -> tạo curated parquet.

    Returns:
        (contractor_history, tender_snapshot)
    """
    curated_path = Path(curated_dir)
    curated_path.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("[Ingest] Bắt đầu pipeline...")
    df = read_raw_csv(csv_path, verbose=verbose)
    if verbose:
        print(f"  [Ingest] Đã đọc {len(df)} dòng gốc.")

    validate_columns(df)

    # ── Parse ngày ──────────────────────────────────────────────
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # ── Parse giá ────────────────────────────────────────────────
    if PRICE_COL in df.columns:
        df[PRICE_COL] = pd.to_numeric(df[PRICE_COL], errors="coerce").fillna(0.0)

    # ── Map lĩnh vực ─────────────────────────────────────────────
    if "bidonotifycontractorminvestfield" in df.columns:
        df["bidonotifycontractorminvestfield"] = df["bidonotifycontractorminvestfield"].apply(
            _normalize_field
        )

    # ── Tạo cột ascii cho search ─────────────────────────────────
    for col in [
        "bidonotifycontractormbidname",
        "bidonotifycontractorminvestfield",
        "provincename",
        "orgfullname",
        "bidonotifycontractorminvestorname",
    ]:
        if col in df.columns:
            df[f"{col}_ascii"] = df[col].apply(_normalize_text_for_search)

    # ── Tạo tender_text ──────────────────────────────────────────
    df["tender_text"] = df.apply(_build_tender_text, axis=1)
    df["tender_text_ascii"] = df["tender_text"].apply(_normalize_text_for_search)

    # ── Tạo is_winner ───────────────────────────────────────────
    if "bidresult" in df.columns:
        df["is_winner"] = df["bidresult"].isin([1, 10])
    else:
        df["is_winner"] = False

    # ── Chuẩn hóa bidresult ──────────────────────────────────────
    if "bidresult" in df.columns:
        df["bidresult"] = df["bidresult"].fillna(0).astype("int8")

    # ── Dedup: contractor_history ───────────────────────────────
    id_cols = ["bidonotifycontractormnotifyno", "taxcode"]
    existing = [c for c in id_cols if c in df.columns]
    if existing:
        df = df.sort_values("bidecontractorinputresultdtodecisiondate", ascending=False)
        df = df.drop_duplicates(subset=existing, keep="first")

    contractor_history = df.copy()
    ch_path = curated_path / "contractor_history.parquet"
    contractor_history.to_parquet(ch_path, compression="snappy", index=False)
    if verbose:
        print(f"  [Ingest] Đã lưu contractor_history: {len(contractor_history)} dòng -> {ch_path}")

    # ── Build tender_snapshot ────────────────────────────────────
    snapshot = _build_tender_snapshot(df)
    ts_path = curated_path / "tender_snapshot.parquet"
    snapshot.to_parquet(ts_path, compression="snappy", index=False)
    if verbose:
        print(f"  [Ingest] Đã lưu tender_snapshot: {len(snapshot)} dòng -> {ts_path}")

    if verbose:
        print("[Ingest] Hoàn tất.")
    return contractor_history, snapshot


def _build_tender_snapshot(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Tổng hợp dữ liệu cấp gói thầu.
    Mỗi bidonotifycontractormnotifyno chỉ còn 1 dòng.
    """
    notifyno_col = "bidonotifycontractormnotifyno"
    if notifyno_col not in history_df.columns:
        return pd.DataFrame()

    # Winner info
    winners = (
        history_df[history_df["is_winner"]]
        .groupby(notifyno_col, sort=False)
        .agg(
            winning_price=("bidecontractorinputresultdtobidprice", "first"),
            winner_names=("orgfullname", lambda x: "; ".join(x.dropna().unique())),
            winner_count=("is_winner", "sum"),
        )
    )

    # Participant count
    participant_cnt = history_df.groupby(notifyno_col, sort=False).size().rename("participant_count")

    # Median bid price (bao gồm cả winner)
    median_price = (
        history_df.groupby(notifyno_col, sort=False)["bidecontractorinputresultdtobidprice"]
        .median()
        .rename("bid_price_median")
    )

    # Take first row as representative for non-numeric fields
    rep_cols = [
        notifyno_col,
        "bidonotifycontractormbidname",
        "bidonotifycontractormprojectname",
        "bidonotifycontractorminvestorname",
        "bidonotifycontractorminvestfield",
        "bidonotifycontractormcapitaldetail",
        "provincename",
        "tender_text",
        "tender_text_ascii",
        "bidecontractorinputresultdtoopendate",
        "bidecontractorinputresultdtopublicdate",
        "bidecontractorinputresultdtodecisiondate",
        "cob_dt",
    ]
    available_rep = [c for c in rep_cols if c in history_df.columns and c != notifyno_col]
    rep = (
        history_df.drop_duplicates(subset=[notifyno_col], keep="first")
        .set_index(notifyno_col)[available_rep]
    )

    snapshot = rep.join(participant_cnt).join(median_price).join(winners)

    # bid_price: ưu tiên winning_price, fallback median
    snapshot["bid_price"] = snapshot["winning_price"].fillna(snapshot["bid_price_median"])

    # taxcode + orgfullname trong snapshot bỏ trống nếu participant_count > 1
    snapshot["taxcode"] = snapshot["participant_count"].apply(
        lambda x: "" if x > 1 else snapshot.get("taxcode", "")
    )
    snapshot["orgfullname"] = snapshot["participant_count"].apply(
        lambda x: "" if x > 1 else snapshot.get("orgfullname", "")
    )

    # price_basis
    snapshot["price_basis"] = snapshot.apply(
        lambda r: "winning"
        if r.get("winning_price", 0) > 0
        else ("median" if r.get("bid_price_median", 0) > 0 else "unknown"),
        axis=1,
    )

    snapshot = snapshot.reset_index()
    return snapshot
