import re
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI


# =========================================================
# 1. 페이지 기본 설정
# =========================================================
st.set_page_config(
    page_title="실시간 응급실 혼잡도 안내",
    page_icon="🏥",
    layout="wide",
)

st.title("🏥 실시간 응급실 혼잡도 안내")
st.caption("현재 위치와 필요한 진료 분야를 바탕으로 주변 응급실의 가용 병상을 확인합니다.")


# =========================================================
# 2. 반드시 확인해야 하는 안전 안내
# =========================================================
st.error(
    """
    **생명이 위급한 상황에서는 이 앱을 사용해 병원을 비교하지 말고 즉시 119에 연락하세요.**

    가슴 통증, 호흡 곤란, 의식 저하, 심한 출혈, 마비, 경련, 심한 알레르기 반응,
    자살·자해 위험 등이 있으면 바로 119에 도움을 요청해야 합니다.
    """
)

st.info(
    """
    이 앱의 혼잡도는 **실제 대기시간이 아니라 가용 병상 정보를 바탕으로 계산한 추정치**입니다.
    출발 전 해당 응급실에 전화하여 진료 가능 여부를 다시 확인하세요.
    """
)


# =========================================================
# 3. API 기본 설정
# =========================================================

# 공공데이터포털 응급실 실시간 가용병상 API
EMERGENCY_API_URL = (
    "https://apis.data.go.kr/B552657/"
    "ErmctInfoInqireService/"
    "getEmrrmRltmUsefulSckbdInfoInqire"
)

# Solar API 접속 주소
SOLAR_BASE_URL = "https://api.upstage.ai/v1"

# 모델 이름은 요청한 이름을 그대로 사용합니다.
SOLAR_MODEL = "solar-open2"


# =========================================================
# 4. 지역명 변환 자료
# =========================================================

# 사용자가 "서울 강남구"처럼 줄여 입력해도
# API가 요구하는 공식 시도명으로 바꾸기 위한 자료입니다.
SIDO_ALIASES = {
    "서울": "서울특별시",
    "서울시": "서울특별시",
    "서울특별시": "서울특별시",

    "부산": "부산광역시",
    "부산시": "부산광역시",
    "부산광역시": "부산광역시",

    "대구": "대구광역시",
    "대구시": "대구광역시",
    "대구광역시": "대구광역시",

    "인천": "인천광역시",
    "인천시": "인천광역시",
    "인천광역시": "인천광역시",

    "광주": "광주광역시",
    "광주시": "광주광역시",
    "광주광역시": "광주광역시",

    "대전": "대전광역시",
    "대전시": "대전광역시",
    "대전광역시": "대전광역시",

    "울산": "울산광역시",
    "울산시": "울산광역시",
    "울산광역시": "울산광역시",

    "세종": "세종특별자치시",
    "세종시": "세종특별자치시",
    "세종특별자치시": "세종특별자치시",

    "경기": "경기도",
    "경기도": "경기도",

    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",

    "충북": "충청북도",
    "충청북도": "충청북도",

    "충남": "충청남도",
    "충청남도": "충청남도",

    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전북특별자치도": "전북특별자치도",

    "전남": "전라남도",
    "전라남도": "전라남도",

    "경북": "경상북도",
    "경상북도": "경상북도",

    "경남": "경상남도",
    "경상남도": "경상남도",

    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주특별자치도": "제주특별자치도",
}


# =========================================================
# 5. 진료 분야별로 참고할 API 항목
# =========================================================

