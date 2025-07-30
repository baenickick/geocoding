import streamlit as st
import pandas as pd
import numpy as np
import requests, io, time, csv
import folium
from streamlit_folium import st_folium
from matplotlib import cm                           # 색상 스케일용
from matplotlib import colors as mcolors
from io import BytesIO                              # Excel 다운로드용

# ────────────────────────────── 페이지·폰트 설정 ──────────────────────────────
st.set_page_config(page_title="GEOCODING TOOL", page_icon="🐱", layout="wide")

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_11-01@1.0/NanumSquareAc.woff2');
html, body, [class*="css"] {font-family: 'NanumSquareAc', sans-serif !important;}
.stApp, h1,h2,h3,h4,h5,h6 {font-weight:700 !important;}
.stButton>button {font-weight:600 !important;}
.block-container{padding-left:1rem;padding-right:1rem;}
.stColumn>div{padding:0 !important;}
</style>
""", unsafe_allow_html=True)

# ────────────────────────────── 카카오 API 키 ──────────────────────────────
KAKAO_API_KEY = "5d4c572b337634c65d1d65fc68519085"

# ────────────────────────────── 세션 상태 ──────────────────────────────
for k, v in {"test_completed": False, "full_processing": False,
             "processed_data": None,  "dark_map": None}.items():
    if k not in st.session_state: st.session_state[k] = v

# ────────────────────────────── 유틸 함수 ──────────────────────────────
def geocode_kakao(addr:str):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    try:
        r = requests.get(url, headers=headers, params={"query": addr}, timeout=5)
        if r.status_code == 200 and r.json()["documents"]:
            lon = float(r.json()["documents"][0]["x"])
            lat = float(r.json()["documents"][0]["y"])
            return lat, lon
    except Exception:
        pass
    return None, None

def detect_separator(content:bytes)->str:
    text = content.decode(errors="ignore")
    seps, best, score = ['\t', ',', ';', '|', '^'], ',', 0
    lines = text.split('\n')[:10]
    for s in seps:
        lens = [len(line.split(s)) for line in lines if line.strip()]
        if lens:
            avg = sum(lens)/len(lens)
            cons = sum(abs(l-avg)<=1 for l in lens)/len(lens)
            sc = avg*cons
            if sc>score and avg>1: best, score = s, sc
    return best

def find_address_column(df:pd.DataFrame)->str|None:
    candidates = ['주소','address','addr','도로명주소','지번주소','road','소재지','위치','location']
    for c in df.columns:
        if c.lower() in candidates: return c
    for c in df.columns:
        if any(k in c.lower() for k in candidates): return c
    return None

def get_color_from_value(val, vmin, vmax, cmap_name="Reds"):
    """수치 → HEX 색 변환"""                           # Matplotlib cmap 사용[70]
    if pd.isna(val) or vmin==vmax: return "#808080"
    norm = max(0,min(1,(val-vmin)/(vmax-vmin)))
    r,g,b = cm.get_cmap(cmap_name)(norm)[:3]
    return "#{:02X}{:02X}{:02X}".format(int(r*255),int(g*255),int(b*255))

def create_dark_map(df, addr_col, color_mode, base_color,
                    color_col=None, cmap_name="Reds"):
    mdata = df.dropna(subset=['위도','경도'])
    if mdata.empty: return None
    lat_c, lon_c = mdata['위도'].mean(), mdata['경도'].mean()
    fmap = folium.Map([lat_c, lon_c], zoom_start=7, tiles=None,
                      attribution_control=False)
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
        attr='&copy; OpenStreetMap & CARTO', control=False).add_to(fmap)

    if color_mode=="데이터 기반 색상" and color_col in mdata.columns:
        vmin, vmax = mdata[color_col].min(), mdata[color_col].max()
    for _, row in mdata.iterrows():
        if color_mode=="데이터 기반 색상" and color_col in mdata.columns:
            c = get_color_from_value(row[color_col], vmin, vmax, cmap_name)
        else:
            c = base_color
        folium.CircleMarker(
            [row['위도'],row['경도']], radius=6, color=c, fillColor=c,
            fillOpacity=0.9, weight=2,
            tooltip=f"{row[addr_col]}",
            popup=(f"<b>{row[addr_col]}</b><br>"
                   f"위도:{row['위도']:.6f}<br>경도:{row['경도']:.6f}"
                   + (f"<br>{color_col}: {row[color_col]}" if color_mode=="데이터 기반 색상" and color_col else "")
            )
        ).add_to(fmap)
    return fmap

# ────────────────────────────── 파일 업로드 처리 ──────────────────────────────
st.subheader("📂 CSV 파일 업로드")
up = st.file_uploader("Upload", type=['csv'])
if not up: st.stop()

content = up.getvalue()
sep = detect_separator(content)
try: df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='utf-8')
except UnicodeDecodeError: df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='cp949')

addr_col = find_address_column(df)
if addr_col is None:
    st.error("주소 칼럼을 찾을 수 없습니다.")
    st.stop()

st.success(f"주소 칼럼: **{addr_col}** 인식")
st.write(df.head())

# ────────────────────────────── 사이드바 색상 옵션 ──────────────────────────────
with st.sidebar:
    st.header("🎨 지도 스타일")
    color_mode = st.radio("색상 설정 방식", ["단일 색상","데이터 기반 색상"], horizontal=True)
    if color_mode=="단일 색상":
        base_color = st.color_picker("마커 색상", "#FF4757")
        color_col, cmap_name = None, "Reds"
    else:
        num_cols = df.select_dtypes(include=np.number).columns.tolist()  # 수치형 추출[98]
        num_cols = [c for c in num_cols if c not in ['위도','경도']]
        if not num_cols:
            st.warning("숫자형 칼럼이 없어 데이터 기반 색상을 사용할 수 없습니다.")
            color_mode, base_color, color_col = "단일 색상", "#FF4757", None
        else:
            color_col = st.selectbox("색상 기준 칼럼", num_cols)
            cmap_name = st.selectbox("색상 스케일", ["Reds","Blues","Greens","Viridis","Plasma","coolwarm","RdYlBu"])
            base_color = "#FF4757"  # placeholder

# ────────────────────────────── 지오코딩 실행 버튼 ──────────────────────────────
if st.button("🚀 지오코딩 전체 실행", type="primary"):
    df['위도'], df['경도'] = None, None
    prog = st.progress(0)
    for i, addr in enumerate(df[addr_col]):
        lat, lon = geocode_kakao(str(addr))
        df.at[i,'위도'], df.at[i,'경도'] = lat, lon
        prog.progress((i+1)/len(df))
        time.sleep(0.05)
    st.success("지오코딩 완료!")
    st.session_state.processed_data = df.copy()
    st.session_state.dark_map = None  # 새로 그리기

# ────────────────────────────── 결과 시각화 및 다운로드 ──────────────────────────────
if st.session_state.processed_data is not None:
    res = st.session_state.processed_data

    # 지도 생성 (필요시 새로)
    if st.session_state.dark_map is None:
        st.session_state.dark_map = create_dark_map = create_dark_minimal_map(
            res, addr_col
        ) if color_mode=="단일 색상" else create_dark_minimal_map(
            res, addr_col, color_mode, base_color, color_col, cmap_name
        )

    col_map, col_tbl = st.columns([2,1], gap="small")
    with col_map:
        st.markdown("### 🌃 위치 지도")
        if st.session_state.dark_map:
            st_folium(st.session_state.dark_map, width=None, height=600, returned_objects=[])
    with col_tbl:
        st.markdown("### 📋 변환 결과")
        st.dataframe(res[[addr_col,'위도','경도']].head(1000), use_container_width=True, height=470)

        # CSV 다운 (utf-8-sig 인코딩 → 한글 깨짐 방지[83])
        csv_buffer = io.StringIO()
        res.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        st.download_button("⬇️ CSV 다운로드", csv_buffer.getvalue().encode('utf-8-sig'),
                           "geocoded_addresses.csv", mime="text/csv", use_container_width=True)

        # Excel 다운 (.xlsx, openpyxl 엔진[83])
        towrite = BytesIO()
        with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
            res.to_excel(writer, index=False, sheet_name="Geocoding")
        st.download_button("⬇️ Excel 다운로드", towrite.getvalue(),
                           "geocoded_addresses.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
