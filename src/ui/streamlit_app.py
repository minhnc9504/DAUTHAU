"""Streamlit UI - 3-tab interface cho hệ thống gợi ý gói thầu."""
import io

import pandas as pd
import streamlit as st

from data.store import ContractorStore, TenderStore
from ranking.hybrid import HybridRanker
from ranking.lexical import LexicalIndexer
from ranking.semantic import SemanticIndexer
from services.competitor import analyze_competitors
from services.profile import get_profile, load_profiles
from settings import SETTINGS
import joblib


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────


def _format_currency(value: float) -> str:
    if not value or value <= 0:
        return "N/A"
    return f"{value:,.0f}".replace(",", ".")


def _format_date(val) -> str:
    if val is None or pd.isna(val):
        return "Chưa cập nhật"
    try:
        if hasattr(val, "strftime"):
            return val.strftime("%d/%m/%Y")
        return pd.to_datetime(val).strftime("%d/%m/%Y")
    except Exception:
        return "Chưa cập nhật"


def _to_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return buf.getvalue()


# ────────────────────────────────────────────────────────────────
# Cached loaders
# ────────────────────────────────────────────────────────────────


@st.cache_resource
def load_hybrid_ranker() -> HybridRanker | None:
    lex_path = SETTINGS.lexical_index_path
    sem_path = SETTINGS.semantic_index_path
    hybrid_path = SETTINGS.hybrid_index_path

    try:
        if lex_path.exists():
            lexical = LexicalIndexer.load(lex_path)
        elif hybrid_path.exists():
            data = joblib.load(hybrid_path)
            lexical = LexicalIndexer.__new__(LexicalIndexer)
            lexical.vectorizer = data["lexical"]["vectorizer"]
            lexical.matrix = data["lexical"]["matrix"]
            lexical.tender_ids = data["lexical"]["tender_ids"]
        else:
            return None

        semantic = None
        if sem_path.exists():
            semantic = SemanticIndexer.load(sem_path)
        elif hybrid_path.exists():
            try:
                data = joblib.load(hybrid_path)
                if data.get("semantic", {}).get("ready", False):
                    semantic = SemanticIndexer.__new__(SemanticIndexer)
                    semantic.model_name = data["semantic"]["model_name"]
                    semantic.embeddings = data["semantic"]["embeddings"]
                    semantic.tender_ids = data["semantic"]["tender_ids"]
                    semantic.ready = data["semantic"]["ready"]
                else:
                    semantic = None
            except Exception:
                semantic = None

        weights = SETTINGS.get_normalized_weights(
            semantic.ready if semantic else False
        )
        return HybridRanker(lexical, semantic, weights)
    except Exception as e:
        st.error(f"Lỗi load hybrid index: {e}")
        return None


@st.cache_data(ttl=3600)
def load_tender_store() -> TenderStore | None:
    if not SETTINGS.tender_snapshot_path.exists():
        return None
    try:
        return TenderStore(SETTINGS.tender_snapshot_path)
    except Exception as e:
        st.error(f"Lỗi load tender store: {e}")
        return None


@st.cache_data(ttl=3600)
def load_contractor_store() -> ContractorStore | None:
    if not SETTINGS.contractor_history_path.exists():
        return None
    try:
        return ContractorStore(SETTINGS.contractor_history_path)
    except Exception as e:
        st.error(f"Lỗi load contractor store: {e}")
        return None