# 이 API에는 진료과별 대기시간이 없습니다.
# 대신 사용자가 선택한 분야와 관련된 병상이나 시설을 참고합니다.
DEPARTMENT_RULES = {
    "일반 응급": {
        "description": "응급실 가용 병상을 중심으로 확인합니다.",
        "numeric_fields": [],
        "yn_fields": [],
    },
    "내과 응급": {
        "description": "응급실과 내과중환자실 가용 병상을 함께 확인합니다.",
        "numeric_fields": ["내과중환자실", "일반중환자실"],
        "yn_fields": [],
    },
    "외과 응급": {
        "description": "수술실과 외과중환자실 가용 여부를 함께 확인합니다.",
        "numeric_fields": ["수술실", "외과중환자실"],
        "yn_fields": [],
    },
    "정형외과·골절": {
        "description": "수술실과 정형외과 입원실 정보를 함께 확인합니다.",
        "numeric_fields": ["수술실", "정형외과입원실"],
        "yn_fields": ["CT"],
    },
    "신경과·뇌졸중": {
        "description": "신경계 중환자 병상과 CT·MRI 가용 여부를 확인합니다.",
        "numeric_fields": [
            "신경중환자실",
            "신경과입원실",
            "신경외과중환자실",
        ],
        "yn_fields": ["CT", "MRI", "조영촬영기"],
    },
    "흉부·심장 응급": {
        "description": "흉부중환자실과 관련 장비 가용 여부를 확인합니다.",
        "numeric_fields": ["흉부중환자실", "일반중환자실"],
        "yn_fields": ["CT", "인공호흡기"],
    },
    "소아 응급": {
        "description": "소아용 인공호흡기와 소아 당직 연락처를 확인합니다.",
        "numeric_fields": ["신생아중환자실"],
        "yn_fields": ["소아인공호흡기", "인큐베이터"],
    },
    "외상 응급": {
        "description": "외상중환자 병상과 수술실, CT 가용 여부를 확인합니다.",
        "numeric_fields": ["외상중환자실", "수술실"],
        "yn_fields": ["CT", "조영촬영기"],
    },
    "화상 응급": {
        "description": "화상중환자 병상과 일반 중환자실 정보를 확인합니다.",
        "numeric_fields": ["화상중환자실", "일반중환자실"],
        "yn_fields": [],
    },
    "약물 중독": {
        "description": "약물중환자 병상과 인공호흡기 가용 여부를 확인합니다.",
        "numeric_fields": ["약물중환자실", "일반중환자실"],
        "yn_fields": ["인공호흡기"],
    },
    "산부인과·신생아": {
        "description": "신생아중환자실과 인큐베이터 가용 여부를 확인합니다.",
        "numeric_fields": ["신생아중환자실"],
        "yn_fields": ["인큐베이터"],
    },
}


# =========================================================
# 6. XML 태그와 화면 표시 이름 연결
# =========================================================
XML_FIELD_MAP = {
    "hpid": "기관코드",
    "dutyname": "병원명",
    "dutytel3": "응급실전화",
    "hvidate": "입력일시",

    "hvec": "응급실",
    "hvoc": "수술실",
    "hvcc": "신경중환자실",
    "hvncc": "신생아중환자실",
    "hvccc": "흉부중환자실",
    "hvicc": "일반중환자실",
    "hvgc": "입원실",

    "hv2": "내과중환자실",
    "hv3": "외과중환자실",
    "hv4": "정형외과입원실",
    "hv5": "신경과입원실",
    "hv6": "신경외과중환자실",
    "hv7": "약물중환자실",
    "hv8": "화상중환자실",
    "hv9": "외상중환자실",

    "hvctayn": "CT",
    "hvmriayn": "MRI",
    "hvangioayn": "조영촬영기",
    "hvventiayn": "인공호흡기",
    "hvamyn": "구급차",
    "hv10": "소아인공호흡기",
    "hv11": "인큐베이터",

    "hv1": "당직의연락처",
    "hv12": "소아당직의연락처",
}


# =========================================================
# 7. 자주 사용하는 보조 함수
# =========================================================
def safe_text(element, tag_name, default=""):
    """
    XML 안에서 원하는 태그의 글자를 안전하게 읽습니다.
    태그가 없거나 값이 비어 있으면 기본값을 돌려줍니다.
    """
    child = element.find(tag_name)

    if child is None or child.text is None:
        return default

    return child.text.strip()


