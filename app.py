import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import set_with_dataframe
import datetime
import ast 
import os
import json
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from konlpy.tag import Okt # 한글 형태소 분석기

# --- 0. 고정 설정: 핵심가치 ---
# (중요) 이곳에 회사의 실제 핵심가치를 입력하세요.
CORE_VALUES = ["(가치 선택)", "존중", "탁월함", "성장", "협력", "자율", "투명성"]


# --- 1. 페이지 설정 및 구글 시트 연동 ---
st.set_page_config(page_title="행동강령 워크샵", layout="wide")

try:
    # 로컬(PC) vs Streamlit Cloud(배포) 인증 분기
    credentials_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "google-credentials.json")

    if os.path.exists(credentials_path):
        gc = gspread.service_account(filename=credentials_path)
    else:
        creds_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds_dict)

    # 시트 이름 (수정됨)
    GOOGLE_SHEET_NAME = "(DWG) 워크샵 응답" 
    try:
        sheet = gc.open(GOOGLE_SHEET_NAME).sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        # 이전 이름으로 한번 더 시도 (하위 호환)
        sheet = gc.open("워크샵 응답").sheet1
        GOOGLE_SHEET_NAME = "워크샵 응답" # 찾은 이름으로 고정

except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"'{GOOGLE_SHEET_NAME}' 또는 '워크샵 응답' 시트를 찾을 수 없습니다.")
    st.stop()
except Exception as e:
    st.error(f"구글 시트 연결 중 오류 발생: {e}")
    st.error("google-credentials.json 파일 / Streamlit Secrets 설정 / 시트 공유 상태를 확인하세요.")
    st.stop()

# --- 2. 세션 상태 초기화 (구조 변경됨) ---
if 'submitted' not in st.session_state:
    st.session_state.submitted = False

keys_to_init = {
    'participant_name': "",
    'emotions': [], 'emotions_etc': "",
    'causes': [], 'causes_etc': "",
    'impacts': [], 'impacts_etc': "",
    'value1': CORE_VALUES[0], 'value1_do': "", 'value1_dont': "",
    'value2': CORE_VALUES[0], 'value2_do': "", 'value2_dont': "",
    'my_plan': "", 'team_plan': ""
}
for key, default_value in keys_to_init.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- 3. 헬퍼 함수 (데이터 로드 및 처리) ---
@st.cache_data(ttl=600)
def load_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df

def safe_literal_eval(s):
    try:
        if isinstance(s, list): return s
        if isinstance(s, str) and s.startswith('[') and s.endswith(']'):
            return ast.literal_eval(s)
        return []
    except (ValueError, SyntaxError): return []

def process_multiselect_column(df, column_name):
    if df.empty or column_name not in df.columns:
        return pd.Series(dtype=int)

    exploded = df[column_name].apply(safe_literal_eval).explode()
    
    etc_column_name = f"{column_name}_etc"
    if etc_column_name in df.columns:
        etc_responses = df[etc_column_name][df[etc_column_name].str.strip() != ""].apply(lambda x: f"(기타) {x}")
        combined = pd.concat([exploded, etc_responses], ignore_index=True)
    else:
        combined = exploded
    return combined.dropna().value_counts()

# --- [NEW] 워드 클라우드 생성 함수 ---
@st.cache_data
def generate_wordcloud(text_data):
    """텍스트 데이터로 워드 클라우드 이미지를 생성합니다."""
    
    # 1. Okt 형태소 분석기로 명사만 추출
    okt = Okt()
    all_nouns = []
    for text in text_data:
        if pd.isna(text) or text.strip() == "":
            continue
        nouns = okt.nouns(str(text))
        all_nouns.extend([n for n in nouns if len(n) > 1]) # 1글자 명사 제외
    
    if not all_nouns:
        return None # 생성할 단어 없음
        
    # 2. 폰트 경로 설정 (클라우드/로컬 자동 감지)
    font_path_cloud = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
    font_path_windows = 'C:/Windows/Fonts/malgun.ttf'
    font_path_mac = '/System/Library/Fonts/Supplemental/AppleGothic.ttf'
    
    if os.path.exists(font_path_cloud):
        font_path = font_path_cloud
    elif os.path.exists(font_path_windows):
        font_path = font_path_windows
    elif os.path.exists(font_path_mac):
        font_path = font_path_mac
    else:
        st.error("한글 폰트 파일을 찾을 수 없습니다. (NanumGothic / Malgun Gothic / AppleGothic)")
        return None

    # 3. 워드 클라우드 생성
    wc = WordCloud(
        font_path=font_path,
        width=800,
        height=400,
        background_color='white',
        colormap='viridis'
    ).generate(' '.join(all_nouns))
    
    # 4. Matplotlib으로 이미지 그리기
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    return fig


