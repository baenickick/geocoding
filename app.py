import streamlit as st
import pandas as pd
import requests
import time
import io
import csv
from streamlit_keplergl import keplergl_static
from keplergl import KeplerGl

# 페이지 설정
st.set_page_config(
    page_title="주소 → 좌표 변환기",
    page_icon="📍",
    layout="wide"
)

# 나눔스퀘어 AC 폰트 적용
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_11-01@1.0/NanumSquareAc.woff2');
    
    html, body, [class*="css"]  {
        font-family: 'NanumSquareAc', sans-serif !important;
    }
    
    .stApp {
        font-family: 'NanumSquareAc', sans-serif !important;
    }
    
    /* 제목과 헤더 폰트 */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'NanumSquareAc', sans-serif !important;
        font-weight: 700 !important;
    }
    
    /* 버튼 폰트 */
    .stButton > button {
        font-family: 'NanumSquareAc', sans-serif !important;
        font-weight: 600 !important;
    }
    
    /* 데이터프레임 폰트 */
    .dataframe {
        font-family: 'NanumSquareAc', sans-serif !important;
    }
    
    /* 메트릭 폰트 */
    .metric-container {
        font-family: 'NanumSquareAc', sans-serif !important;
    }
    
    /* 텍스트 입력 폰트 */
    .stTextInput > div > div > input {
        font-family: 'NanumSquareAc', sans-serif !important;
    }
    
    /* 선택박스 폰트 */
    .stSelectbox > div > div > div {
        font-family: 'NanumSquareAc', sans-serif !important;
    }
    
    /* 컬럼 간격 조정 */
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* 지도 컨테이너 크기 조정 */
    .stColumn > div {
        padding: 0 !important;
    }
    
    /* Kepler.gl 컨테이너 크기 맞춤 */
    iframe[title="streamlit_keplergl.keplergl_static"] {
        width: 100% !important;
        height: 600px !important;
    }