def to_int(value, default=0):
    """
    XML로 받은 숫자는 글자 형태입니다.
    숫자로 바꿀 수 있으면 정수로 바꾸고,
    바꿀 수 없으면 기본값을 사용합니다.
    """
    if value is None:
        return default

    text = str(value).strip()

    if text == "":
        return default

    try:
        return int(float(text))
    except (ValueError, TypeError):
        return default


def normalize_yes_no(value):
    """
    Y, N 값을 보기 쉬운 형태로 정리합니다.
    """
    text = str(value).strip().upper()

    if text == "Y":
        return "가능"

    if text == "N":
        return "불가"

    return "정보 없음"


def parse_location(location_text):
    """
    '서울 강남구 역삼동' 같은 입력에서
    시도와 시군구를 찾아냅니다.

    이 앱은 별도의 지도·주소 검색 API를 사용하지 않으므로
    사용자가 시도와 시군구를 함께 입력해야 합니다.
    """
    cleaned = re.sub(r"[,/]", " ", location_text.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)

    found_sido = None
    found_alias = None

    # 긴 이름부터 확인해야 '서울'보다 '서울특별시'가 먼저 잡힙니다.
    aliases = sorted(SIDO_ALIASES.keys(), key=len, reverse=True)

    for alias in aliases:
        if alias in cleaned:
            found_sido = SIDO_ALIASES[alias]
            found_alias = alias
            break

    if not found_sido:
        return None, None

    # 시도명을 제거한 나머지 글자에서 시군구를 찾습니다.
    remainder = cleaned.replace(found_alias, " ", 1)
    tokens = remainder.split()

    sigungu = None

    # 일반적인 시군구 이름을 찾습니다.
    for token in tokens:
        if token.endswith(("시", "군", "구")):
            sigungu = token
            break

    # 세종시는 API에 시군구 값이 별도로 필요할 수 있어
    # 기본적으로 세종특별자치시를 사용합니다.
    if found_sido == "세종특별자치시" and not sigungu:
        sigungu = "세종특별자치시"

    return found_sido, sigungu


def build_api_url(api_key, sido, sigungu, page_no=1, rows=100):
    """
    공공데이터 API 요청 주소를 만듭니다.

    공공데이터포털 인증키가 이미 URL 인코딩된 상태일 수 있으므로
    먼저 풀어 준 다음 다시 한 번 안전하게 인코딩합니다.
    """
    decoded_key = urllib.parse.unquote(str(api_key).strip())

    params = {
        "serviceKey": decoded_key,
        "STAGE1": sido,
        "STAGE2": sigungu,
        "pageNo": page_no,
        "numOfRows": rows,
    }

    query_string = urllib.parse.urlencode(params)
    return f"{EMERGENCY_API_URL}?{query_string}"


