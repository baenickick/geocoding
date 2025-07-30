import streamlit as st, pandas as pd, numpy as np, requests, io, time
import folium, matplotlib.cm as cm
from streamlit_folium import st_folium
from io import BytesIO

# ────────────────── 1. 페이지 · 폰트 ──────────────────
st.set_page_config(page_title="GEOCODING TOOL", page_icon="🐱", layout="wide",
                   initial_sidebar_state="collapsed")   # 기본은 접힘

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_11-01@1.0/NanumSquareAc.woff2');
html, body, [class*="css"] {font-family:'NanumSquareAc',sans-serif!important}
h1,h2,h3,h4,h5,h6{font-weight:700!important}
.stButton>button{font-weight:600!important}
.block-container{padding-left:1rem;padding-right:1rem}
.stColumn>div{padding:0!important}
</style>
""", unsafe_allow_html=True)

# ────────────────── 2. 카카오 API ──────────────────
KAKAO_API_KEY = "5d4c572b337634c65d1d65fc68519085"

# ────────────────── 3. 세션 상태 ──────────────────
keys_defaults = {
    "test_completed": False, "full_processing": False,
    "processed": None, "map_obj": None,
    "color_mode": "단일 색상", "marker_color": "#FF4757",
    "color_col": None, "cmap_name": "Reds"
}
for k, v in keys_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ────────────────── 4. 함수 ──────────────────
def geocode(addr:str):
    url="https://dapi.kakao.com/v2/local/search/address.json"
    try:
        r=requests.get(url,headers={"Authorization":f"KakaoAK {KAKAO_API_KEY}"},
                       params={"query":addr},timeout=5)
        j=r.json()["documents"];  lon,lat=float(j[0]["x"]),float(j[0]["y"])
        return lat, lon
    except Exception: return None, None

def detect_sep(raw:bytes):
    txt=raw.decode(errors="ignore"); seps=['\t',',',';','|','^']; best=','
    score=0; lines=txt.split('\n')[:10]
    for s in seps:
        lens=[len(l.split(s)) for l in lines if l.strip()]
        if lens:
            avg=sum(lens)/len(lens); cons=sum(abs(x-avg)<=1 for x in lens)/len(lens)
            sc=avg*cons
            if sc>score and avg>1: best,score=s,sc
    return best

def address_col(df):
    cands=['주소','address','addr','도로명주소','지번주소','road','소재지','위치','location']
    for c in df.columns:
        if c.lower() in cands: return c
    for c in df.columns:
        if any(k in c.lower() for k in cands): return c
    return None

def val2hex(val,vmin,vmax,cmap):
    if vmin==vmax: return "#808080"
    norm=(val-vmin)/(vmax-vmin); norm=max(0,min(1,norm))
    r,g,b=cm.get_cmap(cmap)(norm)[:3]
    return "#{:02X}{:02X}{:02X}".format(int(r*255),int(g*255),int(b*255))

def build_map(df, addr_c):
    m=folium.Map(location=[df['위도'].mean(),df['경도'].mean()],
                 zoom_start=7, tiles=None, attribution_control=False)
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
        attr='&copy;OSM & CARTO', control=False).add_to(m)

    if st.session_state.color_mode=="데이터 기반 색상" and st.session_state.color_col:
        col=st.session_state.color_col; vmin=df[col].min(); vmax=df[col].max()
    else:
        col, vmin, vmax = None, None, None

    for _, r in df.dropna(subset=['위도','경도']).iterrows():
        if col: c=val2hex(r[col],vmin,vmax,st.session_state.cmap_name)
        else:   c=st.session_state.marker_color
        folium.CircleMarker(
            [r['위도'],r['경도']], radius=6, color=c, fillColor=c,
            fillOpacity=0.9, tooltip=r[addr_c]).add_to(m)
    return m

# ────────────────── 5. UI ──────────────────
st.title("📍 주소 → 위도·경도 변환기")
st.write("CSV 올리고 **5개 샘플 테스트 → 전체 변환** 순서로 진행하세요.")

up=st.file_uploader("CSV 업로드",type=["csv"])
if up:
    raw=up.getvalue(); sep=detect_sep(raw)
    try: df=pd.read_csv(io.BytesIO(raw),sep=sep,encoding='utf-8')
    except UnicodeDecodeError: df=pd.read_csv(io.BytesIO(raw),sep=sep,encoding='cp949')

    addr_c=address_col(df)
    if not addr_c: st.error("주소 칼럼을 찾지 못했습니다."); st.stop()

    st.subheader("샘플 미리보기")
    st.dataframe(df.head())
    st.info(f"인식된 주소 칼럼: **{addr_c}** / 총 {len(df)}행")

    # ── 5개 샘플 테스트 ──
    if st.button("🧪 샘플 5개 테스트"):
        test_res=[]
        bar=st.progress(0)
        for i in range(5):
            a=df.iloc[i][addr_c]; lat,lon=geocode(str(a))
            test_res.append([a,lat,lon])
            bar.progress((i+1)/5)
        st.table(pd.DataFrame(test_res,columns=['주소','위도','경도']))
        succ=sum(pd.notna(x[1]) for x in test_res)
        st.metric("테스트 성공률",f"{succ/5*100:.1f}%")
        est=f"{len(df)*0.05/60:.1f} 분"
        st.info(f"전체 처리 예상 소요: 약 **{est}**")

        st.session_state.test_completed=True
        st.session_state.test_data=df.copy()
        st.session_state.addr_col=addr_c

    # ── 전체 데이터 처리 ──
    if st.session_state.test_completed and st.button("🚀 전체 데이터 처리"):
        d=st.session_state.test_data
        bar=st.progress(0); status=st.empty()
        for i,a in enumerate(d[addr_c]):
            lat,lon=geocode(str(a))
            d.at[i,'위도'],d.at[i,'경도']=lat,lon
            if i%50==0 or i<10: status.text(f"{i+1}/{len(d)} 처리 중...")
            bar.progress((i+1)/len(d))
            time.sleep(0.02)
        st.success("전체 지오코딩 완료!")
        st.session_state.processed=d
        st.session_state.map_obj=None      # 새 지도 필요

    # ── 지도 & 결과 영역 ──
    if st.session_state.processed is not None:
        result=st.session_state.processed

        # 지도 없으면 생성
        if st.session_state.map_obj is None:
            st.session_state.map_obj=build_map(result, st.session_state.addr_col)

        # 컬럼 레이아웃
        col_map,col_opt,col_tbl=st.columns([5,1,4],gap="small")
        with col_map:
            st_folium(st.session_state.map_obj,height=600,width=None,returned_objects=[])

        # ⚙️ 스타일 버튼 → Expander
        with col_opt:
            with st.expander("⚙️ 스타일"):
                st.session_state.color_mode=st.radio("색상 모드",
                                                     ["단일 색상","데이터 기반 색상"],
                                                     index=0)
                if st.session_state.color_mode=="단일 색상":
                    st.session_state.marker_color=st.color_picker(
                        "마커 색",st.session_state.marker_color)
                else:
                    num_cols=[c for c in result.select_dtypes(np.number).columns
                              if c not in ['위도','경도']]
                    if num_cols:
                        st.session_state.color_col=st.selectbox("기준 칼럼",num_cols)
                        st.session_state.cmap_name=st.selectbox(
                            "컬러맵",["Reds","Blues","Greens","Viridis","Plasma","coolwarm"])
                    else:
                        st.warning("숫자형 칼럼이 없습니다. 단일 색상으로 전환됩니다.")
                        st.session_state.color_mode="단일 색상"

                if st.button("🎨 적용"):
                    st.session_state.map_obj=build_map(result, st.session_state.addr_col)

        with col_tbl:
            st.subheader("결과 데이터")
            st.dataframe(result[[st.session_state.addr_col,'위도','경도']],
                         use_container_width=True,height=600)
            # ── 다운로드 ──
            csv= result.to_csv(index=False,encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("⬇️ CSV",csv,"geocoded.csv",mime="text/csv")
            xls_buf=BytesIO()
            with pd.ExcelWriter(xls_buf,engine="openpyxl") as w:
                result.to_excel(w,index=False,sheet_name="Geocoding")
            st.download_button("⬇️ Excel",xls_buf.getvalue(),
                               "geocoded.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