# --- 4. 앱 메인 레이아웃 (사이드바) ---
st.sidebar.title("워크샵 메뉴")
mode = st.sidebar.radio(
    "모드를 선택하세요:",
    ("1. 워크샵 참여 (참가자용)", "2. 통계 대시보드 (진행자용)")
)

# --- ================================== ---
# --- 5. 모드 1: 워크샵 참여 (참가자용) ---
# --- ================================== ---
if mode == "1. 워크샵 참여 (참가자용)":

    if not st.session_state.submitted:
        # --- [참여 폼] ---
        st.title("[워크샵 자료집] 임직원 커뮤니케이션 및 행동강령 수립")
        st.caption(f"Powered by (주)디센트워킹그룹 | Target Sheet: {GOOGLE_SHEET_NAME}")
        st.info("워크샵 내용을 탭별로 작성하신 후, 마지막 탭에서 '제출하기' 버튼을 눌러주세요.")
        st.text_input("소속/이름을 입력하세요 (예: A팀 홍길동)", key='participant_name')

        tab1, tab2, tab3 = st.tabs(["1. 문제 공감 (As-Is)", "2. 방향 설계 (To-Be)", "3. 실천 계획 (Action Plan)"])

        # --- 탭 1: 문제 공감 (이전과 동일) ---
        with tab1:
            st.subheader("1. 문제 공감: 우리의 현주소 (As-Is)")
            st.markdown("### 1-1. 롤 플레잉 시나리오 (예시)")
            with st.expander("상황 1: 협업 요청"): st.markdown("...")
            with st.expander("상황 2: 보고 및 피드백"): st.markdown("...")
            st.divider()
            st.markdown("### 1-2. [워크시트] 문제 공감하기 (선택형)")
            st.subheader("1. [감정] 어떤 '감정'을 느꼈나요?")
            st.multiselect("감정 선택", ['답답함', '무시당하는 느낌', '막막함', '억울함', '불편함', '공감됨'], key='emotions', label_visibility="collapsed")
            st.text_input("기타 감정:", key='emotions_etc')
            st.subheader("2. [원인] 이 문제가 '반복'되는 가장 큰 이유는?")
            st.multiselect("원인 선택", ['서로의 업무/일정을 몰라서', '명확한 R&R이 없어서', '피드백 문화가 부재해서', '솔직하게 말하기 어려워서 (심리적 안전감 부족)', '너무 바빠서 (물리적 시간 부족)'], key='causes', label_visibility="collapsed")
            st.text_input("기타 원인:", key='causes_etc')
            st.subheader("3. [영향] 이 문제가 해결되지 않으면, 어떤 '악영향'을 미칠까요?")
            st.multiselect("악영향 선택", ['업무/프로젝트 지연', '불필요한 감정 소모', '핵심 인력 퇴사 (번아웃)', '제품/서비스 품질 저하', '부서 간 이기주의 심화'], key='impacts', label_visibility="collapsed")
            st.text_input("기타 악영향:", key='impacts_etc')

        # --- 탭 2: 방향 설계 (업그레이드됨) ---
        with tab2:
            st.subheader("2. 방향 설계: 우리가 원하는 모습 (To-Be)")
            st.info("💡 1부의 문제점을 해결하기 위해, 우리 회사의 **핵심가치**에 기반한 행동강령을 수립합니다.")
            
            st.markdown("### 2-1. [워크시트] 핵심가치 기반 행동강령 (1)")
            st.selectbox("연결할 핵심가치 (1)", CORE_VALUES, key='value1')
            st.text_input("[Do] 위 가치를 실천하기 위해 우리가 해야 할 행동은?", 
                          placeholder="예: 협업 요청 시, '배경'과 '마감일'을 반드시 명확히 전달한다.", 
                          key='value1_do')
            st.text_input("[Don't] 위 가치를 훼손하지 않기 위해 하지 말아야 할 행동은?", 
                          placeholder="예: 요청을 확인했으면 '확인했다'고 즉시 답한다. 침묵하지 않는다.", 
                          key='value1_dont')

            st.divider()
            
            st.markdown("### 2-2. [워크시트] 핵심가치 기반 행동강령 (2)")
            st.selectbox("연결할 핵심가치 (2)", CORE_VALUES, key='value2')
            st.text_input("[Do] 위 가치를 실천하기 위해 우리가 해야 할 행동은?", key='value2_do')
            st.text_input("[Don't] 위 가치를 훼손하지 않기 위해 하지 말아야 할 행동은?", key='value2_dont')

        # --- 탭 3: 실천 계획 및 제출 ---
        with tab3:
            st.subheader("3. 실천 계획: 즉시 행동하기 (Action Plan)")
            st.info("🚀 현업에 돌아가서 '나'부터, '우리 팀'부터 바로 적용할 액션 플랜 1가지를 작성해 보세요.")
            st.markdown("### 3-1. [워크시트] 나의 실천 선언문")
            st.text_area("[My Action Plan] '나'부터 즉시 실천할 한 가지", placeholder="...", key='my_plan')
            st.text_area("[Our Team's Action Plan] '우리 팀'이 먼저 시도할 한 가지", placeholder="...", key='team_plan')
            st.divider()
            
            if st.button("워크샵 결과 제출하기", type="primary", use_container_width=True):
                if not st.session_state.participant_name.strip():
                    st.error("소속/이름을 입력해야 제출할 수 있습니다.")
                else:
                    try:
                        # [중요] 새로운 16개 열 구조에 맞춰 데이터 전송
                        new_row = [
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            st.session_state.participant_name,
                            str(st.session_state.emotions), str(st.session_state.emotions_etc),
                            str(st.session_state.causes), str(st.session_state.causes_etc),
                            str(st.session_state.impacts), str(st.session_state.impacts_etc),
                            st.session_state.value1,
                            st.session_state.value1_do,
                            st.session_state.value1_dont,
                            st.session_state.value2,
                            st.session_state.value2_do,
                            st.session_state.value2_dont,
                            st.session_state.my_plan,
                            st.session_state.team_plan
                        ]
                        sheet.append_row(new_row)
                        st.session_state.submitted = True
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"제출 중 오류가 발생했습니다: {e}")
                        st.error("구글 시트의 1행(헤더)이 [1단계]에서 안내한 16개 열과 정확히 일치하는지 확인하세요.")

    else:
        # --- [제출 완료 및 인쇄용 리포트] ---
        st.success("✅ 제출이 완료되었습니다. 워크샵에 참여해주셔서 감사합니다.")
        st.title("워크샵 결과 리포트 (인쇄용)")
        st.caption(f"작성자: {st.session_state.participant_name}")
        st.markdown("---")
        # (이하 생략 - 이전 코드와 동일한 리포트 화면)
        if st.button("새로 작성하기 (다른 참가자용)"):
            st.session_state.submitted = False
            for key in keys_to_init.keys(): st.session_state[key] = keys_to_init[key]
            st.experimental_rerun()