# 1분 동안 같은 지역의 결과를 캐시에 저장합니다.
# API를 너무 자주 호출하지 않도록 하기 위한 기능입니다.
@st.cache_data(ttl=60, show_spinner=False)
def fetch_emergency_rooms(api_key, sido, sigungu):
    """
    국립중앙의료원 API에서 응급실 가용병상 정보를 가져옵니다.
    """
    url = build_api_url(
        api_key=api_key,
        sido=sido,
        sigungu=sigungu,
        page_no=1,
        rows=100,
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/xml",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            xml_bytes = response.read()

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"공공데이터 서버가 요청을 처리하지 못했습니다. HTTP 상태: {error.code}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            "공공데이터 서버에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요."
        ) from error

    except TimeoutError as error:
        raise RuntimeError(
            "공공데이터 서버의 응답 시간이 너무 오래 걸립니다. 잠시 후 다시 시도해 주세요."
        ) from error

    try:
        root = ET.fromstring(xml_bytes)

    except ET.ParseError as error:
        preview = xml_bytes.decode("utf-8", errors="ignore")[:300]

        raise RuntimeError(
            "공공데이터 응답을 XML로 읽지 못했습니다. "
            f"인증키 또는 API 상태를 확인해 주세요. 응답 일부: {preview}"
        ) from error

    # API 오류 메시지를 확인합니다.
    result_code = root.findtext(".//resultCode")
    result_message = (
        root.findtext(".//resultMsg")
        or root.findtext(".//resultMag")
        or ""
    )

    if result_code and result_code != "00":
        raise RuntimeError(
            f"공공데이터 API 요청에 실패했습니다. "
            f"오류 코드: {result_code}, 안내: {result_message}"
        )

    items = root.findall(".//item")
    rows = []

    for item in items:
        row = {}

        for xml_tag, korean_name in XML_FIELD_MAP.items():
            row[korean_name] = safe_text(item, xml_tag)

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # 숫자로 사용해야 하는 열입니다.
    numeric_columns = [
        "응급실",
        "수술실",
        "신경중환자실",
        "신생아중환자실",
        "흉부중환자실",
        "일반중환자실",
        "입원실",
        "내과중환자실",
        "외과중환자실",
        "정형외과입원실",
        "신경과입원실",
        "신경외과중환자실",
        "약물중환자실",
        "화상중환자실",
        "외상중환자실",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = df[column].apply(to_int)

    # Y/N 형태의 시설 정보를 보기 좋게 바꿉니다.
    yes_no_columns = [
        "CT",
        "MRI",
        "조영촬영기",
        "인공호흡기",
        "구급차",
        "소아인공호흡기",
        "인큐베이터",
    ]

    for column in yes_no_columns:
        if column in df.columns:
            df[column] = df[column].apply(normalize_yes_no)

    return df


def calculate_crowding(row, department):
    """
    응급실 가용 병상을 중심으로 추정 혼잡도를 계산합니다.

    중요한 점:
    이 값은 실제 대기 환자 수나 실제 대기시간이 아닙니다.
    """
    emergency_beds = to_int(row.get("응급실", 0))

    department_rule = DEPARTMENT_RULES[department]

    related_beds = 0
    related_available_count = 0

    # 진료 분야와 관련된 병상 수를 점수에 반영합니다.
    for field in department_rule["numeric_fields"]:
        value = to_int(row.get(field, 0))
        related_beds += max(value, 0)

        if value > 0:
            related_available_count += 1

    available_facilities = 0
    unavailable_facilities = 0

    # CT, MRI, 인공호흡기 같은 시설 가용 여부도 반영합니다.
    for field in department_rule["yn_fields"]:
        value = row.get(field, "정보 없음")

        if value == "가능":
            available_facilities += 1
        elif value == "불가":
            unavailable_facilities += 1

    # 응급실 가용 병상이 음수로 전달되는 경우도 있으므로
    # 0 이하를 모두 병상 부족 상태로 처리합니다.
    if emergency_beds <= 0:
        level = "매우 혼잡"
        level_order = 4
        icon = "🔴"

    elif emergency_beds <= 3:
        level = "혼잡"
        level_order = 3
        icon = "🟠"

    elif emergency_beds <= 9:
        level = "보통"
        level_order = 2
        icon = "🟡"

    else:
        level = "원활"
        level_order = 1
        icon = "🟢"

    # 선택한 진료 분야에 필요한 시설이 불가능하면
    # 한 단계 더 주의가 필요한 것으로 표시합니다.
    if unavailable_facilities > 0:
        if level == "원활":
            level = "보통"
            level_order = 2
            icon = "🟡"
        elif level == "보통":
            level = "혼잡"
            level_order = 3
            icon = "🟠"

    # 병원 정렬에 사용하는 추천 점수입니다.
    # 응급실 병상 비중을 가장 크게 두고,
    # 관련 병상과 장비 가용 여부를 추가합니다.
    recommendation_score = (
        max(emergency_beds, 0) * 10
        + related_beds * 3
        + related_available_count * 5
        + available_facilities * 4
        - unavailable_facilities * 10
    )

    return pd.Series(
        {
            "혼잡도": level,
            "혼잡도표시": f"{icon} {level}",
            "혼잡도순서": level_order,
            "관련병상합계": related_beds,
            "관련시설가능수": available_facilities,
            "관련시설불가수": unavailable_facilities,
            "추천점수": recommendation_score,
        }
    )


def make_ai_hospital_context(df, location, department, symptom):
    """
    AI가 응급실 정보를 근거로 답할 수 있도록
    검색 결과를 짧은 글로 정리합니다.
    """
    if df is None or df.empty:
        return "현재 조회된 응급실 정보가 없습니다."

    lines = [
        f"사용자 입력 위치: {location}",
        f"희망 진료 분야: {department}",
        f"사용자가 적은 증상: {symptom or '입력하지 않음'}",
        "",
        "현재 조회된 응급실 정보:",
    ]

    # AI에게 너무 많은 정보를 보내지 않도록 상위 10개만 사용합니다.
    for _, row in df.head(10).iterrows():
        hospital_line = (
            f"- 병원명: {row.get('병원명', '정보 없음')}, "
            f"추정 혼잡도: {row.get('혼잡도', '정보 없음')}, "
            f"응급실 가용 병상: {row.get('응급실', 0)}, "
            f"관련 병상 합계: {row.get('관련병상합계', 0)}, "
            f"CT: {row.get('CT', '정보 없음')}, "
            f"MRI: {row.get('MRI', '정보 없음')}, "
            f"인공호흡기: {row.get('인공호흡기', '정보 없음')}, "
            f"응급실 전화: {row.get('응급실전화', '정보 없음')}, "
            f"정보 입력 시각: {row.get('입력일시', '정보 없음')}"
        )

        lines.append(hospital_line)

    lines.extend(
        [
            "",
            "주의:",
            "- 혼잡도는 실제 대기시간이 아니라 가용 병상 기반 추정치다.",
            "- 거리 정보는 없으며 같은 시군구 안의 응급실 목록이다.",
            "- 병원 도착 전에 반드시 전화로 수용 가능 여부를 확인해야 한다.",
            "- 중증 또는 생명 위급 상황이면 병원 추천보다 119 신고를 우선 안내해야 한다.",
        ]
    )

    return "\n".join(lines)


def get_solar_client():
    """
    Streamlit 비밀 금고에서 Solar API 키를 읽어
    OpenAI 호환 클라이언트를 만듭니다.
    """
    solar_api_key = st.secrets.get("SOLAR_API_KEY")

    if not solar_api_key:
        return None

    return OpenAI(
        api_key=solar_api_key,
        base_url=SOLAR_BASE_URL,
    )


def stream_solar_answer(client, messages):
    """
    Solar API의 답변을 스트리밍 방식으로 받아옵니다.
    """
    stream = client.chat.completions.create(
        model=SOLAR_MODEL,
        messages=messages,
        stream=True,

        # 생각 기능을 끄기 위해 temperature가 아니라
        # reasoning_effort를 none으로 지정합니다.
        reasoning_effort="none",
    )

    for chunk in stream:
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)

        if content:
            yield content


