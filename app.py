import streamlit as st
import pandas as pd
import requests
import time
import io
import csv

# 페이지 설정
st.set_page_config(
    page_title="주소 → 좌표 변환기",
    page_icon="📍",
    layout="wide"
)

# 카카오 API 키
KAKAO_API_KEY = "5d4c572b337634c65d1d65fc68519085"

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
            text_content = file_content.decode('euc-kr')
    else:
        text_content = file_content
    
    lines = text_content.split('\n')[:5]
    separators = [',', '\t', ';', '|']
    
    for sep in separators:
        scores = []
        for line in lines:
            if line.strip():
                parts = line.split(sep)
                scores.append(len(parts))
        
        if scores:
            avg_cols = sum(scores) / len(scores)
            if avg_cols > 1:
                return sep
    return ','

def find_address_column(df):
    """주소 칼럼 자동 찾기"""
    possible_names = ['주소', 'address', 'addr', '도로명주소', '지번주소', 'road', '소재지']
    
    for col in df.columns:
        for name in possible_names:
            if name in col.lower():
                return col
    return None

# 메인 앱
st.title("📍 주소 → 위도/경도 변환기")
st.markdown("CSV 파일을 업로드하면 주소를 위도/경도로 자동 변환해드립니다!")

# 파일 업로드
uploaded_file = st.file_uploader("CSV 파일을 업로드하세요", type=['csv'])

if uploaded_file is not None:
    try:
        # 구분자 감지
        separator = detect_separator(uploaded_file.getvalue())
        df = pd.read_csv(uploaded_file, sep=separator)
        
        st.subheader("📋 업로드된 데이터")
        st.dataframe(df.head())
        st.info(f"총 {len(df)}개 행, {len(df.columns)}개 칼럼")
        
        # 주소 칼럼 찾기
        address_col = find_address_column(df)
        
        if address_col:
            st.success(f"'{address_col}' 칼럼을 주소로 인식했습니다.")
            
            if st.button("🧪 테스트 실행 (처음 5개)", type="primary"):
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
                
                # 테스트 결과 표시
                test_df = pd.DataFrame(test_results)
                st.dataframe(test_df)
                
                success_rate = len([r for r in test_results if r['위도']]) / len(test_results) * 100
                st.metric("테스트 성공률", f"{success_rate:.1f}%")
                
                # 전체 처리 여부 확인
                st.markdown("---")
                st.subheader("💡 테스트 완료!")
                st.info(f"전체 {len(df)}개 주소 처리 예상 시간: 약 {len(df)*0.1/60:.1f}분")
                
                if st.button("🚀 전체 데이터 처리하기", type="secondary"):
                    df_result = df.copy()
                    df_result['위도'] = None
                    df_result['경도'] = None
                    
                    success_count = 0
                    
                    with st.spinner('전체 데이터 처리 중...'):
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
                    
                    # 결과 표시
                    st.subheader("📊 최종 결과")
                    st.dataframe(df_result[['주소', '위도', '경도']].head(10))
                    
                    # 결과 다운로드
                    csv_buffer = io.StringIO()
                    df_result.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                    
                    st.download_button(
                        label="📥 결과 파일 다운로드 (.csv)",
                        data=csv_buffer.getvalue(),
                        file_name="geocoded_addresses.csv",
                        mime="text/csv"
                    )
        else:
            st.error("주소 칼럼을 찾을 수 없습니다.")
            st.info("가능한 칼럼: " + ", ".join(df.columns))
            
    except Exception as e:
        st.error(f"파일 처리 중 오류: {str(e)}")

# 사용법 안내
with st.expander("📖 사용 방법"):
    st.markdown("""
    1. CSV 파일을 준비하세요 ('주소' 칼럼 포함)
    2. 파일을 업로드하면 자동으로 처리됩니다
    3. 테스트 결과 확인 후 전체 처리를 진행하세요
    4. 완료되면 결과 파일을 다운로드하세요
    
    **특징:**
    - 자동 구분자 감지 (탭, 쉼표 등)
    - 주소 칼럼 자동 인식
    - 전체 데이터 처리 전 테스트 실행
    - 실시간 진행률 표시
    """)
