# ─────────── 지도 & 결과 컬럼 구역 ───────────
col_map, col_table = st.columns([2, 1], gap="small")

# ====================== ① 지도 컬럼 ======================
with col_map:
    st.markdown("### 🌃 위치 지도 (Dark Theme)")

    # ▸ 1) 지도 표시
    if st.session_state.map_obj:
        st_folium(
            st.session_state.map_obj, 
            height=600, 
            width=None,
            returned_objects=[],
            key="main_map"
        )
    else:
        st.warning("표시할 위치 데이터가 없습니다.")

    # ▸ 2) 지도 아래 “마커 스타일” 위젯 배치
    st.markdown("---")               # 시각적 구분선
    st.subheader("🎨 마커 스타일")     # 섹션 제목

    # 한 줄 4칸 (색상모드 · 색/칼럼 · 컬러맵 · 크기 슬라이더) + 적용버튼
    row1_col1, row1_col2, row1_col3, row1_col4, apply_col = st.columns([2,2,2,2,1])

    # 색상 모드
    with row1_col1:
        st.session_state.color_mode = st.selectbox(
            "색상 모드",
            ["단일 색상", "데이터 기반 색상"],
            index = 0 if st.session_state.color_mode=="단일 색상" else 1,
            key="color_mode_select"
        )

    # 단일 색상 ⇔ 데이터 기반 색상
    if st.session_state.color_mode == "단일 색상":
        with row1_col2:
            st.session_state.marker_color = st.color_picker(
                "마커 색상",
                st.session_state.marker_color,
                key="marker_color_picker"
            )
        # 컬러맵 선택 숨김
        row1_col3.empty()

    else:  # 데이터 기반
        num_cols = [c for c in result.select_dtypes(np.number).columns
                    if c not in ["위도","경도"]]
        with row1_col2:
            st.session_state.color_col = st.selectbox(
                "기준 칼럼", num_cols, key="color_col_select")
        with row1_col3:
            st.session_state.cmap_name = st.selectbox(
                "컬러맵",
                ["Reds","Blues","Greens","Viridis","Plasma",
                 "coolwarm","RdYlBu"],
                key="cmap_select")

    # 마커 크기 슬라이더
    with row1_col4:
        st.session_state.marker_size = st.slider(
            "마커 크기",
            min_value=3, max_value=15,
            value=st.session_state.marker_size,
            key="marker_size_slider"
        )

    # 적용 버튼
    with apply_col:
        if st.button("적용", key="apply_style"):
            # 지도 다시 생성 후 리렌더
            st.session_state.map_obj = build_map(result, addr_c)
            st.experimental_rerun()