# =========================================================
# 8. 세션 상태 초기화
# =========================================================
if "emergency_df" not in st.session_state:
    st.session_state.emergency_df = pd.DataFrame()

if "search_location" not in st.session_state:
    st.session_state.search_location = ""

if "search_department" not in st.session_state:
    st.session_state.search_department = "일반 응급"

if "search_symptom" not in st.session_state:
    st.session_state.search_symptom = ""

if "messages" not in st.session_state:
    st.session_state.messages = []


# =========================================================
# 9. 1단계: 위치 입력
# =========================================================
st.header("1단계 · 현재 위치 입력")

st.write(
    "시도와 시군구를 함께 입력하세요. "
    "예: `서울 강남구`, `경기도 수원시`, `부산 해운대구`"
)

location_input = st.text_input(
    "현재 위치",
    value=st.session_state.search_location,
    placeholder="예: 서울 강남구 역삼동",
)

parsed_sido, parsed_sigungu = parse_location(location_input)

if location_input:
    if parsed_sido and parsed_sigungu:
        st.success(
            f"검색 지역: **{parsed_sido} {parsed_sigungu}**"
        )
    else:
        st.warning(
            "지역을 정확히 찾지 못했습니다. "
            "시도와 시군구를 함께 입력해 주세요. 예: 서울 강남구"
        )


