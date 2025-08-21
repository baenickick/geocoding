import streamlit as st, pandas as pd, numpy as np, requests, io, time
import folium, matplotlib.cm as cm
from streamlit_folium import st_folium
from io import BytesIO

# ────────────────── 1. 페이지 · 폰트 ──────────────────
st.set_page_config(page_title="GEOCODING TOOL", page_icon="🐱", layout="wide",
                   initial_sidebar_state="collapsed")

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
    "test_completed": False, "processed": None, "map_obj": None,
    "color_mode": "단일 색상", "marker_color": "#FF4757",
    "color_col": None, "cmap_name": "Reds", "marker_size": 6
}
for k, v in keys_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ────────────────── 4. 함수 ──────────────────
def geocode(addr:str):
    url="https://dapi.kakao.com/v2/local/search/address.json"
    try:
        r=requests.get(url,headers={"Authorization":f"KakaoAK {KAKAO_API_KEY}"},
                       params={"query":addr},timeout=5)
        j=r.json()["documents"]
        if j:
            lon,lat=float(j[0]["x"]),float(j[0]["y"])
            return lat, lon
    except Exception: pass
    return None, None

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
    if pd.isna(val) or vmin==vmax: return "#808080"
    norm=(val-vmin)/(vmax-vmin); norm=max(0,min(1,norm))
    r,g,b=cm.get_cmap(cmap)(norm)[:3]
    return "#{:02X}{:02X}{:02X}".format(int(r*255),int(g*255),int(b*255))

def build_map(df, addr_c):
    valid_data = df.dropna(subset=['위도','경도'])
    if valid_data.empty:
        return None
        
    m=folium.Map(location=[valid_data['위도'].mean(),valid_data['경도'].mean()],
                 zoom_start=7, tiles=None, attribution_control=False)
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
        attr='&copy;OSM & CARTO', control=False).add_to(m)

    if st.session_state.color_mode=="데이터 기반 색상" and st.session_state.color_col:
        col=st.session_state.color_col
        col_data = valid_data[col].dropna()
        if len(col_data) > 0:
            vmin, vmax = col_data.min(), col_data.max()
        else:
            vmin, vmax = 0, 1
    else:
        col, vmin, vmax = None, None, None

    for _, r in valid_data.iterrows():
        if col and not pd.isna(r[col]): 
            c=val2hex(r[col],vmin,vmax,st.session_state.cmap_name)
        else:   
            c=st.session_state.marker_color
        folium.CircleMarker(
            [r['위도'],r['경도']], 
            radius=st.session_state.marker_size,
            color=c, fillColor=c, fillOpacity=0.9, weight=2,
            popup=folium.Popup(
                f"<b>{str(r[addr_c])[:40]}</b><br>"
                f"위도: {r['위도']:.6f}<br>"
                f"경도: {r['경도']:.6f}",
                max_width=200
            ),
            tooltip=f"{str(r[addr_c])[:25]}..."
        ).add_to(m)
    return m

# ────────────────── 5. UI ──────────────────
st.title("📍 주소 → 위도·경도 변환기")
st.markdown("CSV 파일을 업로드하면 주소를 위도/경도로 자동 변환하고 시각화해드립니다! ⸜(๑'ᵕ'๑)⸝ ")