</style>
""", unsafe_allow_html=True)

# 카카오 API 키
KAKAO_API_KEY = "5d4c572b337634c65d1d65fc68519085"

# 세션 상태 초기화
if 'test_completed' not in st.session_state:
    st.session_state.test_completed = False
if 'full_processing' not in st.session_state:
    st.session_state.full_processing = False
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'kepler_map' not in st.session_state:
    st.session_state.kepler_map = None

def geocode_kakao(address):
    """카카오 API를 사용한 지오코딩"""
    if not address:
        return None, None
    
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": address}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json().get("documents")
            if data:
                lon = float(data[0]["x"])
                lat = float(data[0]["y"])
                return lat, lon
        return None, None
    except:
        return None, None

def detect_separator(file_content):
    """파일 구분자 자동 감지"""
    if isinstance(file_content, bytes):
        try:
            text_content = file_content.decode('utf-8')
        except:
            try:
                text_content = file_content.decode('euc-kr')
            except:
                text_content = file_content.decode('cp949')
    else:
        text_content = file_content
    
    lines = text_content.split('\n')[:10]
    separators = ['\t', ',', ';', '|', '^']
    
    best_sep = ','
    max_score = 0
    
    for sep in separators:
        scores = []
        for line in lines:
            if line.strip():
                parts = line.split(sep)
                scores.append(len(parts))
        
        if scores:
            avg_cols = sum(scores) / len(scores)
            consistency = sum(1 for s in scores if abs(s - avg_cols) <= 1) / len(scores)
            final_score = avg_cols * consistency
            
            if final_score > max_score and avg_cols > 1:
                max_score = final_score
                best_sep = sep
    
    return best_sep

def find_address_column(df):
    """주소 칼럼 자동 찾기"""
    possible_names = ['주소', 'address', 'addr', '도로명주소', '지번주소', 'road', '소재지', '위치', 'location']
    
    for col in df.columns:
        if col.strip().lower() in [name.lower() for name in possible_names]:
            return col
    
    for col in df.columns:
        for name in possible_names:
            if name in col.lower():
                return col
    
    return None

def create_kepler_map(df_result, address_col):
    """Kepler.gl 지도 생성 (미니멀 스타일)"""
    map_data = df_result.dropna(subset=['위도', '경도']).copy()
    
    if len(map_data) == 0:
        return None
    
    # Kepler.gl 설정 (Light 스타일)
    config = {
        "version": "v1",
        "config": {
            "mapState": {
                "bearing": 0,
                "dragRotate": False,
                "latitude": map_data['위도'].mean(),
                "longitude": map_data['경도'].mean(),
                "pitch": 0,
                "zoom": 7,
                "isSplit": False
            },
            "mapStyle": {
                "styleType": "light",  # 미니멀한 라이트 스타일[20][23]
                "topLayerGroups": {},
                "visibleLayerGroups": {
                    "label": False,      # 라벨 숨김
                    "road": True,        # 도로 표시
                    "border": True,      # 경계선 표시
                    "building": False,   # 건물 숨김
                    "water": True,       # 수계 표시
                    "land": True,        # 지형 표시
                    "3d building": False # 3D 건물 숨김
                },
                "threeDBuildingColor": [194, 194, 194],
                "mapStyles": {}
            },
            "visState": {
                "filters": [],
                "layers": [
                    {
                        "id": "location_points",
                        "type": "point",
                        "config": {
                            "dataId": "locations",
                            "label": "위치",
                            "color": [255, 87, 87],  # 붉은색 포인트
                            "highlightColor": [252, 242, 26, 255],
                            "columns": {
                                "lat": "위도",
                                "lng": "경도"
                            },
                            "isVisible": True,
                            "visConfig": {
                                "radius": 8,
                                "fixedRadius": False,
                                "opacity": 0.8,
                                "outline": False,
                                "thickness": 2,
                                "strokeColor": None,
                                "colorRange": {
                                    "name": "Global Warming",
                                    "type": "sequential",
                                    "category": "Uber",
                                    "colors": ["#5A1846", "#900C3F", "#C70039", "#E3611C", "#F1920E", "#FFC300"]
                                },
                                "strokeColorRange": {
                                    "name": "Global Warming",
                                    "type": "sequential", 
                                    "category": "Uber",
                                    "colors": ["#5A1846", "#900C3F", "#C70039", "#E3611C", "#F1920E", "#FFC300"]
                                },
                                "radiusRange": [0, 50],
                                "filled": True
                            },
                            "hidden": False,
                            "textLabel": [
                                {
                                    "field": None,
                                    "color": [255, 255, 255],
                                    "size": 18,
                                    "offset": [0, 0],
                                    "anchor": "start",
                                    "alignment": "center"
                                }
                            ]
                        }
                    }
                ],
                "interactionConfig": {
                    "tooltip": {
                        "fieldsToShow": {
                            "locations": [
                                {"name": address_col, "format": None},
                                {"name": "위도", "format": None},
                                {"name": "경도", "format": None}
                            ]
                        },
                        "compareMode": False,
                        "compareType": "absolute",
                        "enabled": True
                    },
                    "brush": {"size": 0.5, "enabled": False},
                    "geocoder": {"enabled": False},
                    "coordinate": {"enabled": False}
                },
                "layerBlending": "normal",
                "splitMaps": [],
                "animationConfig": {"currentTime": None, "speed": 1}
            }
        }
    }
    
    # Kepler.gl 맵 생성
    kepler_map = KeplerGl(height=600, config=config)
    kepler_map.add_data(data=map_data, name="locations")
    
    return kepler_map

# 메인 앱
st.title("📍 주소 → 위도/경도 변환기")
st.markdown("CSV 파일을 업로드하면 주소를 위도/경도로 자동 변환하고 지도에 시각화해드립니다!")

# 파일 업로드
uploaded_file = st.file_uploader("CSV 파일을 업로드하세요", type=['csv'])

if uploaded_file is not None:
    try:
        # 구분자 감지 및 파일 읽기
        file_content = uploaded_file.getvalue()
        separator = detect_separator(file_content)

        df = None
        separators_to_try = [separator, '\t', ',', ';', '|']

        for sep in separators_to_try:
            try:
                df = pd.read_csv(io.BytesIO(file_content), sep=sep, encoding='utf-8')
                if len(df.columns) > 1:
                    st.info(f"구분자 '{sep}' 사용하여 파일 읽기 성공")
                    break
            except:
                continue

        if df is None or len(df.columns) <= 1:
            for encoding in ['euc-kr', 'cp949']:
                for sep in separators_to_try:
                    try:
                        df = pd.read_csv(io.BytesIO(file_content), sep=sep, encoding=encoding)
                        if len(df.columns) > 1:
                            st.info(f"구분자 '{sep}', 인코딩 '{encoding}' 사용하여 파일 읽기 성공")
                            break
                    except:
                        continue
                if df is not None and len(df.columns) > 1:
                    break

        if df is None or len(df.columns) <= 1:
            st.error("파일을 읽을 수 없습니다. CSV 형식을 확인해주세요.")
            st.stop()
        
        st.subheader("📋 업로드된 데이터")
        st.dataframe(df.head())
        st.info(f"총 {len(df)}개 행, {len(df.columns)}개 칼럼")
        
        # 주소 칼럼 찾기
        address_col = find_address_column(df)
        
        if address_col:
            st.success(f"'{address_col}' 칼럼을 주소로 인식했습니다.")
            
            # 테스트 실행 버튼
            if st.button("🧪 테스트 실행 (처음 5개)", type="primary"):
                st.session_state.test_completed = False
                st.session_state.full_processing = False
                st.session_state.processed_data = None
                st.session_state.kepler_map = None
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 테스트 (처음 5개)
                st.subheader("🧪 테스트 결과")
                test_results = []
                
                for idx in range(min(5, len(df))):
                    address = df.iloc[idx][address_col]
                    if pd.notna(address):
                        status_text.text(f"테스트 중: {address}")
                        lat, lon = geocode_kakao(str(address))
                        test_results.append({
                            '주소': str(address)[:50],
                            '위도': lat,
                            '경도': lon,
                            '상태': '✅ 성공' if lat else '❌ 실패'
                        })
                        progress_bar.progress((idx + 1) / 5)
                        time.sleep(0.1)
                
                test_df = pd.DataFrame(test_results)
                st.dataframe(test_df)
                
                success_rate = len([r for r in test_results if r['위도']]) / len(test_results) * 100
                st.metric("테스트 성공률", f"{success_rate:.1f}%")
                
                # 테스트 완료 상태 설정
                st.session_state.test_completed = True
                st.session_state.test_data = df
                st.session_state.address_col = address_col
                
                st.markdown("---")
                st.subheader("💡 테스트 완료!")
                st.info(f"전체 {len(df)}개 주소 처리 예상 시간: 약 {len(df)*0.1/60:.1f}분")
            
            # 테스트 완료 후 전체 처리 버튼 표시
            if st.session_state.test_completed:
                st.markdown("### 🚀 전체 데이터 처리")
                
                # 전체 처리 버튼
                full_process_btn = st.button(
                    "🚀 전체 데이터 처리 시작", 
                    type="secondary",
                    key="full_process_button",
                    help="테스트가 완료된 후 전체 데이터를 처리합니다."
                )
                
                if full_process_btn:
                    st.session_state.full_processing = True
                
                # 전체 처리 실행
                if st.session_state.full_processing and st.session_state.processed_data is None:
                    df = st.session_state.test_data
                    address_col = st.session_state.address_col
                    
                    st.markdown("### 📊 전체 데이터 처리 중...")
                    
                    df_result = df.copy()
                    df_result['위도'] = None
                    df_result['경도'] = None
                    
                    # 진행률 표시를 위한 컨테이너
                    progress_container = st.container()
                    with progress_container:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                    
                    success_count = 0
                    
                    # 전체 데이터 처리
                    for idx in range(len(df)):
                        address = df.iloc[idx][address_col]
                        if pd.notna(address):
                            if idx % 50 == 0 or idx < 10:
                                status_text.text(f"처리 중 {idx+1}/{len(df)}: {str(address)[:30]}...")
                            
                            lat, lon = geocode_kakao(str(address))
                            df_result.at[idx, '위도'] = lat
                            df_result.at[idx, '경도'] = lon
                            
                            if lat:
                                success_count += 1
                            
                            progress_bar.progress((idx + 1) / len(df))
                            time.sleep(0.05)
                    
                    status_text.text(f"✅ 완료! {success_count}/{len(df)}개 성공 ({success_count/len(df)*100:.1f}%)")
                    
                    # 결과 저장 (세션 상태에 저장하여 재로딩 방지)
                    st.session_state.processed_data = df_result
                    st.session_state.address_col = address_col
                    
                    # Kepler.gl 지도 생성
                    st.session_state.kepler_map = create_kepler_map(df_result, address_col)
                
                # 처리 완료 후 결과 표시
                if st.session_state.processed_data is not None:
                    df_result = st.session_state.processed_data
                    address_col = st.session_state.address_col
                    
                    # === 🗺️ 지도와 표를 나란히 배치 ===
                    st.markdown("---")
                    st.subheader("📊 최종 결과 - 지도 시각화 및 데이터")
                    
                    # 2열 레이아웃 생성 (지도:표 = 2:1 비율, 간격 최소화)
                    col_map, col_table = st.columns([2, 1], gap="small")
                    
                    with col_map:
                        st.markdown("### 🗺️ 위치 지도")
                        
                        # Kepler.gl 지도 표시
                        if st.session_state.kepler_map:
                            keplergl_static(
                                st.session_state.kepler_map,
                                height=600,
                                width=None,  # 컨테이너 너비에 맞춤
                                center_map=False,
                                read_only=False
                            )
                            
                            # 지도 통계
                            successful_locations = df_result.dropna(subset=['위도', '경도'])
                            st.info(f"📍 지도에 표시된 위치: {len(successful_locations)}개")
                        else:
                            st.warning("표시할 위치 데이터가 없습니다.")
                    
                    with col_table:
                        st.markdown("### 📋 변환 결과")
                        
                        # CSV 다운로드 버튼을 오른쪽 상단에 배치
                        csv_buffer = io.StringIO()
                        df_result.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                        
                        st.download_button(
                            label="📥 전체 결과 CSV 다운로드",
                            data=csv_buffer.getvalue(),
                            file_name="geocoded_addresses.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                        
                        # 결과 표 표시 (스크롤 가능)
                        result_display = df_result[[address_col, '위도', '경도']].copy()
                        result_display.columns = ['주소', '위도', '경도']
                        
                        # 주소 텍스트 줄이기 (표시용)
                        result_display['주소'] = result_display['주소'].astype(str).str[:25] + "..."
                        
                        st.dataframe(
                            result_display,
                            height=450,  # 높이 조정
                            use_container_width=True
                        )
                        
                        # 통계 정보
                        st.markdown("### 📈 변환 통계")
                        total_count = len(df_result)
                        success_count = df_result['위도'].notna().sum()
                        fail_count = total_count - success_count
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("성공", success_count)
                        with col2:
                            st.metric("실패", fail_count)
                        
                        st.metric("성공률", f"{success_count/total_count*100:.1f}%")
                        
                        # 실패한 주소 목록 (있는 경우)
                        failed_addresses = df_result[df_result['위도'].isna()]
                        if len(failed_addresses) > 0:
                            with st.expander(f"❌ 변환 실패 주소 ({len(failed_addresses)}개)"):
                                for idx, row in failed_addresses.head(5).iterrows():
                                    st.text(f"• {str(row[address_col])[:35]}")
                                if len(failed_addresses) > 5:
                                    st.text(f"... 외 {len(failed_addresses)-5}개 더")
        else:
            st.error("주소 칼럼을 찾을 수 없습니다.")
            st.info("가능한 칼럼: " + ", ".join(df.columns))
            
            selected_col = st.selectbox("주소가 포함된 칼럼을 직접 선택하세요:", df.columns)
            if st.button("선택한 칼럼으로 진행"):
                st.rerun()
            
    except Exception as e:
        st.error(f"파일 처리 중 오류: {str(e)}")
        st.error("파일 형식을 다시 확인해주세요.")

# 사용법 안내
with st.expander("📖 사용 방법"):
    st.markdown("""
    ### 🚀 간단한 3단계
    1. **CSV 파일 업로드**: 주소가 포함된 CSV 파일 선택
    2. **테스트 실행**: 처음 5개 주소로 정상 작동 확인
    3. **전체 처리**: 테스트 성공 후 전체 데이터 변환 및 지도 시각화
    
    ### ✨ 주요 기능
    - **자동 구분자 감지**: 탭, 쉼표 등 자동 인식
    - **주소 칼럼 자동 찾기**: '주소', 'address' 등 자동 탐지
    - **Kepler.gl 지도**: GPU 가속 고성능 인터랙티브 지도
    - **미니멀 라이트 스타일**: 도로와 경계선만 표시하는 깔끔한 스타일
    - **실시간 진행률**: 처리 상황 실시간 확인
    - **즉시 다운로드**: 변환 완료 후 바로 CSV 다운로드
    
    ### 🗺️ Kepler.gl 지도 기능
    - **고성능 렌더링**: GPU 가속으로 대용량 데이터도 부드럽게 처리
    - **인터랙티브 툴팁**: 마커 클릭 시 상세 정보 표시
    - **줌/팬 기능**: 마우스와 터치로 자유로운 지도 탐색
    - **미니멀 스타일**: 라벨 없는 라이트 테마로 데이터에 집중
    """)

st.markdown("---")
st.markdown("🏙️ **도시 브랜딩 및 개발 프로젝트를 위한 위치 데이터 변환 및 시각화 도구**")
st.markdown("by Urban Designer | Powered by Kakao API, Streamlit & Kepler.gl")