# =========================================================
# 10. 2단계: 필요한 진료 분야와 증상 입력
# =========================================================
st.header("2단계 · 필요한 응급 진료 선택")

department = st.selectbox(
    "진료가 필요하다고 생각하는 분야",
    options=list(DEPARTMENT_RULES.keys()),
    index=list(DEPARTMENT_RULES.keys()).index(
        st.session_state.search_department
    ),
)

st.caption(DEPARTMENT_RULES[department]["description"])

symptom = st.text_area(
    "현재 증상 또는 상황",
    value=st.session_state.search_symptom,
    placeholder=(
        "예: 넘어지면서 팔을 다쳤고 움직일 때 통증이 심합니다. "
        "의식은 있고 출혈은 없습니다."
    ),
    height=100,
)

search_button = st.button(
    "🔍 주변 응급실 조회하기",
    type="primary",
    use_container_width=True,
)


# =========================================================
# 11. 응급실 API 조회
# =========================================================
if search_button:
    if not location_input.strip():
        st.warning("현재 위치를 입력해 주세요.")

    elif not parsed_sido or not parsed_sigungu:
        st.warning(
            "시도와 시군구를 함께 입력해 주세요. "
            "예: 서울 강남구, 경기도 수원시"
        )

    else:
        emergency_api_key = st.secrets.get("Emergency_API_KEY")

        if not emergency_api_key:
            st.error(
                "응급실 API 키가 설정되지 않았습니다. "
                "Streamlit 비밀 금고에 Emergency_API_KEY를 등록해 주세요."
            )

        else:
            try:
                with st.spinner("실시간 응급실 정보를 확인하고 있습니다..."):
                    result_df = fetch_emergency_rooms(
                        api_key=emergency_api_key,
                        sido=parsed_sido,
                        sigungu=parsed_sigungu,
                    )

                if result_df.empty:
                    st.warning(
                        "해당 지역에서 조회된 응급실이 없습니다. "
                        "시군구 이름을 확인하거나 더 가까운 큰 지역으로 다시 검색해 주세요."
                    )

                    st.session_state.emergency_df = pd.DataFrame()

                else:
                    crowding_data = result_df.apply(
                        lambda row: calculate_crowding(row, department),
                        axis=1,
                    )

                    result_df = pd.concat(
                        [
                            result_df.reset_index(drop=True),
                            crowding_data.reset_index(drop=True),
                        ],
                        axis=1,
                    )

                    # 먼저 혼잡도가 낮은 병원,
                    # 같은 혼잡도에서는 추천점수가 높은 병원을 보여줍니다.
                    result_df = result_df.sort_values(
                        by=["혼잡도순서", "추천점수", "응급실"],
                        ascending=[True, False, False],
                    ).reset_index(drop=True)

                    st.session_state.emergency_df = result_df
                    st.session_state.search_location = location_input
                    st.session_state.search_department = department
                    st.session_state.search_symptom = symptom

                    st.success(
                        f"{parsed_sido} {parsed_sigungu}의 "
                        f"응급실 {len(result_df)}곳을 조회했습니다."
                    )

            except Exception as error:
                st.session_state.emergency_df = pd.DataFrame()

                st.error(
                    "응급실 정보를 불러오지 못했습니다.\n\n"
                    "다음을 확인해 주세요.\n"
                    "- 공공데이터포털 활용신청이 승인되었는지\n"
                    "- Emergency_API_KEY가 정확한지\n"
                    "- 시도와 시군구 이름이 정확한지\n"
                    "- API 일일 호출 한도를 넘지 않았는지\n\n"
                    f"상세 안내: {error}"
                )