up=st.file_uploader("CSV 파일을 업로드하세요",type=["csv"])
if up:
    raw=up.getvalue(); sep=detect_sep(raw)
    try: df=pd.read_csv(io.BytesIO(raw),sep=sep,encoding='utf-8')
    except UnicodeDecodeError: df=pd.read_csv(io.BytesIO(raw),sep=sep,encoding='cp949')

    addr_c=address_col(df)
    if not addr_c: 
        st.error("주소 칼럼을 찾을 수 없습니다.")
        st.info("가능한 칼럼: " + ", ".join(df.columns))
        st.stop()

    st.subheader("📋 업로드된 데이터")
    st.dataframe(df.head())
    st.info(f"'{addr_c}' 칼럼을 주소로 인식했습니다. | 총 {len(df)}개 행, {len(df.columns)}개 칼럼")

    # ── 5개 샘플 테스트 ──
    if st.button("🧪 테스트 실행 (처음 5개)", type="primary"):
        st.session_state.test_completed = False
        st.session_state.processed = None
        st.session_state.map_obj = None
        
        st.subheader("🧪 테스트 결과")
        test_res=[]
        bar=st.progress(0)
        status_text = st.empty()
        
        for i in range(min(5, len(df))):
            addr = df.iloc[i][addr_c]
            if pd.notna(addr):
                status_text.text(f"테스트 중: {addr}")
                lat,lon=geocode(str(addr))
                test_res.append({
                    '주소': str(addr)[:50],
                    '위도': lat,
                    '경도': lon,
                    '상태': '✅ 성공' if lat else '❌ 실패'
                })
                bar.progress((i+1)/5)
                time.sleep(0.1)
        
        test_df = pd.DataFrame(test_res)
        st.dataframe(test_df)
        
        success_count = len([r for r in test_res if r['위도']])
        success_rate = success_count / len(test_res) * 100
        st.metric("테스트 성공률", f"{success_rate:.1f}%")
        
        # 더 정확한 예상 시간 계산
        avg_time_per_request = 0.1  # 초당 처리 시간
        total_estimated_time = len(df) * avg_time_per_request
        if total_estimated_time < 60:
            time_str = f"{total_estimated_time:.0f}초"
        else:
            time_str = f"{total_estimated_time/60:.1f}분"
        
        st.session_state.test_completed=True
        st.session_state.test_data=df.copy()
        st.session_state.addr_col=addr_c
        
        st.markdown("---")
        st.subheader("💡 테스트 완료!")
        st.info(f"전체 {len(df)}개 주소 처리 예상 시간: 약 **{time_str}**")

    # ── 전체 데이터 처리 ──
    if st.session_state.test_completed:
        st.markdown("### 🚀 전체 데이터 처리")
        
        if st.button("🚀 전체 데이터 처리 시작", type="secondary"):
            df = st.session_state.test_data
            addr_c = st.session_state.addr_col
            
            st.markdown("### 📊 전체 데이터 처리 중...")
            
            df_result = df.copy()
            df_result['위도'] = None
            df_result['경도'] = None
            
            bar=st.progress(0)
            status=st.empty()
            success_count = 0
            
            for i in range(len(df)):
                addr = df.iloc[i][addr_c]
                if pd.notna(addr):
                    if i % 50 == 0 or i < 10:
                        status.text(f"처리 중 {i+1}/{len(df)}: {str(addr)[:30]}...")
                    
                    lat,lon=geocode(str(addr))
                    df_result.at[i,'위도'] = lat
                    df_result.at[i,'경도'] = lon
                    
                    if lat:
                        success_count += 1
                    
                    bar.progress((i+1)/len(df))
                    time.sleep(0.05)
            
            status.text(f"✅ 완료! {success_count}/{len(df)}개 성공 ({success_count/len(df)*100:.1f}%)")
            
            st.session_state.processed=df_result
            st.session_state.addr_col=addr_c
            st.session_state.map_obj=None

    # ── 지도 & 결과 영역 ──
    if st.session_state.processed is not None:
        result=st.session_state.processed
        addr_c = st.session_state.addr_col

        # 지도 없으면 생성
        if st.session_state.map_obj is None:
            st.session_state.map_obj=build_map(result, addr_c)

        st.markdown("---")
        st.subheader("📊 최종 결과 - 어두운 톤 미니멀 지도 & 데이터")
        
        # 컬럼 레이아웃
        col_map, col_table = st.columns([2, 1], gap="small")
        
        with col_map:
            st.markdown("### 🌃 위치 지도 (Dark Theme)")
            
            # 지도 표시
            if st.session_state.map_obj:
                st_folium(st.session_state.map_obj, height=600, width=None, returned_objects=[], key="main_map")
                
                successful_locations = result.dropna(subset=['위도', '경도'])
                if st.session_state.color_mode == "데이터 기반 색상" and st.session_state.color_col:
                    color_values = successful_locations[st.session_state.color_col].dropna()
                    if len(color_values) > 0:
                        st.info(f"🎨 색상 기준: {st.session_state.color_col} (범위: {color_values.min():.2f} ~ {color_values.max():.2f}) | 📍 표시된 위치: {len(successful_locations)}개")
                    else:
                        st.info(f"🔴 지도에 표시된 위치: {len(successful_locations)}개")
                else:
                    st.info(f"🔴 지도에 표시된 위치: {len(successful_locations)}개")
            else:
                st.warning("표시할 위치 데이터가 없습니다.")
            
            # ═══════════════════════════════════════════════════════════
            # 🎨 마커 스타일 설정 - 지도 아래에 위치
            # ═══════════════════════════════════════════════════════════
            st.markdown("---")
            st.subheader("🎨 마커 스타일")
            
            # 한 줄에 4개 컨트롤 + 적용 버튼
            style_col1, style_col2, style_col3, style_col4, apply_col = st.columns([2, 2, 2, 2, 1])
            
            with style_col1:
                new_color_mode = st.selectbox(
                    "색상 모드", 
                    ["단일 색상", "데이터 기반 색상"],
                    index=0 if st.session_state.color_mode == "단일 색상" else 1,
                    key="color_mode_select"
                )
                if new_color_mode != st.session_state.color_mode:
                    st.session_state.color_mode = new_color_mode
            
            with style_col2:
                if st.session_state.color_mode == "단일 색상":
                    new_color = st.color_picker(
                        "마커 색상", 
                        st.session_state.marker_color,
                        key="marker_color_picker"
                    )
                    if new_color != st.session_state.marker_color:
                        st.session_state.marker_color = new_color
                else:
                    num_cols = [c for c in result.select_dtypes(np.number).columns
                               if c not in ['위도','경도']]
                    if num_cols:
                        new_col = st.selectbox("기준 칼럼", num_cols, key="color_col_select")
                        if new_col != st.session_state.color_col:
                            st.session_state.color_col = new_col
                    else:
                        st.warning("숫자형 칼럼 없음")
                        st.session_state.color_mode = "단일 색상"
            
            with style_col3:
                if st.session_state.color_mode == "데이터 기반 색상":
                    new_cmap = st.selectbox(
                        "컬러맵",
                        ["Reds","Blues","Greens","Viridis","Plasma","coolwarm","RdYlBu"],
                        index=["Reds","Blues","Greens","Viridis","Plasma","coolwarm","RdYlBu"].index(st.session_state.cmap_name),
                        key="cmap_select"
                    )
                    if new_cmap != st.session_state.cmap_name:
                        st.session_state.cmap_name = new_cmap
                else:
                    st.empty()  # 빈 공간
            
            with style_col4:
                new_size = st.slider(
                    "마커 크기", 
                    min_value=3, max_value=15, 
                    value=st.session_state.marker_size,
                    key="marker_size_slider"
                )
                if new_size != st.session_state.marker_size:
                    st.session_state.marker_size = new_size
            
            with apply_col:
                if st.button("🎨 적용", key="apply_style"):
                    st.session_state.map_obj = build_map(result, addr_c)
                    st.rerun()

        with col_table:
            st.markdown("### 📋 변환 결과")
            
            # 다운로드 버튼들을 수평으로 배치
            dl_col1, dl_col2 = st.columns(2)
            
            with dl_col1:
                # CSV 다운로드
                csv_buffer = io.StringIO()
                result.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📄 CSV 다운로드",
                    data=csv_buffer.getvalue().encode('utf-8-sig'),
                    file_name="geocoded_addresses.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with dl_col2:
                # Excel 다운로드
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    result.to_excel(writer, sheet_name='지오코딩결과', index=False)
                st.download_button(
                    label="📊 Excel 다운로드",
                    data=excel_buffer.getvalue(),
                    file_name="geocoded_addresses.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            # 결과 테이블
            result_display = result[[addr_c, '위도', '경도']].copy()
            result_display.columns = ['주소', '위도', '경도']
            result_display['주소'] = result_display['주소'].astype(str).str[:25] + "..."
            
            st.dataframe(
                result_display,
                height=280,
                use_container_width=True
            )
            
            # 변환 통계
            st.markdown("### 📈 변환 통계")
            
            total_count = len(result)
            success_count = result['위도'].notna().sum()
            fail_count = total_count - success_count
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("성공", success_count, delta=None)
            with col_stat2:
                st.metric("실패", fail_count, delta=None)  
            with col_stat3:
                st.metric("성공률", f"{success_count/total_count*100:.1f}%", delta=None)
            
            st.markdown("---")
            
            # 성공/실패 비율 프로그레스 바
            if total_count > 0:
                success_ratio = success_count / total_count
                st.markdown("**처리 현황**")
                st.progress(success_ratio)
                st.caption(f"전체 {total_count}개 중 {success_count}개 성공 ({success_ratio*100:.1f}%)")
            
            # 실패한 주소 목록
            failed_addresses = result[result['위도'].isna()]
            if len(failed_addresses) > 0:
                st.markdown("**❌ 변환 실패 주소**")
                with st.expander(f"실패한 주소 {len(failed_addresses)}개 보기", expanded=False):
                    for idx, row in failed_addresses.head(6).iterrows():
                        st.text(f"• {str(row[addr_c])[:35]}")
                    if len(failed_addresses) > 6:
                        st.text(f"... 외 {len(failed_addresses)-6}개 더")
            else:
                st.success("🎉 모든 주소가 성공적으로 변환되었습니다!")
            
            # 추가 정보
            st.markdown("---")
            st.markdown("**💡 변환 정보**")
            
            valid_coords = result.dropna(subset=['위도', '경도'])
            if len(valid_coords) > 0:
                lat_range = f"{valid_coords['위도'].min():.4f} ~ {valid_coords['위도'].max():.4f}"
                lon_range = f"{valid_coords['경도'].min():.4f} ~ {valid_coords['경도'].max():.4f}"
                
                info_col1, info_col2 = st.columns(2)
                with info_col1:
                    st.caption(f"**위도 범위**  \n{lat_range}")
                with info_col2:
                    st.caption(f"**경도 범위**  \n{lon_range}")

# 사용법 안내
with st.expander("📖 사용 방법"):
    st.markdown("""
    ### 🚀 사용 방법 3단계
    1. **CSV 파일 업로드**: 주소가 포함된 CSV 파일 선택
    2. **테스트 실행**: 처음 5개 주소로 정상 작동 확인
    3. **전체 처리**: 테스트 성공 후 전체 데이터 변환 및 지도 시각화
    
    ### ✨ 주요 기능
    - **자동 구분자 감지**: 탭, 쉼표 등 자동 인식
    - **주소 칼럼 자동 찾기**: '주소', 'address' 등 자동 탐지
    - **어두운 톤 미니멀 지도**: 도로와 경계선만 표시하는 다크 테마 지도 시각화
    - **실시간 스타일 조정**: 색상, 크기 등을 지도 아래에서 바로 변경
    - **실시간 진행률**: 처리 상황 실시간 확인!
    - **CSV & Excel 다운로드**: 한글 깨짐 없는 완벽한 파일 저장 
    """)

st.markdown("---")
st.markdown("by 배서현 baenickick ʢᴗ.ᴗʡ | Powered by Kakao API, Streamlit & Folium")
