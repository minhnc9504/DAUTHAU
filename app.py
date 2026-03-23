import streamlit as st
import pandas as pd
import pickle
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os
import io
from datetime import datetime

# ===============================
# CẤU HÌNH TRANG
# ===============================
st.set_page_config(
    page_title="Hệ thống Gợi ý gói thầu phù hợp cho Doanh nghiệp",
    layout="wide"
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

# ===============================
# DANH MỤC VÙNG MIỀN
# ===============================
MIEN_BAC = ['Hà Nội', 'Hải Phòng', 'Hà Giang', 'Cao Bằng', 'Bắc Kạn', 'Tuyên Quang',
            'Lào Cai', 'Yên Bái', 'Thái Nguyên', 'Lạng Sơn', 'Quảng Ninh', 'Bắc Giang',
            'Phú Thọ', 'Vĩnh Phúc', 'Bắc Ninh', 'Hải Dương', 'Hưng Yên', 'Thái Bình',
            'Hà Nam', 'Nam Định', 'Ninh Bình', 'Điện Biên', 'Lai Châu', 'Sơn La', 'Hòa Bình']
MIEN_TRUNG = ['Thanh Hóa', 'Nghệ An', 'Hà Tĩnh', 'Quảng Bình', 'Quảng Trị', 'Thừa Thiên Huế',
              'Đà Nẵng', 'Quảng Nam', 'Quảng Ngãi', 'Bình Định', 'Phú Yên', 'Khánh Hòa',
              'Ninh Thuận', 'Bình Thuận', 'Kon Tum', 'Gia Lai', 'Đắk Lắk', 'Đắk Nông', 'Lâm Đồng']
MIEN_NAM = ['TP Hồ Chí Minh', 'Bình Dương', 'Đồng Nai', 'Bà Rịa - Vũng Tàu', 'Bình Phước',
            'Tây Ninh', 'Long An', 'Tiền Giang', 'Bến Tre', 'Trà Vinh', 'Vĩnh Long',
            'Đồng Tháp', 'An Giang', 'Kiên Giang', 'Cần Thơ', 'Hậu Giang', 'Sóc Trăng',
            'Bạc Liêu', 'Cà Mau']

# ===============================
# HÀM TRỢ GIÚP
# ===============================
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def format_currency(value):
    try:
        if pd.isna(value) or value == 0: return "0"
        return "{:,.0f}".format(float(value)).replace(",", ".")
    except: return "0"

# ✅ FIX: Bỏ format_date dùng apply, dùng vectorized thay thế
def format_date_series(series):
    """Vectorized date formatting - nhanh hơn apply() nhiều lần"""
    return pd.to_datetime(series, dayfirst=True, errors='coerce') \
             .dt.strftime('%d/%m/%Y') \
             .fillna('Chưa cập nhật')

def clean_field_name(field):
    if pd.isna(field): return "Khác"
    f = str(field).strip()
    mapping = {
        'HH': 'Hàng hóa', 'Hàng hóa': 'Hàng hóa',
        'HON_HOP': 'Hỗn hợp', 'Hỗn hợp': 'Hỗn hợp',
        'PTV': 'Phi tư vấn', 'Phi tư vấn': 'Phi tư vấn',
        'TV': 'Tư vấn', 'Tư vấn': 'Tư vấn',
        'XL': 'Xây lắp', 'Xây lắp': 'Xây lắp',
    }
    return mapping.get(f, f)

# ===============================
# TẢI DỮ LIỆU & MODEL
# ===============================
@st.cache_resource
def load_assets():
    try:
        with open('models/tfidf_model.pkl', 'rb') as f: tfidf = pickle.load(f)
        with open('models/tfidf_matrix.pkl', 'rb') as f: tfidf_matrix = pickle.load(f)
        return tfidf, tfidf_matrix
    except Exception as e:
        st.error(f"❌ Không tìm thấy mô hình AI: {e}")
        st.stop()

# ✅ FIX: Thêm ttl=3600 để cache không bị stale vô hạn
@st.cache_data(ttl=3600)
def load_data():
    path = "data/dauthau_data.parquet"
    if not os.path.exists(path):
        st.error("❌ Không tìm thấy dữ liệu tại 'data/dauthau_data.parquet'")
        st.stop()
    
    df = pd.read_parquet(path)
    
    df['bidecontractorinputresultdtobidprice'] = pd.to_numeric(
        df['bidecontractorinputresultdtobidprice'], errors='coerce'
    ).fillna(0)
    
    df['bidonotifycontractorminvestfield'] = df['bidonotifycontractorminvestfield'].apply(clean_field_name)
    
    # ✅ Convert ngày 1 lần duy nhất khi load
    df['dt_opendate'] = pd.to_datetime(df['bidecontractorinputresultdtoopendate'], dayfirst=True, errors='coerce')
    df['dt_decisiondate'] = pd.to_datetime(df['bidecontractorinputresultdtodecisiondate'], dayfirst=True, errors='coerce')

    list_companies = sorted(df['orgfullname'].dropna().unique())
    list_provinces = sorted(df['provincename'].dropna().unique())
    list_fields = sorted(df['bidonotifycontractorminvestfield'].dropna().unique())
    region_options = ["Tất cả", "Miền Bắc", "Miền Trung", "Miền Nam"] + list_provinces
    
    return df, list_companies, region_options, list_fields

tfidf, tfidf_matrix = load_assets()
df, list_companies, region_options, list_fields = load_data()

# ===============================
# GIAO DIỆN NHẬP LIỆU
# ===============================
st.title("🚀 Hệ thống Gợi ý gói thầu phù hợp cho Doanh nghiệp v12.0")
st.markdown("---")

user_type = st.radio("Đối tượng doanh nghiệp:", ["Đã có lịch sử đấu thầu", "Doanh nghiệp mới"], horizontal=True)

col1, col2, col3 = st.columns(3)
with col1:
    if user_type == "Đã có lịch sử đấu thầu":
        selected_company = st.selectbox("Chọn doanh nghiệp", ["-- Chọn công ty --"] + list_companies)
    else:
        query_input_new = st.text_input("Nhập ngành nghề/doanh nghiệp", placeholder="Ví dụ: xây lắp, tư vấn...")

with col2:
    target_location = st.selectbox("Khu vực ưu tiên", region_options)

with col3:
    target_field = st.selectbox("Lĩnh vực", ["Tất cả lĩnh vực"] + list_fields)

st.markdown("### 💰 Phân khúc giá dự thầu (VNĐ)")
price_map = {
    "0": 0, "1 Tỷ": 1e9, "5 Tỷ": 5e9, "10 Tỷ": 10e9, "30 Tỷ": 30e9, "50 Tỷ": 50e9,
    "100 Tỷ": 100e9, "200 Tỷ": 200e9, "300 Tỷ": 300e9, "400 Tỷ": 400e9, "500 Tỷ": 500e9,
    "600 Tỷ": 600e9, "700 Tỷ": 700e9, "800 Tỷ": 800e9, "900 Tỷ": 900e9,
    "1000 Tỷ": 1e12, "Trên 1000 Tỷ": 1e15
}
selected_range = st.select_slider(
    "Kéo để chọn phân khúc ngân sách:",
    options=list(price_map.keys()),
    value=("0", "Trên 1000 Tỷ")
)
start_val = price_map[selected_range[0]]
end_val = price_map[selected_range[1]]

# ===============================
# PHẦN 1: LỊCH SỬ ĐẤU THẦU
# ===============================
query_for_ai = ""

if user_type == "Đã có lịch sử đấu thầu":
    if selected_company != "-- Chọn công ty --":
        hist_raw = df[df['orgfullname'] == selected_company].copy() #lọc gói thầu mà doanh nghiệp tham gia trong quá khứ
        query_for_ai = " ".join(hist_raw['bidonotifycontractormbidname'].astype(str))

        st.markdown(f"### 📊 Lịch sử đấu thầu: {selected_company}")
        t1, t2, t3 = st.columns(3)
        tong_goi = len(hist_raw)
        so_trung = hist_raw['bidresult'].isin([1, 10]).sum()
        ti_le = round((so_trung / tong_goi * 100), 1) if tong_goi > 0 else 0

        t1.metric("Tổng gói đã tham gia", f"{tong_goi} gói")
        t2.metric("Số gói trúng thầu", f"{so_trung} gói")
        t3.metric("Tỉ lệ thắng", f"{ti_le}%")

        hist_raw['Kết quả'] = hist_raw['bidresult'].apply(lambda x: "🟢 TRÚNG" if x in [1, 10] else "🔴 KHÔNG TRÚNG")
        
        # ✅ FIX: Dùng vectorized thay vì apply(format_date)
        hist_raw['Ngày Mở'] = format_date_series(hist_raw['bidecontractorinputresultdtoopendate'])
        hist_raw['Ngày công bộ'] = format_date_series(hist_raw['bidecontractorinputresultdtopublicdate'])
        hist_raw['Giá Dự Thầu'] = hist_raw['bidecontractorinputresultdtobidprice'].apply(format_currency)
        hist_raw['Lý do'] = hist_raw.get('reason', pd.Series(["Không có dữ liệu"] * len(hist_raw))).fillna("Không có dữ liệu")

        hist_display = hist_raw[[
            'bidonotifycontractormnotifyno', 'bidonotifycontractormbidname', 'bidonotifycontractormprojectname',
            'provincename', 'bidonotifycontractorminvestfield',
            'Ngày Mở', 'Ngày công bộ', 'Giá Dự Thầu', 'Kết quả', 'Lý do'
        ]].copy()
        hist_display.columns = ["Mã gói", "Tên gói thầu", "Tên dự án", "Tỉnh", "Lĩnh vực",
                                 "Ngày mở thầu", "Ngày công bố", "Giá dự thầu", "Kết quả", "Lý do trúng/trượt"]

        row_count = len(hist_display)
        calculated_height = min(int(35.2 * (row_count + 1)) + 10, 500)
        st.dataframe(
            hist_display.sort_values(by="Ngày mở thầu", ascending=False),
            use_container_width=True, hide_index=True, height=calculated_height
        )
        st.download_button(
            "📥 Tải lịch sử đầy đủ (Excel)",
            to_excel(hist_display),
            f"lich_su_{selected_company.replace(' ', '_')}.xlsx"
        )
        st.markdown("---")
else:
    query_for_ai = query_input_new if 'query_input_new' in locals() else ""

# ===============================
# PHẦN 2: GỢI Ý GÓI THẦU
# ===============================

# ===============================
# HÀM TÍNH TOÁN HYBRID SCORE (CHỈ CHẤM ĐIỂM)
# ===============================
def calculate_hybrid_score(row, start_val, end_val):
    """
    Hàm này CHỈ tính điểm cho 1 dòng dữ liệu. 
    Không chứa lệnh lọc res_df ở đây.
    """
    # a. Điểm chuyên môn (TF-IDF đã tính trước đó)
    lexical_score = row['score'] 
    
    # b. Điểm phân khúc giá (Vì đã lọc cứng ở ngoài nên mặc định là 100)
    price_score = 100 

    # c. Điểm thời gian (Recency)
    days_to_open = (row['dt_opendate'] - datetime.now()).days if pd.notna(row['dt_opendate']) else 0
    if days_to_open > 0:
        recency_score = max(50, 100 - (days_to_open * 2)) 
    else:
        recency_score = 30 

    # d. TỔNG HỢP ĐIỂM (60% Chuyên môn | 25% Giá | 15% Thời gian)
    total_score = (lexical_score * 0.6) + (price_score * 0.25) + (recency_score * 0.15)
    
    # e. PHÂN TÍCH TỪ AI (Lý do gợi ý)
    reasons = []
    if lexical_score > 75: reasons.append("🎯 Chuyên môn rất sát")
    elif lexical_score > 40: reasons.append("✅ Đúng ngành nghề")
    
    reasons.append("💰 Đúng phân khúc vốn")
    
    if 0 < days_to_open <= 10: reasons.append("⏳ Cơ hội vàng (Sắp đóng)")
    
    why_recommended = " | ".join(reasons) if reasons else "🔍 Phù hợp tiêu chuẩn"
    
    return pd.Series([round(total_score, 1), why_recommended])

# ===============================
# GỢI Ý GÓI THẦU (NÂNG CẤP LOGIC LỌC)
# ===============================
if 'final_results' not in st.session_state:
    st.session_state['final_results'] = None

if st.button("🔍 PHÂN TÍCH GỢI Ý GÓI THẦU", use_container_width=True):
    if not query_for_ai:
        st.warning("⚠️ Vui lòng nhập thông tin hoặc chọn doanh nghiệp để AI phân tích.")
    else:
        with st.spinner("AI đang sàng lọc phân khúc giá..."):
            now = datetime.now()

            # 1. Lọc thời gian & Xóa trùng
            res_df = df[
                (df['dt_opendate'] >= now) | 
                (df['dt_decisiondate'] >= now) | 
                (df['dt_decisiondate'].isna())
            ].copy()
            res_df = res_df.drop_duplicates(subset=['bidonotifycontractormnotifyno'])

            # 2. LỌC CỨNG THEO GIÁ (Sửa lỗi lọc ở đây)
            res_df = res_df[
                (res_df['bidecontractorinputresultdtobidprice'] >= start_val) & 
                (res_df['bidecontractorinputresultdtobidprice'] <= end_val)
            ]

            if res_df.empty:
                st.error(f"❌ Không tìm thấy gói thầu nào trong phân khúc giá từ {format_currency(start_val)} đến {format_currency(end_val)}.")
                st.session_state['final_results'] = None
            else:
                # 3. Tính Lexical Score (TF-IDF)
                query_vec = tfidf.transform([query_for_ai.lower()])
                bid_names = res_df['bidonotifycontractormbidname'].astype(str).str.lower()
                current_matrix = tfidf.transform(bid_names)
                sim_scores = cosine_similarity(query_vec, current_matrix).flatten()
                res_df['score'] = (sim_scores * 100).round(1)

                # 4. Áp dụng bộ lọc cứng (Vùng miền & Lĩnh vực)
                if target_location != "Tất cả":
                    if target_location == "Miền Bắc": pattern = '|'.join(MIEN_BAC)
                    elif target_location == "Miền Trung": pattern = '|'.join(MIEN_TRUNG)
                    elif target_location == "Miền Nam": pattern = '|'.join(MIEN_NAM)
                    else: pattern = target_location
                    res_df = res_df[res_df['provincename'].str.contains(pattern, case=False, na=False)]

                if target_field != "Tất cả lĩnh vực":
                    res_df = res_df[res_df['bidonotifycontractorminvestfield'] == target_field]

                # 5. TÍNH ĐIỂM HYBRID (Chỉ chạy khi có dữ liệu sau lọc)
                if not res_df.empty:
                    # Gọi apply để chấm điểm từng dòng
                    res_df[['total_score', 'why_recommended']] = res_df.apply(
                        lambda x: calculate_hybrid_score(x, start_val, end_val), axis=1
                    )
                    
                    # Sắp xếp và lấy Top 20
                    st.session_state['final_results'] = res_df.sort_values('total_score', ascending=False).head(20)
                else:
                    st.warning("⚠️ Không tìm thấy gói thầu phù hợp với khu vực/lĩnh vực sau khi lọc giá.")
                    st.session_state['final_results'] = None

# ===============================
# HIỂN THỊ KẾT QUẢ CUỐI CÙNG
# ===============================
if st.session_state['final_results'] is not None:
    final_results = st.session_state['final_results']

    if final_results.empty:
        st.error("❌ Không tìm thấy gói thầu nào phù hợp với tiêu chí lọc.")
    else:
        st.success(f"✅ Tìm thấy {len(final_results)} gói thầu có độ ưu tiên cao nhất.")

        display_df = final_results.copy()
        display_df['Giá dự kiến'] = display_df['bidecontractorinputresultdtobidprice'].apply(format_currency)
        display_df['Ngày mở thầu'] = display_df['dt_opendate'].dt.strftime('%d/%m/%Y').fillna('Chưa cập nhật')

        # CHUẨN BỊ BẢNG IN RA THEO YÊU CẦU
        out_table = display_df[[
            'bidonotifycontractormnotifyno',     # Mã gói
            'bidonotifycontractormbidname',       # Tên gói
            'bidonotifycontractorminvestorname', # Chủ đầu tư
            'provincename',                      # Tỉnh
            'bidonotifycontractorminvestfield',  # Lĩnh vực
            'Giá dự kiến',                       # Giá dự kiến
            'Ngày mở thầu',                      # Ngày mở thầu
            'total_score',                       # Độ ưu tiên (Điểm tổng hợp)
            'why_recommended'                    # Phân tích từ AI
        ]]
        
        out_table.columns = [
            "Mã gói", "Tên gói thầu", "Chủ đầu tư", "Tỉnh", "Lĩnh vực", 
            "Giá dự kiến", "Ngày mở thầu", "Độ ưu tiên", "Phân tích từ AI"
        ]

        # Hiển thị DataFrame với cấu hình cột đẹp
        st.dataframe(
            out_table, 
            use_container_width=True, 
            hide_index=True,
            height=500,
            column_config={
                "Độ ưu tiên": st.column_config.ProgressColumn(
                    "Độ ưu tiên AI",
                    help="Điểm Hybrid: Chuyên môn (60%) + Giá (25%) + Thời gian (15%)",
                    format="%.1f",
                    min_value=0,
                    max_value=100,
                ),
                "Tên gói thầu": st.column_config.TextColumn("Tên gói thầu", width="large"),
                "Phân tích từ AI": st.column_config.TextColumn("🎯 Phân tích từ AI", width="medium")
            }
        )
        
        st.download_button(
            "📥 Tải danh sách gợi ý chuyên sâu (Excel)", 
            to_excel(out_table), 
            "goi_y_hybrid_ranking.xlsx"
        )

 
# PHẦN SOI ĐỐI THỦ
# ===============================
# Kiểm tra an toàn: Đảm bảo final_results tồn tại trong session_state thì mới hiển thị phần soi đối thủ
if st.session_state.get('final_results') is not None and not st.session_state['final_results'].empty:
    # Lấy lại biến final_results từ session_state
    final_results = st.session_state['final_results']
    
    st.markdown("---")
    st.subheader("🛡️ PHÂN TÍCH ĐỐI THỦ THEO TỪNG GÓI THẦU GỢI Ý")

    # Khởi tạo selectbox chọn gói thầu
    selected_package_name = st.selectbox(
        "🎯 Chọn gói thầu bạn muốn soi đối thủ:",
        final_results['bidonotifycontractormbidname'].tolist(),
        key="select_package_competitor"
    )

    if selected_package_name:
        p_info = final_results[final_results['bidonotifycontractormbidname'] == selected_package_name].iloc[0]
        p_field = p_info['bidonotifycontractorminvestfield']
        p_investor = p_info['bidonotifycontractorminvestorname']
        p_province = p_info['provincename']
        p_price = p_info['bidecontractorinputresultdtobidprice']
        
        # ✅ CẢI THIỆN: Thu hẹp phân khúc giá (50% - 150%) để lọc chính xác hơn
        lower_b, upper_b = p_price * 0.5, p_price * 1.5

        # ✅ Lấy taxcode của công ty hiện tại để loại trừ chính mình
        # Ưu tiên: lấy từ selected_company nếu có, hoặc từ final_results
        current_taxcode = ''
        current_company = ''
        
        if 'selected_company' in dir() and selected_company != "-- Chọn công ty --":
            company_data = df[df['orgfullname'] == selected_company]
            if not company_data.empty:
                current_company = selected_company
                current_taxcode = company_data.iloc[0].get('taxcode', '')
        else:
            # Lấy từ final_results
            current_company = final_results.iloc[0].get('orgfullname', '')
            current_taxcode = final_results.iloc[0].get('taxcode', '')

        # Hiển thị thông tin gói thầu đã chọn
        info_col1, info_col2, info_col3, info_col4 = st.columns(4)
        info_col1.markdown(f"📍 Tỉnh: **{p_province}**")
        info_col2.markdown(f"📋 Lĩnh vực: **{p_field}**")
        info_col3.markdown(f"🏢 CĐT: **{str(p_investor)[:30]}...**" if len(str(p_investor)) > 30 else f"🏢 CĐT: **{p_investor}**")
        info_col4.markdown(f"💰 Giá: **{format_currency(p_price)}**")

        price_low_fmt = format_currency(lower_b)
        price_high_fmt = format_currency(upper_b)
        st.markdown(f"📊 **Top 10 đối thủ tiềm năng (Phân khúc: {price_low_fmt} - {price_high_fmt}):**")

        relevant_cols = [
            'taxcode', 'orgfullname', 'bidonotifycontractorminvestorname',
            'provincename', 'bidonotifycontractorminvestfield',
            'bidecontractorinputresultdtobidprice', 'bidresult'
        ]

        # ✅ CẢI THIỆN: Lọc chặt hơn - kết hợp CĐT + Lĩnh vực + Tỉnh (AND)
        # Đối thủ tiềm năng = Cùng CĐT HOẶC Cùng Lĩnh vực HOẶC Cùng Tỉnh
        mask = (
            (df['bidonotifycontractorminvestorname'] == p_investor) |
            (df['bidonotifycontractorminvestfield'] == p_field) |
            (df['provincename'] == p_province)
        )
        
        comp_df = df.loc[mask, relevant_cols].copy().reset_index(drop=True)

        # ✅ CẢI THIỆN: Loại trừ chính mình khỏi danh sách đối thủ
        if current_taxcode:
            comp_df = comp_df[comp_df['taxcode'] != current_taxcode]
        if current_company:
            comp_df = comp_df[comp_df['orgfullname'] != current_company]

        if not comp_df.empty:
            # Tạo is_won SAU reset_index để index khớp
            is_won = comp_df['bidresult'].isin([1, 10])

            comp_df['at_inv'] = comp_df['bidonotifycontractorminvestorname'] == p_investor
            comp_df['at_prov'] = comp_df['provincename'] == p_province
            comp_df['at_field'] = comp_df['bidonotifycontractorminvestfield'] == p_field
            comp_df['at_seg'] = (
                (comp_df['bidecontractorinputresultdtobidprice'] >= lower_b) &
                (comp_df['bidecontractorinputresultdtobidprice'] <= upper_b)
            )

            # Cột win (bitwise AND - nhanh, an toàn)
            comp_df['win_inv'] = comp_df['at_inv'] & is_won
            comp_df['win_prov'] = comp_df['at_prov'] & is_won
            comp_df['win_f'] = comp_df['at_field'] & is_won
            comp_df['win_seg'] = comp_df['at_seg'] & is_won
            comp_df['won_price'] = comp_df['bidecontractorinputresultdtobidprice'].where(is_won)

            res = comp_df.groupby(['taxcode', 'orgfullname']).agg(
                join_inv = ('at_inv', 'sum'),
                win_inv = ('win_inv', 'sum'),
                join_prov = ('at_prov', 'sum'),
                win_prov = ('win_prov', 'sum'),
                join_f = ('at_field', 'sum'),
                win_f = ('win_f', 'sum'),
                join_seg = ('at_seg', 'sum'),
                win_seg = ('win_seg', 'sum'),
                avg_price = ('won_price', 'mean')
            ).reset_index()

            # Tính điểm Kỵ Rơ (thang 0–2.5 mỗi tiêu chí)
            def get_score(win_col, join_col):
                return (res[win_col] / res[join_col].replace(0, np.nan)).fillna(0) * 2.5

            res['Đ.CĐT'] = get_score('win_inv', 'join_inv')
            res['Đ.Tỉnh'] = get_score('win_prov', 'join_prov')
            res['Đ.Lĩnh vực'] = get_score('win_f', 'join_f')
            res['Đ.Phân khúc']= get_score('win_seg', 'join_seg')
            res['Tổng Kỵ Rơ'] = res[['Đ.CĐT','Đ.Tỉnh','Đ.Lĩnh vực','Đ.Phân khúc']].sum(axis=1)
            
            # ✅ CẢI THIỆN: Tính tổng số lần tham gia để lọc bớt công ty ít kinh nghiệm
            res['Tổng tham gia'] = res['join_inv'] + res['join_prov'] + res['join_f'] + res['join_seg']
            
            # ✅ CẢI THIỆN: Chỉ hiển thị công ty tham gia >= 2 lần (đảm bảo độ tin cậy)
            res = res[res['Tổng tham gia'] >= 2]

            top_rivals = res.sort_values('Tổng Kỵ Rơ', ascending=False).head(10).copy()

            # ✅ Format dạng "win/join" cho 4 chiều
            top_rivals['CĐT'] = top_rivals['win_inv'].astype(int).astype(str) + "/" + top_rivals['join_inv'].astype(int).astype(str)
            top_rivals['Tỉnh'] = top_rivals['win_prov'].astype(int).astype(str) + "/" + top_rivals['join_prov'].astype(int).astype(str)
            top_rivals['Lĩnh vực'] = top_rivals['win_f'].astype(int).astype(str) + "/" + top_rivals['join_f'].astype(int).astype(str)
            top_rivals['Phân khúc'] = top_rivals['win_seg'].astype(int).astype(str) + "/" + top_rivals['join_seg'].astype(int).astype(str)
            top_rivals['Quy mô TB'] = top_rivals['avg_price'].fillna(0).apply(format_currency)

            final_display = top_rivals[[
                "taxcode", "orgfullname",
                "CĐT", "Tỉnh", "Lĩnh vực", "Phân khúc",
                "Đ.CĐT", "Đ.Tỉnh", "Đ.Lĩnh vực", "Đ.Phân khúc",
                "Tổng Kỵ Rơ", "Quy mô TB"
            ]].copy()

            final_display.columns = [
                "MST", "Tên đối thủ",
                "Trúng/Dự CĐT", "Trúng/Dự Tỉnh", "Trúng/Dự Lĩnh vực", "Trúng/Dự Phân khúc",
                "Đ.CĐT", "Đ.Tỉnh", "Đ.Lĩnh vực", "Đ.Phân khúc",
                "Tổng Kỵ Rơ", "Quy mô TB"
            ]

            st.markdown("📊 **Bảng xếp hạng năng lực đối thủ (Thang điểm 10.0):**")
            st.dataframe(
                final_display.style.background_gradient(
                    subset=["Đ.CĐT", "Đ.Tỉnh", "Đ.Lĩnh vực", "Đ.Phân khúc", "Tổng Kỵ Rơ"],
                    cmap='YlOrRd'
                ).format({
                    "Đ.CĐT": "{:.2f}", "Đ.Tỉnh": "{:.2f}",
                    "Đ.Lĩnh vực": "{:.2f}", "Đ.Phân khúc": "{:.2f}",
                    "Tổng Kỵ Rơ": "{:.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )
            st.info(f"💡 Hệ thống đã phân tích lịch sử thầu tại: **{p_investor}**")
        else:
            st.warning("⚠️ Không tìm thấy đối thủ phù hợp.")