# --- ======================================= ---
# --- 6. 모드 2: 통계 대시보드 (진행자용) ---
# --- ======================================= ---
elif mode == "2. 통계 대시보드 (진행자용)":
    
    st.title("📊 실시간 통계 대시보드 (진행자용)")
    st.info("참가자들이 제출하는 현황이 실시간으로 집계됩니다.")

    try:
        df_original = load_data() 
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        st.stop()

    if st.button("새로 고침"):
        st.cache_data.clear()
        st.experimental_rerun()
    
    if df_original.empty:
        st.warning("아직 제출된 응답이 없습니다.")
    else:
        # --- 비식별화 로직 ---
        df_display = df_original.copy()
        def anonymize_name(name_str):
            name_str = str(name_str)
            if "팀" in name_str:
                parts = name_str.split(" ")
                if parts[0].endswith("팀"):
                    return f"{parts[0]} ***"
            return "참가자 ***" 
        if 'name' in df_display.columns:
            df_display['name'] = df_display['name'].apply(anonymize_name)
        # --- 비식별화 로직 끝 ---

        # --- 위험 경로 분석 (원본 df_original 사용) ---
        st.subheader("🚨 주요 위험 경로 분석 (Path Analysis)")
        st.caption("참가자들이 선택한 [원인]과 [영향]을 조합하여 가장 빈번하게 나타난 '위험 경로'를 표시합니다.")

        if 'causes' in df_original.columns:
            df_original['causes_list'] = df_original['causes'].apply(safe_literal_eval)
        else:
            df_original['causes_list'] = [[] for _ in range(len(df_original))]
        if 'impacts' in df_original.columns:
            df_original['impacts_list'] = df_original['impacts'].apply(safe_literal_eval)
        else:
            df_original['impacts_list'] = [[] for _ in range(len(df_original))]

        risk_paths = {
            "심리적 안전감 부족 → 핵심 인력 퇴사": ('솔직하게 말하기 어려워서 (심리적 안전감 부족)', '핵심 인력 퇴사 (번아웃)'),
            "피드백 부재 → 불필요한 감정 소모": ('피드백 문화가 부재해서', '불필요한 감정 소모'),
            "R&R 불명확 → 부서 간 이기주의": ('명확한 R&R이 없어서', '부서 간 이기주의 심화'),
            "정보 불투명 → 업무/프로젝트 지연": ('서로의 업무/일정을 몰라서', '업무/프로젝트 지연')
        }
        
        path_counts = {}
        for path_name, (cause, impact) in risk_paths.items():
            count = len(df_original[
                df_original['causes_list'].apply(lambda x: cause in x) & 
                df_original['impacts_list'].apply(lambda x: impact in x)
            ])
            path_counts[path_name] = count
        sorted_paths = sorted(path_counts.items(), key=lambda item: item[1], reverse=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            if len(sorted_paths) > 0 and sorted_paths[0][1] > 0:
                st.metric(label=f"[위험 경로 1위] {sorted_paths[0][0]}", value=f"{sorted_paths[0][1]} 건", delta="심각", delta_color="inverse")
            else:
                st.info("아직 주요 위험 경로는 발견되지 않았습니다.")
        with col2:
            if len(sorted_paths) > 1 and sorted_paths[1][1] > 0:
                st.metric(label=f"[위험 경로 2위] {sorted_paths[1][0]}", value=f"{sorted_paths[1][1]} 건", delta="경고", delta_color="inverse")
        with col3:
            if len(sorted_paths) > 2 and sorted_paths[2][1] > 0:
                st.metric(label=f"[위험 경로 3위] {sorted_paths[2][0]}", value=f"{sorted_paths[2][1]} 건", delta="주의", delta_color="inverse")
        
        st.divider()
        # --- 위험 경로 분석 끝 ---

        st.subheader(f"📈 전체 응답 현황 (총 {len(df_original)}명 응답)")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### 1. 공감된 감정")
            emotion_counts = process_multiselect_column(df_original, 'emotions')
            if not emotion_counts.empty: st.bar_chart(emotion_counts)
        with col2:
            st.markdown("#### 2. 진단된 문제 원인")
            cause_counts = process_multiselect_column(df_original, 'causes')
            if not cause_counts.empty: st.bar_chart(cause_counts)
        with col3:
            st.markdown("#### 3. 예상되는 악영향")
            impact_counts = process_multiselect_column(df_original, 'impacts')
            if not impact_counts.empty: st.bar_chart(impact_counts)
        
        st.divider()

        # --- [NEW] 워드 클라우드 섹션 ---
        st.subheader("☁️ 행동강령 핵심 키워드 (Word Cloud)")
        st.caption("참가자들이 '행동강령(Do/Don't)'에서 가장 많이 언급한 명사 키워드입니다.")
        
        # 워드 클라우드 생성을 위해 텍스트 데이터 취합 (새로운 컬럼명 사용)
        text_columns = ['value1_do', 'value1_dont', 'value2_do', 'value2_dont']
        # 해당 컬럼이 df_original에 있는지 확인
        available_text_columns = [col for col in text_columns if col in df_original.columns]
        
        if not available_text_columns:
            st.warning("행동강령 데이터가 없습니다. (시트 헤더 확인 필요)")
        else:
            all_text_data = pd.concat([df_original[col] for col in available_text_columns]).dropna()
            if all_text_data.empty:
                st.info("아직 분석할 행동강령 텍스트가 없습니다.")
            else:
                wordcloud_fig = generate_wordcloud(all_text_data)
                if wordcloud_fig:
                    st.pyplot(wordcloud_fig)
        
        st.divider()

        # --- [NEW] 행동강령 표시 (새로운 컬럼명 사용) ---
        st.subheader("📝 행동강령 및 실천 계획안 (비식별화)")
        columns_to_show = ['name', 'value1', 'value1_do', 'value1_dont', 'value2', 'value2_do', 'value2_dont', 'my_plan', 'team_plan']
        available_columns = [col for col in columns_to_show if col in df_display.columns]
        
        if not available_columns:
            st.warning("표시할 데이터가 없습니다. (컬럼명 확인 필요)")
        else:
            st.dataframe(df_display[available_columns], use_container_width=True) 

        st.divider()
        st.subheader("📋 전체 원본 데이터 (비식별화)")
        st.dataframe(df_display, use_container_width=True)