# =========================================================
# 12. 검색 결과 표시
# =========================================================
result_df = st.session_state.emergency_df

if not result_df.empty:
    st.divider()
    st.header("조회 결과")

    smooth_count = int((result_df["혼잡도"] == "원활").sum())
    normal_count = int((result_df["혼잡도"] == "보통").sum())
    busy_count = int(
        result_df["혼잡도"].isin(["혼잡", "매우 혼잡"]).sum()
    )
    total_er_beds = int(
        result_df["응급실"].clip(lower=0).sum()
    )

    metric_columns = st.columns(4)

    metric_columns[0].metric("조회된 응급실", f"{len(result_df)}곳")
    metric_columns[1].metric("원활 추정", f"{smooth_count}곳")
    metric_columns[2].metric("보통 추정", f"{normal_count}곳")
    metric_columns[3].metric("응급실 가용 병상 합계", f"{total_er_beds}개")

    if busy_count > 0:
        st.warning(
            f"혼잡 또는 매우 혼잡으로 추정되는 응급실이 {busy_count}곳 있습니다."
        )

    st.caption(
        "정렬 기준: 추정 혼잡도가 낮은 순 → 선택 진료 분야 관련 병상·시설 점수가 높은 순"
    )

    # 진료 분야에 따라 표에 추가할 열을 정합니다.
    department_fields = DEPARTMENT_RULES[
        st.session_state.search_department
    ]["numeric_fields"]

    facility_fields = DEPARTMENT_RULES[
        st.session_state.search_department
    ]["yn_fields"]

    display_columns = [
        "혼잡도표시",
        "병원명",
        "응급실",
        "응급실전화",
        "입력일시",
    ]

    for field in department_fields + facility_fields:
        if field in result_df.columns and field not in display_columns:
            display_columns.insert(-2, field)

    display_df = result_df[display_columns].copy()

    display_df = display_df.rename(
        columns={
            "혼잡도표시": "추정 혼잡도",
            "응급실": "응급실 가용 병상",
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("응급실별 자세한 정보")

    for index, row in result_df.iterrows():
        hospital_name = row.get("병원명", "병원명 정보 없음")
        crowding = row.get("혼잡도표시", "정보 없음")
        emergency_beds = row.get("응급실", 0)

        with st.expander(
            f"{index + 1}. {crowding} · {hospital_name} "
            f"· 가용 병상 {emergency_beds}"
        ):
            left, right = st.columns(2)

            with left:
                st.write(f"**응급실 가용 병상:** {emergency_beds}")
                st.write(f"**수술실:** {row.get('수술실', 0)}")
                st.write(
                    f"**일반중환자실:** "
                    f"{row.get('일반중환자실', 0)}"
                )
                st.write(f"**입원실:** {row.get('입원실', 0)}")
                st.write(
                    f"**선택 분야 관련 병상 합계:** "
                    f"{row.get('관련병상합계', 0)}"
                )

            with right:
                st.write(f"**CT:** {row.get('CT', '정보 없음')}")
                st.write(f"**MRI:** {row.get('MRI', '정보 없음')}")
                st.write(
                    f"**인공호흡기:** "
                    f"{row.get('인공호흡기', '정보 없음')}"
                )
                st.write(
                    f"**응급실 전화:** "
                    f"{row.get('응급실전화', '정보 없음')}"
                )
                st.write(
                    f"**정보 입력 시각:** "
                    f"{row.get('입력일시', '정보 없음')}"
                )

            st.warning(
                "출발 전 응급실에 전화하여 현재 증상에 대한 "
                "진료 가능 여부를 반드시 확인하세요."
            )


# =========================================================
# 13. 3단계: Solar AI 채팅
# =========================================================
st.divider()
st.header("3단계 · AI 응급실 안내")

st.write(
    "조회 결과를 바탕으로 어느 응급실에 먼저 전화해 볼지 물어보세요."
)

st.caption(
    "예: 현재 조회된 병원 중 신경과 응급에 적합한 곳을 간단히 알려줘."
)

button_column, notice_column = st.columns([1, 4])

with button_column:
    if st.button("대화 지우기", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

with notice_column:
    st.caption(
        "AI 답변은 의료진의 진단이나 119의 판단을 대신하지 않습니다."
    )


# 이전 대화 내용을 말풍선으로 보여줍니다.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


user_prompt = st.chat_input(
    "응급실 선택이나 현재 조회 결과에 대해 질문해 주세요."
)

if user_prompt:
    # 사용자의 질문을 세션에 저장합니다.
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_prompt)

    solar_client = get_solar_client()

    if solar_client is None:
        with st.chat_message("assistant"):
            st.warning(
                "Solar API 키가 설정되지 않았습니다. "
                "Streamlit 비밀 금고에 SOLAR_API_KEY를 등록해 주세요."
            )

    else:
        hospital_context = make_ai_hospital_context(
            df=st.session_state.emergency_df,
            location=st.session_state.search_location,
            department=st.session_state.search_department,
            symptom=st.session_state.search_symptom,
        )

        system_prompt = f"""
너는 냉철한, 단답형, 시크한 성격이야.
반드시 순수 한국어로만 답해.

너는 사용자가 조회한 실시간 응급실 가용 병상 정보를 정리하는 안내 도우미다.
의학적 진단을 내리지 마라.
약물 복용량이나 치료법을 지시하지 마라.
실제 대기시간을 아는 것처럼 말하지 마라.
거리 정보가 없으므로 가장 가까운 병원이라고 단정하지 마라.
현재 자료는 같은 시군구 안의 응급실 목록이라는 점을 기억해라.

응답 규칙:
1. 생명이 위급해 보이면 다른 설명보다 먼저 119 연락을 안내한다.
2. 병원을 추천할 때는 최대 3곳만 짧게 제시한다.
3. 병원명, 추정 혼잡도, 가용 병상, 전화 확인 필요성을 말한다.
4. 가용 병상이 많아도 실제 환자 수용이 불가능할 수 있다고 알려라.
5. 출발 전에 응급실에 전화하라고 안내한다.
6. 조회 결과가 없으면 특정 병원을 지어내지 말고 119 또는 응급의료 상담을 안내한다.
7. 답변은 짧고 분명하게 한다.

현재 앱의 조회 자료:
{hospital_context}
""".strip()

        api_messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        # 저장된 대화 기록을 함께 보내 이전 대화를 기억하게 합니다.
        api_messages.extend(st.session_state.messages)

        try:
            with st.chat_message("assistant"):
                answer = st.write_stream(
                    stream_solar_answer(
                        client=solar_client,
                        messages=api_messages,
                    )
                )

            # 일부 환경에서는 write_stream 결과가 리스트가 될 수 있어
            # 문자열 형태로 정리합니다.
            if isinstance(answer, list):
                answer = "".join(str(part) for part in answer)

            answer = str(answer)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

        except Exception as error:
            friendly_message = (
                "AI 안내를 불러오지 못했습니다. "
                "잠시 후 다시 시도해 주세요. "
                "SOLAR_API_KEY와 API 사용 가능 상태도 확인해 주세요."
            )

            with st.chat_message("assistant"):
                st.warning(friendly_message)
                st.caption(f"상세 안내: {error}")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": friendly_message,
                }
            )


# =========================================================
# 14. 앱 맨 아래 안내
# =========================================================
st.divider()

st.caption(
    "자료 출처: 국립중앙의료원 전국 응급의료기관 정보 조회 서비스"
)

st.caption(
    f"앱 화면 갱신 시각: "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

st.caption(
    "이 앱은 응급실 가용 병상 정보를 보기 쉽게 정리한 참고용 서비스이며, "
    "의료진의 진단이나 119 구급상황관리센터의 판단을 대신하지 않습니다."
)
