import streamlit as st
import gspread
import pandas as pd
from gspread_dataframe import set_with_dataframe
import datetime
import ast 
import os
import json # JSON 처리를 위해 import

# --- 1. 페이지 설정 및 구글 시트 연동 ---
st.set_page_config(page_title="행동강령 워크샵", layout="wide")

try:
    # --- (중요) 수정된 인증 블록 ---
    # 로컬(PC)에서 실행할 때: google-credentials.json 파일을 직접 사용
    credentials_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "google-credentials.json")

    if os.path.exists(credentials_path):
        gc = gspread.service_account(filename=credentials_path)
    
    # Streamlit Cloud에서 실행할 때: st.secrets에서 보안 비밀을 읽어 사용
    else:
        # st.secrets에서 "gcp_service_account"라는 키로 저장된 JSON 내용을 읽어옴
        creds_dict = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds_dict)
    # --- 수정된 블록 끝 ---

    # --- (중요) 여기에 구글 시트 파일의 '정확한 이름'을 입력하세요 ---
    GOOGLE_SHEET_NAME = "(DWG) 워크샵 응답" 
    
    sheet = gc.open(GOOGLE_SHEET_NAME).sheet1

except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"'{GOOGLE_SHEET_NAME}' 이름의 구글 시트 파일을 찾을 수 없습니다. [1단계] 설정을 확인하세요.")
    st.stop()
except Exception as e:
    st.error(f"구글 시트 연결 중 오류 발생: {e}")
    st.error("google-credentials.json 파일 / Streamlit Secrets 설정 / 시트 공유 상태를 확인하세요.")
    st.stop()


# --- 2. 세션 상태 초기화 ---
# (이하 코드는 이전과 동일합니다)
if 'submitted' not in st.session_state:
    st.session_state.submitted = False

keys_to_init = {
    'participant_name': "",
    'emotions': [], 'emotions_etc': "",
    'causes': [], 'causes_etc': "",
    'impacts': [], 'impacts_etc': "",
    'do1': "", 'do2': "", 'do3': "",
    'dont1': "", 'dont2': "", 'dont3': "",
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

def process_multiselect_column(df, column_name):
    def safe_literal_eval(s):
        try:
            if isinstance(s, list): return s
            if isinstance(s, str) and s.startswith('[') and s.endswith(']'):
                return ast.literal_eval(s)
            return []
        except (ValueError, SyntaxError): return []

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


# --- 4. 앱 메인 레이아웃 (사이드바) ---
st.sidebar.title("워크샵 메뉴")
mode = st.sidebar.radio(
    "모드를 선택하세요:",
    ("1. 워크샵 참여 (참가자용)", "2. 통계 대시보드 (진행자용)")
)

# --- 5. 모드 1: 워크샵 참여 (참가자용) ---
if mode == "1. 워크샵 참여 (참가자용)":

    if not st.session_state.submitted:
        st.title("[워크샵 자료집] 임직원 커뮤니케이션 및 행동강령 수립")
        st.caption("Powered by (주)디센트워킹그룹")
        st.info("워크샵 내용을 탭별로 작성하신 후, 마지막 탭에서 '제출하기' 버튼을 눌러주세요.")
        st.text_input("소속/이름을 입력하세요 (예: A팀 홍길동)", key='participant_name')

        tab1, tab2, tab3 = st.tabs(["1. 문제 공감 (As-Is)", "2. 방향 설계 (To-Be)", "3. 실천 계획 (Action Plan)"])

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

        with tab2:
            st.subheader("2. 방향 설계: 우리가 원하는 모습 (To-Be)")
            st.info("💡 1부에서 도출된 문제점을 해결하기 위한 구체적인 '소통 원칙(Do & Don't)'을 수립합니다.")
            st.markdown("### 2-1. [워크시트] 행동강령(Action Guide) 수립하기")
            st.markdown("#### [Do: 우리가 반드시 실천할 행동]")
            st.text_input("Do 1:", placeholder="예: 협업 요청 시, '배경'과 '마감일'을 반드시 명확히 전달한다.", key='do1')
            st.text_input("Do 2:", key='do2')
            st.text_input("Do 3:", key='do3')
            st.markdown("#### [Don't: 우리가 반드시 지양할 행동]")
            st.text_input("Don't 1:", placeholder="예: 요청을 확인했으면 '확인했다'고 즉시 답한다. 침묵하지 않는다.", key='dont1')
            st.text_input("Don't 2:", key='dont2')
            st.text_input("Don't 3:", key='dont3')

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
                        new_row = [
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            st.session_state.participant_name,
                            str(st.session_state.emotions), str(st.session_state.emotions_etc),
                            str(st.session_state.causes), str(st.session_state.causes_etc),
                            str(st.session_state.impacts), str(st.session_state.impacts_etc),
                            st.session_state.do1, st.session_state.do2, st.session_state.do3,
                            st.session_state.dont1, st.session_state.dont2, st.session_state.dont3,
                            st.session_state.my_plan, st.session_state.team_plan
                        ]
                        sheet.append_row(new_row)
                        st.session_state.submitted = True
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"제출 중 오류가 발생했습니다: {e}")

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

# --- 6. 모드 2: 통계 대시보드 (진행자용) ---
elif mode == "2. 통계 대시보드 (진행자용)":
    st.title("📊 실시간 통계 대시보드 (진행자용)")
    try:
        df = load_data()
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        st.stop()

    if st.button("새로 고침"):
        st.cache_data.clear()
        st.experimental_rerun()
    
    if df.empty:
        st.warning("아직 제출된 응답이 없습니다.")
    else:
        st.subheader(f"📈 전체 응답 현황 (총 {len(df)}명 응답)")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### 1. 공감된 감정")
            emotion_counts = process_multiselect_column(df, 'emotions')
            if not emotion_counts.empty: st.bar_chart(emotion_counts)
        with col2:
            st.markdown("#### 2. 진단된 문제 원인")
            cause_counts = process_multiselect_column(df, 'causes')
            if not cause_counts.empty: st.bar_chart(cause_counts)
        with col3:
            st.markdown("#### 3. 예상되는 악영향")
            impact_counts = process_multiselect_column(df, 'impacts')
            if not impact_counts.empty: st.bar_chart(impact_counts)
        
        st.divider()
        st.subheader("📝 행동강령 및 실천 계획안")
        columns_to_show = ['name', 'do1', 'dont1', 'my_plan', 'team_plan']
        available_columns = [col for col in columns_to_show if col in df.columns]
        if available_columns: st.dataframe(df[available_columns], use_container_width=True)

        st.divider()
        st.subheader("📋 전체 원본 데이터 (Raw Data)")
        st.dataframe(df, use_container_width=True)