@st.cache_data(ttl=3600)
def load_profiles_df():
    if not SETTINGS.company_profiles_path.exists():
        return None
    try:
        return load_profiles(SETTINGS.company_profiles_path)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def load_metadata() -> dict:
    import json

    if SETTINGS.metadata_path.exists():
        try:
            with open(SETTINGS.metadata_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ────────────────────────────────────────────────────────────────
# Region definitions
# ────────────────────────────────────────────────────────────────

MIEN_BAC = SETTINGS.mien_bac
MIEN_TRUNG = SETTINGS.mien_trung
MIEN_NAM = SETTINGS.mien_nam

PRICE_MAP = SETTINGS.price_map

# ────────────────────────────────────────────────────────────────
# Main render
# ────────────────────────────────────────────────────────────────


APP_TITLE = SETTINGS.app_title


def render():
    st.set_page_config(
        page_title="Gợi ý gói thầu phù hợp cho DN",
        layout="wide",
    )

    st.markdown("""
    <style>
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: #c1c1c1; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #a8a8a8; }
    [data-testid="stMetricValue"] { font-size: 28px; }
    </style>
    """, unsafe_allow_html=True)

    st.title(APP_TITLE)
    st.markdown("---")

    ranker = load_hybrid_ranker()
    tender_store = load_tender_store()
    contractor_store = load_contractor_store()
    profiles_df = load_profiles_df()
    metadata = load_metadata()

    if ranker is None or tender_store is None:
        st.error(
            "❌ Thiếu artifact. Vui lòng chạy `python main.py rebuild` trước khi mở UI."
        )
        return

    sem_ready = ranker.semantic_ready

    tabs = st.tabs([
        "📊 Hồ sơ doanh nghiệp",
        "🎯 Gợi ý gói thầu",
        "🔍 Sức khỏe dữ liệu",
    ])

    with tabs[0]:
        _render_profile_tab(contractor_store, profiles_df)

    with tabs[1]:
        _render_recommendation_tab(
            tender_store, ranker, contractor_store, profiles_df, sem_ready
        )

    with tabs[2]:
        _render_health_tab(metadata, tender_store, contractor_store, sem_ready)


# ────────────────────────────────────────────────────────────────
# Tab 1: Hồ sơ doanh nghiệp
# ────────────────────────────────────────────────────────────────

def _render_profile_tab(contractor_store: ContractorStore, profiles_df):
    st.subheader("📊 Hồ sơ doanh nghiệp")

    if contractor_store is None:
        st.warning("Chưa có dữ liệu lịch sử.")
        return

    companies = ["-- Chọn công ty --"] + contractor_store.available_companies

    default_idx = 0
    if (
        "pending_company" in st.session_state
        and st.session_state.pending_company in companies
    ):
        default_idx = companies.index(st.session_state.pending_company)
        st.session_state.pending_company = None

    selected = st.selectbox(
        "Chọn doanh nghiệp:", companies,
        index=default_idx,
        key="profile_company",
    )

    if selected == "-- Chọn công ty --":
        st.info("Vui lòng chọn một doanh nghiệp để xem hồ sơ.")
        return

    hist = contractor_store.get_history(orgfullname=selected)
    if hist.empty:
        st.warning("Không tìm thấy lịch sử.")
        return

    stats = contractor_store.get_company_stats(selected)
    total = stats.get("participated_count", 0)
    won = stats.get("won_count", 0)
    rate = stats.get("win_rate", 0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng gói đã tham gia", f"{total}")
    c2.metric("Số gói trúng thầu", f"{won}")
    c3.metric("Tỉ lệ thắng", f"{rate}%")

    if profiles_df is not None:
        profile = get_profile(profiles_df, selected)
        if profile:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Lĩnh vực mạnh:**")
                for f in profile.get("strong_fields", []):
                    st.markdown(f"  - {f}")
                st.markdown("**Địa bàn mạnh:**")
                for p in profile.get("strong_provinces", []):
                    st.markdown(f"  - {p}")
            with col2:
                st.markdown(
                    f"**Khung giá:** {_format_currency(profile.get('price_low',0))}"
                    f" — {_format_currency(profile.get('price_high',0))}"
                )
                st.markdown(
                    f"**Giá trung vị:** {_format_currency(profile.get('median_price',0))}"
                )
                st.markdown("**Chủ đầu tư quen:**")
                for inv in profile.get("familiar_investors", [])[:5]:
                    st.markdown(f"  - {inv}")

    st.markdown("**Lịch sử tham gia:**")
    display = hist.copy()
    display["Kết quả"] = display["is_winner"].apply(
        lambda x: "🟢 TRÚNG" if x else "🔴 KHÔNG TRÚNG"
    )

    def _get_reason(row):
        if row.get("is_winner", False):
            return ""
        return str(row.get("reason", "")) if pd.notna(row.get("reason")) else ""

    display["Lý do"] = display.apply(_get_reason, axis=1)
    display["Ngày mở"] = display["bidecontractorinputresultdtoopendate"].apply(_format_date)
    display["Ngày công bố"] = display["bidecontractorinputresultdtopublicdate"].apply(_format_date)
    display["Giá Dự Thầu"] = display["bidecontractorinputresultdtobidprice"].apply(_format_currency)

    out = display[[
        "bidonotifycontractormnotifyno",
        "bidonotifycontractormbidname",
        "bidonotifycontractorminvestorname",
        "provincename",
        "bidonotifycontractorminvestfield",
        "Ngày mở",
        "Giá Dự Thầu",
        "Kết quả",
        "Lý do",
    ]].copy()
    out.columns = ["Mã gói", "Tên gói", "Chủ đầu tư", "Tỉnh", "Lĩnh vực", "Ngày mở", "Giá", "Kết quả", "Lý do"]

    rows = len(out)
    height = min(rows * 35 + 50, 500)
    st.dataframe(
        out.sort_values("Ngày mở", ascending=False),
        width="stretch",
        hide_index=True,
        height=height,
    )

    st.download_button(
        "📥 Tải lịch sử (Excel)",
        _to_excel(out),
        f"lich_su_{selected[:20]}.xlsx",
    )


# ────────────────────────────────────────────────────────────────
# Tab 2: Gợi ý gói thầu
# ────────────────────────────────────────────────────────────────

def _render_recommendation_tab(tender_store, ranker, contractor_store, profiles_df, sem_ready):
    st.subheader("🎯 Gợi ý gói thầu")

    user_type = st.radio(
        "Đối tượng doanh nghiệp:",
        ["Đã có lịch sử đấu thầu", "Doanh nghiệp mới"],
        horizontal=True,
        key="rec_user_type",
    )

    query_input = None
    selected_company = None

    col1, col2, col3 = st.columns(3)
    with col1:
        if user_type == "Đã có lịch sử đấu thầu" and contractor_store:
            companies = ["-- Chọn công ty --"] + contractor_store.available_companies
            default_idx = 0
            if (
                "pending_company" in st.session_state
                and st.session_state.pending_company in companies
            ):
                default_idx = companies.index(st.session_state.pending_company)
            selected_company = st.selectbox(
                "Chọn doanh nghiệp",
                companies,
                index=default_idx,
                key="rec_company",
            )
        else:
            query_input = st.text_input(
                "Nhập ngành nghề/doanh nghiệp",
                placeholder="Ví dụ: xây lắp, tư vấn...",
                key="rec_query",
            )

    with col2:
        region_opts = ["Tất cả", "Miền Bắc", "Miền Trung", "Miền Nam"] + tender_store.available_provinces
        target_region = st.selectbox("Khu vực ưu tiên", region_opts, key="rec_region")

    with col3:
        field_opts = ["Tất cả lĩnh vực"] + tender_store.available_fields
        target_field = st.selectbox("Lĩnh vực", field_opts, key="rec_field")

    st.markdown("### 💰 Phân khúc giá dự thầu (VNĐ)")
    price_range = st.select_slider(
        "Kéo để chọn phân khúc ngân sách:",
        options=list(PRICE_MAP.keys()),
        value=("0", "Trên 1000 Tỷ"),
        key="rec_price",
    )
    price_min = PRICE_MAP.get(price_range[0], 0)
    price_max = PRICE_MAP.get(price_range[1], 1e15)

    if st.button("🔍 PHÂN TÍCH GỢI Ý GÓI THẦU", use_container_width=True, key="rec_analyze"):
        _do_recommend(
            tender_store, ranker, contractor_store, profiles_df,
            user_type, selected_company,
            query_input if user_type == "Doanh nghiệp mới" else None,
            target_region, target_field, price_min, price_max,
        )

    if "rec_results" in st.session_state and st.session_state.rec_results is not None:
        _display_recommendation_with_competitors(
            st.session_state.rec_results, ranker, contractor_store
        )


def _do_recommend(tender_store, ranker, contractor_store, profiles_df,
                  user_type, selected_company, query_input,
                  target_region, target_field, price_min, price_max):
    query_text = ""
    orgfullname = None

    if user_type == "Đã có lịch sử đấu thầu":
        if selected_company and selected_company != "-- Chọn công ty --":
            orgfullname = selected_company
            if profiles_df is not None:
                profile = get_profile(profiles_df, selected_company)
                if profile:
                    query_text = profile.get("text_profile", "")
        else:
            st.warning("Vui lòng chọn doanh nghiệp.")
            return
    else:
        query_text = query_input or ""

    if not query_text:
        st.warning("Vui lòng nhập thông tin để phân tích.")
        return

    provinces = None
    if target_region and target_region != "Tất cả":
        if target_region == "Miền Bắc":
            provinces = MIEN_BAC
        elif target_region == "Miền Trung":
            provinces = MIEN_TRUNG
        elif target_region == "Miền Nam":
            provinces = MIEN_NAM
        else:
            provinces = [target_region]

    fields = None
    if target_field and target_field != "Tất cả lĩnh vực":
        fields = [target_field]

    with st.spinner("Đang phân tích..."):
        ranked = ranker.score(query_text, tender_store.df, profile=None)
    # Lọc gói thầu đã đóng thầu (nếu có ngày hiệu lực)
    # from datetime import datetime
    # now = datetime.now()
    # date_filtered = []
    # for r in ranked:
    #     eff_date = r.decision_date or r.open_date
    #     if eff_date is not None:
    #         try:
    #             eff_date = pd.to_datetime(eff_date)
    #             if eff_date < now:
    #                 continue
    #         except Exception:
    #             pass
    #     date_filtered.append(r)
    # ranked = date_filtered
    ranked = ranked  # Không lọc ngày - hiển thị tất cả gói thầu
    filtered = []
    for r in ranked:
        if provinces and r.province not in provinces:
            continue
        if fields and r.field not in fields:
            continue
        if r.bid_price > 0:
            if r.bid_price < price_min or r.bid_price > price_max:
                continue
        filtered.append(r)

    if orgfullname and profiles_df is not None:
        profile = get_profile(profiles_df, orgfullname)
        if profile:
            for r in filtered:
                h_fit, p_fit, why_parts = _profile_scores(r, profile)
                r.historical_fit_score = round(h_fit, 2)
                r.price_fit_score = round(p_fit, 2)
                w = ranker.weights
                r.total_score = round(
                    w.get("lexical", 0) * r.lexical_score
                    + w.get("semantic", 0) * r.semantic_score
                    + w.get("historical", 0) * r.historical_fit_score
                    + w.get("price", 0) * r.price_fit_score
                    + w.get("recency", 0) * r.recency_score,
                    2,
                )
                parts = list(why_parts)
                if r.lexical_score > SETTINGS.lexical_weight * 100:
                    parts.append("Đúng ngành nghề")
                if r.historical_fit_score > SETTINGS.historical_weight * 100:
                    parts.append("Phù hợp lịch sử")
                if r.price_fit_score > SETTINGS.price_weight * 100:
                    parts.append("Khung giá phù hợp")
                if r.recency_score > SETTINGS.recency_weight * 100:
                    parts.append("Sắp đóng thầu")
                r.why_recommended = " | ".join(parts) if parts else "Phù hợp"

    filtered.sort(key=lambda x: x.total_score, reverse=True)
    st.session_state.rec_results = filtered[:SETTINGS.top_k_results]


def _profile_scores(ranked_tender, profile: dict) -> tuple:
    why_parts = []
    hist = 0.0

    tender_field = ranked_tender.field.strip()
    tender_province = ranked_tender.province.strip()
    tender_price = ranked_tender.bid_price

    strong_fields = [str(f).strip() for f in profile.get("strong_fields", [])]
    strong_provinces = [str(p).strip() for p in profile.get("strong_provinces", [])]
    familiar_investors = [str(i).strip() for i in profile.get("familiar_investors", [])]

    if tender_field in strong_fields:
        hist += 50.0
        why_parts.append("Đúng lĩnh vực mạnh")
    if tender_province in strong_provinces:
        hist += 30.0
        why_parts.append("Đúng địa bàn mạnh")
    if ranked_tender.investor_name.strip() in familiar_investors:
        hist += 20.0
        why_parts.append("Cùng CĐT quen")

    hist_score = profile.get("_hist_score", 100.0) if "_hist_score" in profile else 100.0
    price_fit = 0.0
    p_low = float(profile.get("price_low", 0))
    p_high = float(profile.get("price_high", 0))
    if p_low > 0 and p_high > 0:
        if p_low <= tender_price <= p_high:
            price_fit = 100.0
            why_parts.append("Nằm trong khung giá")
        elif tender_price > 0:
            if tender_price < p_low:
                price_fit = max(0, 100 - ((p_low - tender_price) / p_low * 100))
            else:
                price_fit = max(0, 100 - ((tender_price - p_high) / p_high * 100))
            price_fit = min(price_fit, 100.0)

    return min(hist_score, 100.0), price_fit, why_parts


def _display_recommendation_with_competitors(results, ranker, contractor_store):
    if not results:
        st.warning("Không tìm thấy gói thầu phù hợp.")
        return

    st.success(f"✅ Tìm thấy {len(results)} gói thầu phù hợp nhất.")

    rows = []
    for r in results:
        rows.append({
            "Mã gói": r.notifyno,
            "Tên gói thầu": r.bid_name,
            "Chủ đầu tư": r.investor_name,
            "Tỉnh": r.province,
            "Lĩnh vực": r.field,
            "Giá dự kiến": _format_currency(r.bid_price),
            "Ngày mở thầu": _format_date(r.open_date),
            "Người tham gia": r.participant_count,
            "Điểm lexical": r.lexical_score,
            "Điểm semantic": r.semantic_score,
            "Điểm lịch sử": r.historical_fit_score,
            "Điểm giá": r.price_fit_score,
            "Điểm recency": r.recency_score,
            "**Tổng điểm": r.total_score,
            "**Phân tích": r.why_recommended,
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        height=500,
        column_config={
            "**Tổng điểm": st.column_config.ProgressColumn(
                "Tổng điểm", format="%.1f", min_value=0, max_value=100,
                help="Lexical + Semantic + Historical + Price + Recency",
            ),
            "Tên gói thầu": st.column_config.TextColumn("Tên gói thầu", width="large"),
        },
    )
    st.download_button(
        "📥 Tải danh sách (Excel)",
        _to_excel(df),
        "goi_y_goi_thau.xlsx",
    )

    st.markdown("---")
    st.subheader("🛡️ Phân tích đối thủ")

    tender_options = [
        f"{r.notifyno} | {str(r.bid_name)[:60]}"
        for r in results
    ]
    selected_tender = st.selectbox(
        "🎯 Chọn gói thầu để xem đối thủ:",
        tender_options,
        key="comp_select",
    )

    if selected_tender and contractor_store is not None:
        notifyno = selected_tender.split(" | ")[0]
        sel_ranked = next((r for r in results if r.notifyno == notifyno), None)

        col1, col2 = st.columns(2)
        with col1:
            companies = ["-- Không loại trừ --"] + contractor_store.available_companies
            excl = st.selectbox("Loại trừ công ty của tôi:", companies, key="comp_excl_rec")
        with col2:
            st.write("")

        current_company = ""
        current_taxcode = ""
        if excl != "-- Không loại trừ --":
            current_company = excl
            current_taxcode = contractor_store.get_company_taxcode(excl) or ""

        if sel_ranked:
            i1, i2, i3, i4 = st.columns(4)
            i1.markdown(f"📍 **Tỉnh:** {sel_ranked.province}")
            i2.markdown(f"📋 **Lĩnh vực:** {sel_ranked.field}")
            i3.markdown(
                f"🏢 **CĐT:** {str(sel_ranked.investor_name)[:40]}"
            )
            i4.markdown(f"💰 **Giá:** {_format_currency(sel_ranked.bid_price)}")

        st.markdown("---")

        competitors = analyze_competitors(
            contractor_store.df, notifyno,
            current_taxcode=current_taxcode,
            current_company=current_company,
        )

        if not competitors:
            st.warning("Không tìm thấy đối thủ.")
            return

        st.success(f"Tìm thấy {len(competitors)} đối thủ tiềm năng.")

        comp_rows = []
        for c in competitors:
            comp_rows.append({
                "MST": c.taxcode,
                "Tên đối thủ": c.orgfullname,
                "CĐT (T/D)": f"{c.win_investor}/{c.join_investor}",
                "Tỉnh (T/D)": f"{c.win_province}/{c.join_province}",
                "Lĩnh vực (T/D)": f"{c.win_field}/{c.join_field}",
                "Giá (T/D)": f"{c.win_segment}/{c.join_segment}",
                "Đ.CĐT": c.score_investor,
                "Đ.Tỉnh": c.score_province,
                "Đ.Lĩnh vực": c.score_field,
                "Đ.Giá": c.score_segment,
                "**Tổng Kỵ Rơ": c.total_score,
                "Quy mô TB": _format_currency(c.avg_won_price),
                "**Giải thích": c.why_strong,
            })

        comp_df = pd.DataFrame(comp_rows)
        st.dataframe(
            comp_df.style.background_gradient(
                subset=["Đ.CĐT", "Đ.Tỉnh", "Đ.Lĩnh vực", "Đ.Giá", "**Tổng Kỵ Rơ"],
                cmap="YlOrRd",
            ).format({
                "Đ.CĐT": "{:.2f}", "Đ.Tỉnh": "{:.2f}",
                "Đ.Lĩnh vực": "{:.2f}", "Đ.Giá": "{:.2f}", "**Tổng Kỵ Rơ": "{:.2f}",
            }),
            width="stretch",
            hide_index=True,
        )

        st.download_button(
            "📥 Tải danh sách đối thủ (Excel)",
            _to_excel(comp_df),
            f"doi_thu_{notifyno[:20]}.xlsx",
        )


# ────────────────────────────────────────────────────────────────
# Tab 3: Sức khỏe dữ liệu
# ────────────────────────────────────────────────────────────────

def _render_health_tab(metadata, tender_store, contractor_store, sem_ready):
    st.subheader("🔍 Sức khỏe dữ liệu")

    c1, c2, c3, c4 = st.columns(4)
    tender_count = len(tender_store.df) if tender_store else 0
    contractor_count = len(contractor_store.df) if contractor_store else 0

    c1.metric("Tổng gói thầu", f"{tender_count:,}")
    c2.metric("Tổng bidder-history", f"{contractor_count:,}")
    c3.metric("Semantic ready", "✅ Có" if sem_ready else "❌ Không")
    c4.metric("Semantic model", SETTINGS.semantic_model_name)

    st.markdown("---")
    st.markdown("**📋 Metadata:**")
    if metadata:
        for k, v in metadata.items():
            st.markdown(f"  - `{k}`: {v}")
    else:
        st.info("Chưa có metadata. Chạy `python main.py rebuild` để tạo.")

    st.markdown("---")
    st.markdown("**📁 Artifact paths:**")
    for name, path in [
        ("contractor_history", SETTINGS.contractor_history_path),
        ("tender_snapshot", SETTINGS.tender_snapshot_path),
        ("company_profiles", SETTINGS.company_profiles_path),
        ("hybrid_index", SETTINGS.hybrid_index_path),
        ("metadata", SETTINGS.metadata_path),
    ]:
        status = "✅" if path.exists() else "❌"
        st.markdown(f"  {status} `{name}`: `{path}`")

    st.markdown("---")
    st.markdown("**⚙️ Trọng số tính điểm hiện tại:**")
    weights = SETTINGS.get_normalized_weights(sem_ready)
    for k, v in weights.items():
        st.markdown(f"  - `{k}`: {v:.2f} ({v*100:.0f}%)")


if __name__ == "__main__":
    render()
