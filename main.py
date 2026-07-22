import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI


# =========================================================
# 1. 스트림릿 화면 기본 설정
# =========================================================
st.set_page_config(
    page_title="실시간 응급실 혼잡도 안내",
    page_icon="🏥",
    layout="wide",
)


# =========================================================
# 2. 화면 디자인
# =========================================================
st.markdown(
    """
    <style>
    /* 전체 화면 최대 너비 */
    .block-container {
        max-width: 1250px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* 앱 상단 소개 영역 */
    .main-banner {
        padding: 28px 30px;
        border-radius: 22px;
        background: linear-gradient(
            135deg,
            rgba(230, 242, 255, 0.95),
            rgba(238, 250, 245, 0.95)
        );
        border: 1px solid rgba(70, 130, 180, 0.25);
        margin-bottom: 24px;
    }

    .main-banner h1 {
        margin: 0 0 10px 0;
        font-size: 38px;
        font-weight: 900;
    }

    .main-banner p {
        margin: 0;
        font-size: 17px;
        line-height: 1.65;
    }

    /* 단계 제목 */
    .step-title {
        padding: 14px 18px;
        margin-top: 20px;
        margin-bottom: 14px;
        border-left: 7px solid #3578e5;
        border-radius: 10px;
        background-color: rgba(53, 120, 229, 0.08);
        font-size: 25px;
        font-weight: 850;
    }

    /* AI 상담 영역 */
    .ai-chat-banner {
        margin-top: 34px;
        margin-bottom: 18px;
        padding: 26px 28px;
        border: 3px solid #6c63ff;
        border-radius: 22px;
        background: linear-gradient(
            135deg,
            rgba(108, 99, 255, 0.17),
            rgba(49, 196, 190, 0.13)
        );
        box-shadow: 0 10px 28px rgba(75, 65, 180, 0.20);
    }

    .ai-chat-banner h2 {
        margin: 0 0 10px 0;
        font-size: 31px;
        font-weight: 900;
    }

    .ai-chat-banner p {
        margin: 0;
        font-size: 17px;
        line-height: 1.65;
    }

    /* AI 질문 예시 카드 */
    .question-example {
        min-height: 108px;
        padding: 16px;
        border-radius: 16px;
        border: 1px solid rgba(108, 99, 255, 0.25);
        background-color: rgba(108, 99, 255, 0.07);
        font-size: 15px;
        line-height: 1.55;
    }

    /* 채팅 메시지 말풍선 */
    [data-testid="stChatMessage"] {
        border: 1px solid rgba(108, 99, 255, 0.30);
        border-radius: 17px;
        padding: 12px 15px;
        margin-bottom: 13px;
        background-color: rgba(108, 99, 255, 0.045);
        box-shadow: 0 3px 12px rgba(60, 55, 150, 0.07);
    }

    /* 채팅 입력창 주변을 강조 */
    [data-testid="stChatInput"] {
        border: 3px solid #6c63ff;
        border-radius: 20px;
        box-shadow: 0 7px 22px rgba(108, 99, 255, 0.28);
        background-color: white;
    }

    [data-testid="stChatInput"] textarea {
        font-size: 17px;
        font-weight: 600;
        min-height: 52px;
    }

    /* 버튼을 조금 더 크게 */
    div.stButton > button {
        min-height: 44px;
        font-weight: 750;
        border-radius: 12px;
    }

    /* 모바일 화면 보정 */
    @media (max-width: 700px) {
        .main-banner {
            padding: 20px;
        }

        .main-banner h1 {
            font-size: 29px;
        }

        .ai-chat-banner {
            padding: 20px;
        }

        .ai-chat-banner h2 {
            font-size: 25px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 3. 앱 제목
# =========================================================
st.markdown(
    """
    <div class="main-banner">
        <h1>🏥 실시간 응급실 혼잡도 안내</h1>
        <p>
            현재 지역과 필요한 진료 분야를 입력하면,
            주변 응급실의 실시간 가용 병상과 의료시설 정보를 확인할 수 있습니다.
            조회 결과를 바탕으로 AI에게 어느 병원에 먼저 전화할지 질문할 수도 있습니다.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 4. 응급 상황 안전 안내
# =========================================================
st.error(
    """
    **생명이 위급한 상황에서는 이 앱을 사용해 병원을 비교하지 말고 즉시 119에 연락하세요.**

    호흡 곤란, 의식 저하, 심한 출혈, 갑작스러운 마비, 심한 가슴 통증,
    경련, 심각한 알레르기 반응 등이 있으면 바로 119에 도움을 요청해야 합니다.
    """
)

st.info(
    """
    이 앱의 혼잡도는 실제 대기 환자 수나 대기시간이 아닙니다.

    국립중앙의료원 Open API가 제공하는 응급실 가용 병상과 관련 시설 정보를 바탕으로
    계산한 참고용 추정치입니다. 출발 전에 반드시 응급실에 전화해 수용 가능 여부를 확인하세요.
    """
)


# =========================================================
# 5. API 기본 정보
# =========================================================

# 국립중앙의료원 전국 응급의료기관 정보 조회 서비스
EMERGENCY_API_URL = (
    "https://apis.data.go.kr/B552657/"
    "ErmctInfoInqireService/"
    "getEmrrmRltmUsefulSckbdInfoInqire"
)

# Solar API 정보
SOLAR_BASE_URL = "https://api.upstage.ai/v1"
SOLAR_MODEL = "solar-open2"


# =========================================================
# 6. 시도 이름 변환표
# =========================================================
SIDO_ALIASES = {
    "서울특별시": "서울특별시",
    "서울시": "서울특별시",
    "서울": "서울특별시",

    "부산광역시": "부산광역시",
    "부산시": "부산광역시",
    "부산": "부산광역시",

    "대구광역시": "대구광역시",
    "대구시": "대구광역시",
    "대구": "대구광역시",

    "인천광역시": "인천광역시",
    "인천시": "인천광역시",
    "인천": "인천광역시",

    "광주광역시": "광주광역시",
    "광주시": "광주광역시",
    "광주": "광주광역시",

    "대전광역시": "대전광역시",
    "대전시": "대전광역시",
    "대전": "대전광역시",

    "울산광역시": "울산광역시",
    "울산시": "울산광역시",
    "울산": "울산광역시",

    "세종특별자치시": "세종특별자치시",
    "세종시": "세종특별자치시",
    "세종": "세종특별자치시",

    "경기도": "경기도",
    "경기": "경기도",

    "강원특별자치도": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원": "강원특별자치도",

    "충청북도": "충청북도",
    "충북": "충청북도",

    "충청남도": "충청남도",
    "충남": "충청남도",

    "전북특별자치도": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전북": "전북특별자치도",

    "전라남도": "전라남도",
    "전남": "전라남도",

    "경상북도": "경상북도",
    "경북": "경상북도",

    "경상남도": "경상남도",
    "경남": "경상남도",

    "제주특별자치도": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주": "제주특별자치도",
}


# =========================================================
# 7. 진료 분야별 참고 항목
# =========================================================
DEPARTMENT_RULES = {
    "일반 응급": {
        "description": "응급실 가용 병상을 중심으로 확인합니다.",
        "numeric_fields": [],
        "yn_fields": [],
    },

    "내과 응급": {
        "description": "응급실과 내과·일반 중환자실 병상을 함께 확인합니다.",
        "numeric_fields": ["내과중환자실", "일반중환자실"],
        "yn_fields": [],
    },

    "외과 응급": {
        "description": "수술실과 외과 중환자실 병상을 함께 확인합니다.",
        "numeric_fields": ["수술실", "외과중환자실"],
        "yn_fields": [],
    },

    "정형외과·골절": {
        "description": "수술실, 정형외과 입원실과 CT 가용 여부를 확인합니다.",
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
        "description": "흉부 중환자실과 인공호흡기, CT 가용 여부를 확인합니다.",
        "numeric_fields": ["흉부중환자실", "일반중환자실"],
        "yn_fields": ["CT", "인공호흡기"],
    },

    "소아 응급": {
        "description": "신생아 중환자실, 소아 인공호흡기와 인큐베이터를 확인합니다.",
        "numeric_fields": ["신생아중환자실"],
        "yn_fields": ["소아인공호흡기", "인큐베이터"],
    },

    "외상 응급": {
        "description": "외상 중환자실과 수술실, CT 가용 여부를 확인합니다.",
        "numeric_fields": ["외상중환자실", "수술실"],
        "yn_fields": ["CT", "조영촬영기"],
    },

    "화상 응급": {
        "description": "화상 중환자 병상과 일반 중환자실 병상을 확인합니다.",
        "numeric_fields": ["화상중환자실", "일반중환자실"],
        "yn_fields": [],
    },

    "약물 중독": {
        "description": "약물 중환자 병상과 인공호흡기 가용 여부를 확인합니다.",
        "numeric_fields": ["약물중환자실", "일반중환자실"],
        "yn_fields": ["인공호흡기"],
    },

    "산부인과·신생아": {
        "description": "신생아 중환자실과 인큐베이터 가용 여부를 확인합니다.",
        "numeric_fields": ["신생아중환자실"],
        "yn_fields": ["인큐베이터"],
    },

    "치과 응급": {
        "description": (
            "이 API에는 치과 전용 병상이나 치과 당직 정보가 없습니다. "
            "응급실 병상, 수술실과 CT 정보를 참고용으로 확인합니다."
        ),
        "numeric_fields": ["수술실"],
        "yn_fields": ["CT"],
    },
}


# =========================================================
# 8. XML 태그 후보
# =========================================================
# XML은 대소문자를 구분합니다.
# 실제 API에서 dutyName 또는 dutyname처럼 다르게 오는 경우를 모두 처리합니다.
XML_FIELD_MAP = {
    "기관코드": ["hpid", "HPID"],
    "병원명": ["dutyName", "dutyname", "DUTYNAME"],
    "응급실전화": ["dutyTel3", "dutytel3", "DUTYTEL3"],
    "입력일시": ["hvidate", "hviDate"],

    "응급실": ["hvec"],
    "수술실": ["hvoc"],
    "신경중환자실": ["hvcc"],
    "신생아중환자실": ["hvncc"],
    "흉부중환자실": ["hvccc"],
    "일반중환자실": ["hvicc"],
    "입원실": ["hvgc"],

    "내과중환자실": ["hv2"],
    "외과중환자실": ["hv3"],
    "정형외과입원실": ["hv4"],
    "신경과입원실": ["hv5"],
    "신경외과중환자실": ["hv6"],
    "약물중환자실": ["hv7"],
    "화상중환자실": ["hv8"],
    "외상중환자실": ["hv9"],

    "CT": ["hvctayn", "hvctAyn"],
    "MRI": ["hvmriayn", "hvmriAyn"],
    "조영촬영기": ["hvangioayn", "hvangioAyn"],
    "인공호흡기": ["hvventiayn", "hvventiAyn"],
    "구급차": ["hvamyn", "hvamYn"],
    "소아인공호흡기": ["hv10"],
    "인큐베이터": ["hv11"],

    "당직의": ["hvdnm"],
    "당직의연락처": ["hv1"],
    "소아당직의연락처": ["hv12"],
}


# =========================================================
# 9. 보조 함수
# =========================================================
def safe_text_any(element, tag_candidates, default=""):
    """
    여러 XML 태그 후보를 차례로 확인해 값을 읽습니다.
    """
    for tag_name in tag_candidates:
        child = element.find(tag_name)

        if child is not None and child.text is not None:
            value = child.text.strip()

            if value:
                return value

    return default


def to_int(value, default=0):
    """
    문자열 숫자를 안전하게 정수로 변환합니다.
    """
    if value is None:
        return default

    text = str(value).strip()

    if not text:
        return default

    try:
        return int(float(text))
    except (ValueError, TypeError):
        return default


def normalize_yes_no(value):
    """
    Y/N 값을 화면에 표시하기 좋은 한국어로 바꿉니다.
    """
    text = str(value).strip().upper()

    if text == "Y":
        return "가능"

    if text == "N":
        return "불가"

    return "정보 없음"


def parse_location(location_text):
    """
    사용자가 입력한 주소에서 시도와 시군구를 추출합니다.

    예:
    서울 강남구 역삼동 → 서울특별시, 강남구
    경기도 수원시 영통구 → 경기도, 수원시
    """
    cleaned = re.sub(r"[,/]", " ", location_text.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)

    found_sido = None
    found_alias = None

    # 이름이 긴 항목부터 확인합니다.
    aliases = sorted(SIDO_ALIASES.keys(), key=len, reverse=True)

    for alias in aliases:
        if alias in cleaned:
            found_sido = SIDO_ALIASES[alias]
            found_alias = alias
            break

    if not found_sido:
        return None, None

    remainder = cleaned.replace(found_alias, " ", 1)
    tokens = remainder.split()

    sigungu = None

    for token in tokens:
        if token.endswith(("시", "군", "구")):
            sigungu = token
            break

    # 세종시는 시군구를 별도로 쓰지 않는 경우가 있어 예외 처리합니다.
    if found_sido == "세종특별자치시" and not sigungu:
        sigungu = "세종특별자치시"

    return found_sido, sigungu


def build_api_url(api_key, sido, sigungu, page_no=1, rows=100):
    """
    공공데이터 API 요청 주소를 만듭니다.
    """
    # 인증키가 이미 인코딩된 형태일 수 있어 먼저 해제합니다.
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


# 같은 지역의 결과는 1분 동안 저장합니다.
# 사용자가 새로고침할 때 API가 지나치게 많이 호출되는 것을 막습니다.
@st.cache_data(ttl=60, show_spinner=False)
def fetch_emergency_rooms(api_key, sido, sigungu):
    """
    국립중앙의료원 API에서 응급실 정보를 가져옵니다.
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
            f"공공데이터 서버 요청이 거절되었습니다. 상태 코드: {error.code}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            "공공데이터 서버에 연결하지 못했습니다."
        ) from error

    except TimeoutError as error:
        raise RuntimeError(
            "공공데이터 서버 응답이 지연되고 있습니다."
        ) from error

    try:
        root = ET.fromstring(xml_bytes)

    except ET.ParseError as error:
        raise RuntimeError(
            "공공데이터 응답을 XML 형식으로 읽지 못했습니다."
        ) from error

    # API가 반환한 결과 코드를 확인합니다.
    result_code = root.findtext(".//resultCode")

    result_message = (
        root.findtext(".//resultMsg")
        or root.findtext(".//resultMag")
        or ""
    )

    if result_code and result_code != "00":
        raise RuntimeError(
            f"API 요청 실패: {result_code} / {result_message}"
        )

    items = root.findall(".//item")
    rows = []

    for item in items:
        row = {}

        for korean_name, tag_candidates in XML_FIELD_MAP.items():
            row[korean_name] = safe_text_any(
                item,
                tag_candidates,
                default="",
            )

        # 병원명과 전화번호가 없는 경우 안내 문구를 넣습니다.
        if not row.get("병원명"):
            row["병원명"] = "병원명 정보 없음"

        if not row.get("응급실전화"):
            row["응급실전화"] = "전화번호 정보 없음"

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

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
    가용 응급실 병상과 진료 분야 관련 시설을 바탕으로
    추정 혼잡도를 계산합니다.

    실제 대기 환자 수 또는 실제 대기시간은 아닙니다.
    """
    emergency_beds = to_int(row.get("응급실", 0))

    rule = DEPARTMENT_RULES[department]

    related_beds = 0
    available_facilities = 0
    unavailable_facilities = 0

    for field in rule["numeric_fields"]:
        value = to_int(row.get(field, 0))
        related_beds += max(value, 0)

    for field in rule["yn_fields"]:
        value = row.get(field, "정보 없음")

        if value == "가능":
            available_facilities += 1

        elif value == "불가":
            unavailable_facilities += 1

    # 기본 혼잡도는 응급실 가용 병상 수를 기준으로 정합니다.
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

    # 필요한 장비가 불가능한 경우 혼잡도를 한 단계 주의 상태로 조정합니다.
    if unavailable_facilities > 0:
        if level == "원활":
            level = "보통"
            level_order = 2
            icon = "🟡"

        elif level == "보통":
            level = "혼잡"
            level_order = 3
            icon = "🟠"

    recommendation_score = (
        max(emergency_beds, 0) * 10
        + related_beds * 3
        + available_facilities * 5
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
    AI가 현재 조회 결과를 참고할 수 있도록 문자열로 정리합니다.
    """
    if df is None or df.empty:
        return "현재 조회된 응급실 정보가 없습니다."

    lines = [
        f"사용자가 입력한 위치: {location}",
        f"선택한 진료 분야: {department}",
        f"입력한 증상: {symptom or '입력하지 않음'}",
        "",
        "현재 조회된 응급실 정보:",
    ]

    # AI에 너무 많은 정보가 전달되지 않도록 상위 10곳만 사용합니다.
    for _, row in df.head(10).iterrows():
        lines.append(
            (
                f"- 병원명: {row.get('병원명', '정보 없음')}, "
                f"추정 혼잡도: {row.get('혼잡도', '정보 없음')}, "
                f"응급실 가용 병상: {row.get('응급실', 0)}, "
                f"관련 병상 합계: {row.get('관련병상합계', 0)}, "
                f"수술실: {row.get('수술실', 0)}, "
                f"CT: {row.get('CT', '정보 없음')}, "
                f"MRI: {row.get('MRI', '정보 없음')}, "
                f"인공호흡기: {row.get('인공호흡기', '정보 없음')}, "
                f"응급실 전화: {row.get('응급실전화', '정보 없음')}, "
                f"입력 시각: {row.get('입력일시', '정보 없음')}"
            )
        )

    lines.extend(
        [
            "",
            "반드시 지켜야 할 조건:",
            "- 이 혼잡도는 실제 대기시간이 아니라 가용 병상 기반 추정치다.",
            "- 같은 시군구 안의 병원을 조회한 것이며 실제 거리순이 아니다.",
            "- 출발 전 병원에 전화해 수용 가능 여부를 확인해야 한다.",
            "- 생명이 위급하면 병원 비교보다 119 신고를 우선 안내해야 한다.",
            "- 치과 응급은 치과 전용 진료 가능 정보를 제공하지 않는다.",
        ]
    )

    return "\n".join(lines)


def get_solar_client():
    """
    Streamlit 비밀 금고에서 Solar API 키를 읽습니다.
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
    Solar 답변을 스트리밍 형태로 전달합니다.
    """
    stream = client.chat.completions.create(
        model=SOLAR_MODEL,
        messages=messages,
        stream=True,
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
# 10. 세션 상태 초기화
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
# 11. 1단계: 위치 입력
# =========================================================
st.markdown(
    '<div class="step-title">1단계 · 현재 위치 입력</div>',
    unsafe_allow_html=True,
)

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
            f"API 검색 지역: **{parsed_sido} {parsed_sigungu}**"
        )

    else:
        st.warning(
            "지역을 정확히 찾지 못했습니다. "
            "시도와 시군구를 함께 입력해 주세요. 예: 서울 강남구"
        )


# =========================================================
# 12. 2단계: 진료 분야 입력
# =========================================================
st.markdown(
    '<div class="step-title">2단계 · 필요한 응급 진료 선택</div>',
    unsafe_allow_html=True,
)

department_names = list(DEPARTMENT_RULES.keys())

saved_department = st.session_state.search_department

if saved_department not in department_names:
    saved_department = "일반 응급"

department = st.selectbox(
    "진료가 필요하다고 생각하는 분야",
    options=department_names,
    index=department_names.index(saved_department),
)

st.caption(DEPARTMENT_RULES[department]["description"])

if department == "치과 응급":
    st.warning(
        """
        **치과 응급 안내**

        이 API에는 치과 당직 여부나 구강악안면외과 진료 가능 여부가 포함되지 않습니다.
        현재 앱은 응급실 병상, 수술실과 CT 정보를 참고용으로 보여줍니다.

        심한 얼굴 외상, 턱 골절 의심, 멈추지 않는 출혈 또는 호흡 곤란이 있으면
        일반 치과를 찾기보다 즉시 119에 연락하거나 응급실에 전화하세요.
        """
    )

symptom = st.text_area(
    "현재 증상 또는 상황",
    value=st.session_state.search_symptom,
    placeholder=(
        "예: 넘어지면서 턱을 부딪쳤고 입안 출혈이 계속됩니다. "
        "의식은 있으며 호흡은 가능합니다."
    ),
    height=105,
)

search_button = st.button(
    "🔍 주변 응급실 실시간 조회",
    type="primary",
    use_container_width=True,
)


# =========================================================
# 13. API 조회 실행
# =========================================================
if search_button:
    if not location_input.strip():
        st.warning("현재 위치를 입력해 주세요.")

    elif not parsed_sido or not parsed_sigungu:
        st.warning(
            "시도와 시군구를 함께 입력해 주세요. "
            "예: 서울 강남구 또는 경기도 수원시"
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
                    st.session_state.emergency_df = pd.DataFrame()

                    st.warning(
                        "해당 지역에서 조회된 응급실 정보가 없습니다. "
                        "시군구 이름을 확인하거나 인접한 지역으로 다시 검색해 주세요."
                    )

                else:
                    crowding_df = result_df.apply(
                        lambda row: calculate_crowding(
                            row=row,
                            department=department,
                        ),
                        axis=1,
                    )

                    result_df = pd.concat(
                        [
                            result_df.reset_index(drop=True),
                            crowding_df.reset_index(drop=True),
                        ],
                        axis=1,
                    )

                    result_df = result_df.sort_values(
                        by=[
                            "혼잡도순서",
                            "추천점수",
                            "응급실",
                        ],
                        ascending=[
                            True,
                            False,
                            False,
                        ],
                    ).reset_index(drop=True)

                    st.session_state.emergency_df = result_df
                    st.session_state.search_location = location_input
                    st.session_state.search_department = department
                    st.session_state.search_symptom = symptom

                    st.success(
                        f"{parsed_sido} {parsed_sigungu}에서 "
                        f"응급실 {len(result_df)}곳을 조회했습니다."
                    )

            except Exception:
                st.session_state.emergency_df = pd.DataFrame()

                st.error(
                    """
                    응급실 정보를 불러오지 못했습니다.

                    다음 사항을 확인해 주세요.

                    - 공공데이터포털에서 해당 API 활용신청을 완료했는지
                    - 비밀 금고의 Emergency_API_KEY가 정확한지
                    - 시도와 시군구 이름을 정확히 입력했는지
                    - 개발계정의 일일 호출 한도를 넘지 않았는지
                    - 공공데이터 서버가 일시적으로 점검 중인지
                    """
                )


# =========================================================
# 14. 검색 결과 표시
# =========================================================
result_df = st.session_state.emergency_df

if not result_df.empty:
    st.divider()
    st.subheader("📋 실시간 조회 결과")

    smooth_count = int(
        (result_df["혼잡도"] == "원활").sum()
    )

    normal_count = int(
        (result_df["혼잡도"] == "보통").sum()
    )

    busy_count = int(
        result_df["혼잡도"].isin(
            ["혼잡", "매우 혼잡"]
        ).sum()
    )

    total_er_beds = int(
        result_df["응급실"]
        .clip(lower=0)
        .sum()
    )

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "조회된 응급실",
        f"{len(result_df)}곳",
    )

    metric_columns[1].metric(
        "원활 추정",
        f"{smooth_count}곳",
    )

    metric_columns[2].metric(
        "보통 추정",
        f"{normal_count}곳",
    )

    metric_columns[3].metric(
        "가용 응급실 병상 합계",
        f"{total_er_beds}개",
    )

    if busy_count > 0:
        st.warning(
            f"혼잡 또는 매우 혼잡으로 추정되는 응급실이 "
            f"{busy_count}곳 있습니다."
        )

    st.caption(
        "정렬 기준: 추정 혼잡도가 낮은 순 → "
        "선택 진료 분야 관련 병상·시설 점수가 높은 순"
    )

    active_department = st.session_state.search_department
    rule = DEPARTMENT_RULES[active_department]

    display_columns = [
        "혼잡도표시",
        "병원명",
        "응급실전화",
        "응급실",
    ]

    # 선택한 진료 분야와 관련된 병상 정보를 표에 추가합니다.
    for field in rule["numeric_fields"]:
        if field in result_df.columns and field not in display_columns:
            display_columns.append(field)

    # 선택한 진료 분야와 관련된 시설 정보를 표에 추가합니다.
    for field in rule["yn_fields"]:
        if field in result_df.columns and field not in display_columns:
            display_columns.append(field)

    display_columns.append("입력일시")

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

    st.subheader("🏨 병원별 자세한 정보")

    for index, row in result_df.iterrows():
        hospital_name = row.get(
            "병원명",
            "병원명 정보 없음",
        )

        crowding = row.get(
            "혼잡도표시",
            "정보 없음",
        )

        emergency_beds = row.get(
            "응급실",
            0,
        )

        phone_number = row.get(
            "응급실전화",
            "전화번호 정보 없음",
        )

        with st.expander(
            f"{index + 1}. {crowding} · "
            f"{hospital_name} · "
            f"가용 병상 {emergency_beds}개"
        ):
            st.markdown(
                f"### {hospital_name}"
            )

            st.markdown(
                f"**☎ 응급실 전화번호: {phone_number}**"
            )

            left, right = st.columns(2)

            with left:
                st.write(
                    f"**응급실 가용 병상:** {emergency_beds}개"
                )

                st.write(
                    f"**수술실:** {row.get('수술실', 0)}개"
                )

                st.write(
                    f"**일반 중환자실:** "
                    f"{row.get('일반중환자실', 0)}개"
                )

                st.write(
                    f"**입원실:** {row.get('입원실', 0)}개"
                )

                st.write(
                    f"**선택 분야 관련 병상 합계:** "
                    f"{row.get('관련병상합계', 0)}개"
                )

            with right:
                st.write(
                    f"**CT:** {row.get('CT', '정보 없음')}"
                )

                st.write(
                    f"**MRI:** {row.get('MRI', '정보 없음')}"
                )

                st.write(
                    f"**인공호흡기:** "
                    f"{row.get('인공호흡기', '정보 없음')}"
                )

                st.write(
                    f"**구급차:** "
                    f"{row.get('구급차', '정보 없음')}"
                )

                st.write(
                    f"**정보 입력 시각:** "
                    f"{row.get('입력일시', '정보 없음')}"
                )

            if active_department == "치과 응급":
                st.info(
                    "치과나 구강악안면외과의 실제 진료 가능 여부는 "
                    "이 데이터로 알 수 없습니다. "
                    "전화로 치과 응급진료 가능 여부를 반드시 확인하세요."
                )

            st.warning(
                "출발 전에 위 전화번호로 연락하여 "
                "현재 증상에 대한 수용 가능 여부를 확인하세요."
            )


# =========================================================
# 15. 3단계: AI 채팅 영역
# =========================================================
st.divider()

st.markdown(
    """
    <div class="ai-chat-banner">
        <h2>🤖 3단계 · AI 응급실 추천 상담</h2>
        <p>
            위에서 조회한 실시간 병상 정보를 바탕으로,
            어느 응급실에 먼저 전화해 볼지 AI에게 물어보세요.<br>
            병원명, 추정 혼잡도, 가용 병상과 전화번호를 비교해 짧게 안내합니다.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.session_state.emergency_df.empty:
    st.warning(
        "먼저 위에서 현재 위치와 진료 분야를 입력한 뒤 "
        "응급실을 조회해 주세요."
    )

else:
    best_hospital = st.session_state.emergency_df.iloc[0]

    st.success(
        f"현재 조회 결과의 첫 번째 후보: "
        f"**{best_hospital.get('병원명', '정보 없음')}** · "
        f"{best_hospital.get('혼잡도표시', '혼잡도 정보 없음')} · "
        f"가용 병상 {best_hospital.get('응급실', 0)}개 · "
        f"전화 {best_hospital.get('응급실전화', '정보 없음')}"
    )

st.markdown("#### 💬 질문 예시")

example_col1, example_col2, example_col3 = st.columns(3)

with example_col1:
    st.markdown(
        """
        <div class="question-example">
            <strong>혼잡도 비교</strong><br><br>
            가장 덜 붐비는 병원 세 곳만 알려줘.
        </div>
        """,
        unsafe_allow_html=True,
    )

with example_col2:
    st.markdown(
        """
        <div class="question-example">
            <strong>치과 응급</strong><br><br>
            치과 응급이면 어느 병원에 먼저 전화해야 해?
        </div>
        """,
        unsafe_allow_html=True,
    )

with example_col3:
    st.markdown(
        """
        <div class="question-example">
            <strong>의료시설 확인</strong><br><br>
            CT가 가능하고 병상이 있는 병원을 알려줘.
        </div>
        """,
        unsafe_allow_html=True,
    )

button_column, notice_column = st.columns([1, 4])

with button_column:
    if st.button(
        "🗑️ 대화 지우기",
        use_container_width=True,
    ):
        st.session_state.messages = []
        st.rerun()

with notice_column:
    st.caption(
        "AI 답변은 의료진의 진단이나 119의 판단을 대신하지 않습니다."
    )


# 이전 대화를 말풍선으로 표시합니다.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


user_prompt = st.chat_input(
    "여기에 질문하세요. 예: 가장 덜 붐비는 응급실 세 곳을 알려줘."
)

if user_prompt:
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

반드시 지켜야 할 규칙:
1. 의학적 진단을 내리지 마라.
2. 약물 복용량이나 치료 방법을 지시하지 마라.
3. 실제 대기시간을 알고 있는 것처럼 말하지 마라.
4. 거리 정보가 없으므로 가장 가까운 병원이라고 단정하지 마라.
5. 현재 자료는 같은 시군구 안의 병원 목록이다.
6. 생명이 위급해 보이면 다른 설명보다 먼저 119 신고를 안내한다.
7. 병원을 추천할 때는 최대 세 곳만 짧게 제시한다.
8. 병원명, 추정 혼잡도, 가용 병상과 전화번호를 함께 말한다.
9. 출발 전에 응급실에 전화하라고 반드시 안내한다.
10. 가용 병상이 있어도 실제 수용이 불가능할 수 있다고 말한다.
11. 조회 결과가 없으면 병원을 지어내지 마라.
12. 치과 응급에서는 치과 전용 진료 가능 여부를 단정하지 마라.
13. 치과 응급은 응급실 병상, 수술실과 CT를 참고한 것이라고 밝혀라.
14. 치과 또는 구강악안면외과 진료 가능 여부를 전화로 확인하라고 안내한다.
15. 답변은 짧고 분명하게 한다.

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

            if isinstance(answer, list):
                answer = "".join(
                    str(part)
                    for part in answer
                )

            answer = str(answer)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

        except Exception:
            friendly_message = (
                "AI 안내를 불러오지 못했습니다. "
                "잠시 후 다시 시도해 주세요. "
                "Solar API 키와 사용 가능 상태를 확인하세요."
            )

            with st.chat_message("assistant"):
                st.warning(friendly_message)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": friendly_message,
                }
            )


# =========================================================
# 16. 하단 안내
# =========================================================
st.divider()

st.caption(
    "자료 출처: 국립중앙의료원 전국 응급의료기관 정보 조회 서비스"
)

st.caption(
    f"현재 앱 화면 시각: "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

st.caption(
    "이 앱은 응급실 가용 병상 정보를 보기 쉽게 정리한 참고용 서비스입니다. "
    "의료진의 진단이나 119 구급상황관리센터의 판단을 대신하지 않습니다."
)
