import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from openai import OpenAI
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
    .block-container {
        max-width: 1250px;
        padding-top: 2rem;
        padding-bottom: 5rem;
    }

    .main-banner {
        padding: 28px 30px;
        margin-bottom: 24px;
        border: 1px solid rgba(60, 130, 190, 0.25);
        border-radius: 22px;
        background: linear-gradient(
            135deg,
            rgba(229, 242, 255, 0.96),
            rgba(236, 250, 244, 0.96)
        );
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

    .step-title {
        padding: 14px 18px;
        margin-top: 22px;
        margin-bottom: 14px;
        border-left: 7px solid #3578e5;
        border-radius: 10px;
        background: rgba(53, 120, 229, 0.08);
        font-size: 25px;
        font-weight: 850;
    }

    .map-banner {
        margin-top: 25px;
        margin-bottom: 15px;
        padding: 20px 23px;
        border: 2px solid rgba(32, 125, 210, 0.50);
        border-radius: 17px;
        background: linear-gradient(
            135deg,
            rgba(219, 239, 255, 0.85),
            rgba(239, 249, 255, 0.85)
        );
    }

    .map-banner h3 {
        margin: 0 0 7px 0;
        font-size: 25px;
        font-weight: 900;
    }

    .map-banner p {
        margin: 0;
        line-height: 1.6;
    }

    .selected-hospital-card {
        padding: 18px 20px;
        margin: 12px 0 16px 0;
        border: 3px solid #ff3b30;
        border-radius: 17px;
        background: rgba(255, 59, 48, 0.07);
        box-shadow: 0 5px 18px rgba(255, 59, 48, 0.14);
    }

    .selected-hospital-card h4 {
        margin: 0 0 8px 0;
        font-size: 21px;
        font-weight: 900;
    }

    .selected-hospital-card p {
        margin: 3px 0;
        line-height: 1.55;
    }

    .ai-chat-banner {
        margin-top: 34px;
        margin-bottom: 18px;
        padding: 27px 29px;
        border: 3px solid #6c63ff;
        border-radius: 22px;
        background: linear-gradient(
            135deg,
            rgba(108, 99, 255, 0.18),
            rgba(49, 196, 190, 0.14)
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

    .question-example {
        min-height: 108px;
        padding: 16px;
        border: 1px solid rgba(108, 99, 255, 0.25);
        border-radius: 16px;
        background: rgba(108, 99, 255, 0.07);
        font-size: 15px;
        line-height: 1.55;
    }

    [data-testid="stChatMessage"] {
        padding: 12px 15px;
        margin-bottom: 13px;
        border: 1px solid rgba(108, 99, 255, 0.30);
        border-radius: 17px;
        background: rgba(108, 99, 255, 0.045);
        box-shadow: 0 3px 12px rgba(60, 55, 150, 0.07);
    }

    [data-testid="stChatInput"] {
        border: 3px solid #6c63ff;
        border-radius: 20px;
        background: white;
        box-shadow: 0 7px 22px rgba(108, 99, 255, 0.28);
    }

    [data-testid="stChatInput"] textarea {
        min-height: 52px;
        font-size: 17px;
        font-weight: 600;
    }

    div.stButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        min-height: 46px;
        border-radius: 12px;
        font-weight: 750;
    }

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
# 3. 앱 상단 제목
# =========================================================
st.markdown(
    """
    <div class="main-banner">
        <h1>🏥 실시간 응급실 혼잡도 안내</h1>
        <p>
            현재 지역과 필요한 진료 분야를 입력하면 주변 응급실의
            실시간 가용 병상과 의료시설 정보를 확인할 수 있습니다.<br>
            응급실 위치를 지도에서 비교하고, AI에게 어느 병원에 먼저
            전화할지 질문할 수도 있습니다.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 4. 안전 안내
# =========================================================
st.error(
    """
    **생명이 위급한 상황에서는 이 앱으로 병원을 비교하지 말고 즉시 119에 연락하세요.**

    호흡 곤란, 의식 저하, 심한 출혈, 갑작스러운 마비, 심한 가슴 통증,
    경련, 심각한 알레르기 반응 등이 있으면 바로 119에 도움을 요청해야 합니다.
    """
)

st.info(
    """
    이 앱의 혼잡도는 실제 대기 환자 수나 실제 대기시간이 아닙니다.

    국립중앙의료원 Open API의 응급실 가용 병상과 관련 시설 정보를 바탕으로
    계산한 참고용 추정치입니다. 출발 전 반드시 응급실에 전화해 수용 가능 여부를 확인하세요.
    """
)


# =========================================================
# 5. API 주소와 모델 설정
# =========================================================

# 실시간 응급실 가용병상 조회
EMERGENCY_BED_API_URL = (
    "https://apis.data.go.kr/B552657/"
    "ErmctInfoInqireService/"
    "getEmrrmRltmUsefulSckbdInfoInqire"
)

# 지역별 응급의료기관 위치정보 조회
EMERGENCY_LOCATION_API_URL = (
    "https://apis.data.go.kr/B552657/"
    "ErmctInfoInqireService/"
    "getEgytListInfoInqire"
)

# Solar API
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
            "치과 전용 병상이나 치과 당직 정보는 제공되지 않습니다. "
            "응급실 병상, 수술실과 CT 정보를 참고용으로 확인합니다."
        ),
        "numeric_fields": ["수술실"],
        "yn_fields": ["CT"],
    },
}


# =========================================================
# 8. XML 태그 후보
# =========================================================

# 실시간 병상 API
BED_XML_FIELD_MAP = {
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
}

# 위치정보 API
LOCATION_XML_FIELD_MAP = {
    "기관코드": ["hpid", "HPID"],
    "위치병원명": ["dutyName", "dutyname", "DUTYNAME"],
    "병원주소": ["dutyAddr", "dutyaddr", "DUTYADDR"],
    "대표전화": ["dutyTel1", "dutytel1", "DUTYTEL1"],
    "위치응급실전화": ["dutyTel3", "dutytel3", "DUTYTEL3"],

    "경도": [
        "wgs84Lon",
        "wgs84lon",
        "WGS84LON",
        "wgs84LON",
    ],

    "위도": [
        "wgs84Lat",
        "wgs84lat",
        "WGS84LAT",
        "wgs84LAT",
    ],
}


# =========================================================
# 9. 세션 상태 초기화
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

if "selected_hpid" not in st.session_state:
    st.session_state.selected_hpid = ""

if "selected_hospital_name" not in st.session_state:
    st.session_state.selected_hospital_name = ""


# =========================================================
# 10. 기본 변환 함수
# =========================================================
def get_secret(name):
    """
    Streamlit 비밀 금고의 값을 안전하게 불러옵니다.
    """
    try:
        return str(st.secrets[name]).strip()
    except (KeyError, FileNotFoundError):
        return ""


def safe_text_any(element, tag_candidates, default=""):
    """
    XML 태그 후보를 차례로 확인해 값을 읽습니다.
    XML은 대소문자를 구분합니다.
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


def to_float(value, default=None):
    """
    위도와 경도를 안전하게 실수로 변환합니다.
    """
    if value is None:
        return default

    text = str(value).strip().replace(",", "")

    if not text:
        return default

    try:
        return float(text)
    except (ValueError, TypeError):
        return default


def normalize_yes_no(value):
    """
    Y와 N을 보기 쉬운 한국어로 바꿉니다.
    """
    text = str(value).strip().upper()

    if text == "Y":
        return "가능"

    if text == "N":
        return "불가"

    return "정보 없음"


def normalize_api_key(api_key):
    """
    인증키가 URL 인코딩된 형태일 경우 먼저 해제합니다.
    """
    return urllib.parse.unquote(str(api_key).strip())


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

    aliases = sorted(
        SIDO_ALIASES.keys(),
        key=len,
        reverse=True,
    )

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

    if found_sido == "세종특별자치시" and not sigungu:
        sigungu = "세종특별자치시"

    return found_sido, sigungu


# =========================================================
# 11. 재시도 기능이 적용된 HTTP 연결
# =========================================================
@st.cache_resource
def get_http_session():
    """
    공공데이터 서버가 순간적으로 실패하면 자동으로 재시도하는
    requests 세션을 만듭니다.
    """
    retry_policy = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry_policy,
        pool_connections=10,
        pool_maxsize=10,
    )

    session = requests.Session()

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/xml, text/xml",
        }
    )

    return session


def request_xml(base_url, parameters):
    """
    공공데이터 API를 호출한 뒤 XML 최상위 요소를 반환합니다.

    연결 제한시간과 응답 제한시간을 각각 설정하여
    앱이 지나치게 오래 멈추지 않도록 합니다.
    """
    session = get_http_session()

    try:
        response = session.get(
            base_url,
            params=parameters,

            # 연결은 최대 4초, 응답 읽기는 최대 8초입니다.
            timeout=(4, 8),
        )

    except requests.exceptions.ConnectTimeout as error:
        raise RuntimeError(
            "공공데이터 서버 연결 시간이 초과되었습니다."
        ) from error

    except requests.exceptions.ReadTimeout as error:
        raise RuntimeError(
            "공공데이터 서버의 응답이 너무 늦습니다."
        ) from error

    except requests.exceptions.SSLError as error:
        raise RuntimeError(
            "공공데이터 서버와 보안 연결을 만들지 못했습니다."
        ) from error

    except requests.exceptions.ConnectionError as error:
        raise RuntimeError(
            "공공데이터 서버에 연결하지 못했습니다."
        ) from error

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"공공데이터 요청 중 네트워크 오류가 발생했습니다: {error}"
        ) from error

    if response.status_code == 429:
        raise RuntimeError(
            "짧은 시간에 API 요청이 너무 많이 발생했습니다."
        )

    if response.status_code in [500, 502, 503, 504]:
        raise RuntimeError(
            f"공공데이터 서버가 일시적으로 불안정합니다. "
            f"상태 코드: {response.status_code}"
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"공공데이터 요청이 거절되었습니다. "
            f"상태 코드: {response.status_code}"
        )

    if not response.content:
        raise RuntimeError(
            "공공데이터 서버가 빈 응답을 반환했습니다."
        )

    try:
        root = ET.fromstring(response.content)

    except ET.ParseError as error:
        preview = response.text[:300]

        raise RuntimeError(
            "공공데이터 응답을 XML로 읽지 못했습니다. "
            f"응답 일부: {preview}"
        ) from error

    result_code = root.findtext(".//resultCode")

    result_message = (
        root.findtext(".//resultMsg")
        or root.findtext(".//resultMag")
        or ""
    )

    if result_code and result_code != "00":
        error_message = f"{result_code} / {result_message}"

        if "LIMITED_NUMBER" in result_message:
            raise RuntimeError(
                "공공데이터 API의 일일 호출 한도를 초과했습니다."
            )

        if "SERVICE_KEY" in result_message:
            raise RuntimeError(
                "공공데이터 인증키가 정상적으로 인식되지 않았습니다."
            )

        if "ACCESS_DENIED" in result_message:
            raise RuntimeError(
                "해당 공공데이터 API를 사용할 권한이 없습니다."
            )

        raise RuntimeError(
            f"공공데이터 API 오류: {error_message}"
        )

    return root


# =========================================================
# 12. 실시간 병상 API
# =========================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_emergency_beds(api_key, sido, sigungu):
    """
    실시간 응급실 병상정보를 조회합니다.

    같은 지역의 결과는 1분 동안 캐시에 저장합니다.
    """
    parameters = {
        "serviceKey": normalize_api_key(api_key),
        "STAGE1": sido,
        "STAGE2": sigungu,
        "pageNo": 1,
        "numOfRows": 50,
    }

    root = request_xml(
        EMERGENCY_BED_API_URL,
        parameters,
    )

    items = root.findall(".//item")
    rows = []

    for item in items:
        row = {}

        for korean_name, tag_candidates in BED_XML_FIELD_MAP.items():
            row[korean_name] = safe_text_any(
                item,
                tag_candidates,
                default="",
            )

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


# =========================================================
# 13. 위치정보 API
# =========================================================
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_emergency_locations(api_key, sido, sigungu):
    """
    병원 주소와 위도·경도를 조회합니다.

    위치정보는 자주 바뀌지 않으므로 24시간 캐시합니다.
    이 API가 실패하더라도 병상 결과는 계속 표시됩니다.
    """
    parameters = {
        "serviceKey": normalize_api_key(api_key),
        "Q0": sido,
        "Q1": sigungu,
        "pageNo": 1,
        "numOfRows": 50,
    }

    root = request_xml(
        EMERGENCY_LOCATION_API_URL,
        parameters,
    )

    items = root.findall(".//item")
    rows = []

    for item in items:
        row = {}

        for korean_name, tag_candidates in LOCATION_XML_FIELD_MAP.items():
            row[korean_name] = safe_text_any(
                item,
                tag_candidates,
                default="",
            )

        row["위도"] = to_float(row.get("위도"))
        row["경도"] = to_float(row.get("경도"))

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    location_df = pd.DataFrame(rows)

    if "기관코드" in location_df.columns:
        location_df = location_df.drop_duplicates(
            subset=["기관코드"],
            keep="first",
        )

    return location_df


# =========================================================
# 14. 병상정보와 위치정보 결합
# =========================================================
def merge_bed_and_location_data(bed_df, location_df):
    """
    기관코드를 기준으로 실시간 병상정보와 위치정보를 합칩니다.
    """
    if bed_df.empty:
        return bed_df

    result_df = bed_df.copy()

    if location_df.empty:
        result_df["병원주소"] = ""
        result_df["대표전화"] = ""
        result_df["위도"] = None
        result_df["경도"] = None
        return result_df

    result_df = result_df.merge(
        location_df,
        on="기관코드",
        how="left",
    )

    if "위치병원명" in result_df.columns:
        missing_name = (
            result_df["병원명"].isna()
            | result_df["병원명"].eq("")
            | result_df["병원명"].eq("병원명 정보 없음")
        )

        result_df.loc[missing_name, "병원명"] = (
            result_df.loc[missing_name, "위치병원명"]
        )

    if "위치응급실전화" in result_df.columns:
        missing_phone = (
            result_df["응급실전화"].isna()
            | result_df["응급실전화"].eq("")
            | result_df["응급실전화"].eq("전화번호 정보 없음")
        )

        result_df.loc[missing_phone, "응급실전화"] = (
            result_df.loc[missing_phone, "위치응급실전화"]
        )

    result_df["병원명"] = result_df["병원명"].fillna(
        "병원명 정보 없음"
    )

    result_df["응급실전화"] = result_df["응급실전화"].fillna(
        "전화번호 정보 없음"
    )

    result_df["병원주소"] = result_df["병원주소"].fillna("")
    result_df["대표전화"] = result_df["대표전화"].fillna("")

    result_df["위도"] = result_df["위도"].apply(to_float)
    result_df["경도"] = result_df["경도"].apply(to_float)

    return result_df


# =========================================================
# 15. 혼잡도 계산
# =========================================================
def calculate_crowding(row, department):
    """
    가용 병상과 관련 시설을 이용해 참고용 혼잡도를 계산합니다.
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

    # 필요한 시설이 불가능한 경우 한 단계 주의 상태로 조정합니다.
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


# =========================================================
# 16. 오류 안내
# =========================================================
def show_api_error(error):
    """
    오류 종류에 따라 사용자에게 이해하기 쉬운 안내를 보여줍니다.
    """
    error_text = str(error)
    lower_text = error_text.lower()

    if "일일 호출 한도" in error_text:
        st.error(
            "오늘 사용할 수 있는 공공데이터 API 호출 횟수를 초과했습니다. "
            "공공데이터포털에서 운영계정 전환 또는 트래픽 증가를 신청해 주세요."
        )

    elif "인증키" in error_text:
        st.error(
            "공공데이터 인증키가 정상적으로 인식되지 않았습니다. "
            "Streamlit 비밀 금고의 Emergency_API_KEY를 확인해 주세요."
        )

    elif "권한" in error_text:
        st.error(
            "해당 API 사용 권한이 없습니다. "
            "공공데이터포털의 활용신청 상태를 확인해 주세요."
        )

    elif "요청이 너무 많이" in error_text or "429" in error_text:
        st.error(
            "짧은 시간에 API 요청이 너무 많이 발생했습니다. "
            "잠시 기다린 뒤 다시 조회해 주세요."
        )

    elif (
        "연결 시간이 초과" in error_text
        or "응답이 너무 늦" in error_text
        or "연결하지 못했습니다" in error_text
        or "불안정" in error_text
        or "timeout" in lower_text
    ):
        st.error(
            "공공데이터 서버와의 연결이 일시적으로 불안정합니다. "
            "입력값이나 인증키 문제라기보다 외부 서버 문제일 수 있습니다. "
            "잠시 후 다시 시도해 주세요."
        )

    else:
        st.error(
            "응급실 정보를 불러오지 못했습니다. "
            "잠시 후 다시 시도해 주세요."
        )

    with st.expander("개발용 오류 내용 보기"):
        st.code(error_text)


# =========================================================
# 17. 지도 처리 함수
# =========================================================
def get_map_color(crowding_level):
    """
    혼잡도에 따라 지도 표식 색상을 반환합니다.
    """
    color_map = {
        "원활": [35, 180, 90, 205],
        "보통": [255, 190, 20, 215],
        "혼잡": [255, 120, 20, 225],
        "매우 혼잡": [220, 45, 45, 235],
    }

    return color_map.get(
        crowding_level,
        [100, 130, 160, 190],
    )


def prepare_map_dataframe(df):
    """
    유효한 위도와 경도가 있는 병원만 지도 데이터로 정리합니다.
    지도 성능을 위해 최대 30개만 표시합니다.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    map_df = df.head(30).copy()

    map_df["위도"] = pd.to_numeric(
        map_df["위도"],
        errors="coerce",
    )

    map_df["경도"] = pd.to_numeric(
        map_df["경도"],
        errors="coerce",
    )

    map_df = map_df.dropna(
        subset=["위도", "경도"]
    )

    map_df = map_df[
        map_df["위도"].between(32, 39)
        & map_df["경도"].between(124, 132)
    ].copy()

    if map_df.empty:
        return map_df

    map_df["지도색상"] = map_df["혼잡도"].apply(
        get_map_color
    )

    map_df["주소표시"] = map_df["병원주소"].replace(
        "",
        "주소 정보 없음",
    )

    return map_df


def create_hospital_map(map_df, selected_hpid):
    """
    전체 병원과 선택 병원을 지도에 표시합니다.
    선택 병원은 큰 빨간색 원으로 강조합니다.
    """
    selected_df = map_df[
        map_df["기관코드"].astype(str) == str(selected_hpid)
    ].copy()

    if selected_df.empty:
        selected_df = map_df.head(1).copy()

    center_latitude = float(selected_df.iloc[0]["위도"])
    center_longitude = float(selected_df.iloc[0]["경도"])

    all_hospitals_layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[경도, 위도]",
        get_fill_color="지도색상",
        get_line_color=[255, 255, 255, 235],
        get_radius=90,
        radius_min_pixels=7,
        radius_max_pixels=18,
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=True,
        auto_highlight=True,
    )

    selected_outer_layer = pdk.Layer(
        "ScatterplotLayer",
        data=selected_df,
        get_position="[경도, 위도]",
        get_fill_color=[255, 45, 45, 70],
        get_line_color=[255, 0, 0, 255],
        get_radius=230,
        radius_min_pixels=21,
        radius_max_pixels=35,
        line_width_min_pixels=5,
        stroked=True,
        filled=True,
        pickable=True,
    )

    selected_center_layer = pdk.Layer(
        "ScatterplotLayer",
        data=selected_df,
        get_position="[경도, 위도]",
        get_fill_color=[255, 255, 255, 255],
        get_line_color=[190, 0, 0, 255],
        get_radius=55,
        radius_min_pixels=7,
        radius_max_pixels=12,
        line_width_min_pixels=3,
        stroked=True,
        filled=True,
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=center_latitude,
        longitude=center_longitude,
        zoom=12,
        pitch=0,
    )

    tooltip = {
        "html": """
        <div style="font-size:14px; line-height:1.55;">
            <b style="font-size:16px;">{병원명}</b><br>
            추정 혼잡도: <b>{혼잡도표시}</b><br>
            응급실 가용 병상: <b>{응급실}개</b><br>
            주소: {주소표시}<br>
            응급실 전화: {응급실전화}
        </div>
        """,
        "style": {
            "backgroundColor": "rgba(25, 30, 40, 0.94)",
            "color": "white",
            "borderRadius": "10px",
            "padding": "10px",
        },
    }

    return pdk.Deck(
        layers=[
            all_hospitals_layer,
            selected_outer_layer,
            selected_center_layer,
        ],
        initial_view_state=view_state,
        map_style=(
            "https://basemaps.cartocdn.com/"
            "gl/positron-gl-style/style.json"
        ),
        tooltip=tooltip,
    )


# =========================================================
# 18. Solar AI 관련 함수
# =========================================================
def get_solar_client():
    """
    Solar API 클라이언트를 만듭니다.
    """
    solar_api_key = get_secret("SOLAR_API_KEY")

    if not solar_api_key:
        return None

    return OpenAI(
        api_key=solar_api_key,
        base_url=SOLAR_BASE_URL,
    )


def make_ai_hospital_context(
    df,
    location,
    department,
    symptom,
    selected_hospital_name,
):
    """
    조회 결과를 AI가 읽을 수 있는 글로 정리합니다.
    """
    if df is None or df.empty:
        return "현재 조회된 응급실 정보가 없습니다."

    lines = [
        f"사용자가 입력한 위치: {location}",
        f"선택한 진료 분야: {department}",
        f"입력한 증상: {symptom or '입력하지 않음'}",
        f"지도에서 선택한 병원: {selected_hospital_name or '선택하지 않음'}",
        "",
        "현재 조회된 응급실 정보:",
    ]

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
                f"주소: {row.get('병원주소', '정보 없음')}, "
                f"정보 입력 시각: {row.get('입력일시', '정보 없음')}"
            )
        )

    lines.extend(
        [
            "",
            "주의:",
            "- 혼잡도는 실제 대기시간이 아니라 가용 병상 기반 추정치다.",
            "- 같은 시군구 안의 병원이며 사용자와의 정확한 거리순이 아니다.",
            "- 출발 전에 병원에 전화해 수용 가능 여부를 확인해야 한다.",
            "- 생명이 위급하면 병원 비교보다 119 신고를 우선해야 한다.",
            "- 치과 응급은 치과 전용 진료 가능 정보를 제공하지 않는다.",
        ]
    )

    return "\n".join(lines)


def stream_solar_answer(client, messages):
    """
    Solar 답변을 스트리밍 방식으로 전달합니다.
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
# 19. 검색 입력 폼
# =========================================================
st.markdown(
    '<div class="step-title">1단계 · 현재 위치와 증상 입력</div>',
    unsafe_allow_html=True,
)

st.write(
    "시도와 시군구를 함께 입력하세요. "
    "예: `서울 강남구`, `경기도 수원시`, `부산 해운대구`"
)

department_names = list(DEPARTMENT_RULES.keys())

saved_department = st.session_state.search_department

if saved_department not in department_names:
    saved_department = "일반 응급"

# form을 사용하면 사용자가 글자를 입력할 때마다
# 앱 전체가 반복 실행되는 현상을 줄일 수 있습니다.
with st.form("emergency_search_form"):
    location_input = st.text_input(
        "현재 위치",
        value=st.session_state.search_location,
        placeholder="예: 서울 강남구 역삼동",
    )

    department = st.selectbox(
        "필요하다고 생각하는 응급 진료 분야",
        options=department_names,
        index=department_names.index(saved_department),
    )

    symptom = st.text_area(
        "현재 증상 또는 상황",
        value=st.session_state.search_symptom,
        placeholder=(
            "예: 갑자기 가슴이 조이듯 아픕니다. "
            "언제부터 시작되었는지와 현재 상태를 간단히 적어 주세요."
        ),
        height=105,
    )

    search_button = st.form_submit_button(
        "🔍 주변 응급실 실시간 조회",
        type="primary",
        use_container_width=True,
    )

st.caption(DEPARTMENT_RULES[department]["description"])

if department == "치과 응급":
    st.warning(
        """
        **치과 응급 안내**

        이 API에는 치과 당직 여부나 구강악안면외과 진료 가능 여부가 포함되지 않습니다.
        응급실 병상, 수술실과 CT 정보를 참고용으로 보여줍니다.

        심한 얼굴 외상, 턱 골절 의심, 멈추지 않는 출혈 또는 호흡 곤란이 있으면
        즉시 119에 연락하거나 응급실에 전화하세요.
        """
    )


# =========================================================
# 20. 응급실 조회 실행
# =========================================================
if search_button:
    parsed_sido, parsed_sigungu = parse_location(
        location_input
    )

    if not location_input.strip():
        st.warning("현재 위치를 입력해 주세요.")

    elif not parsed_sido or not parsed_sigungu:
        st.warning(
            "시도와 시군구를 함께 입력해 주세요. "
            "예: 서울 강남구 또는 경기도 수원시"
        )

    else:
        emergency_api_key = get_secret(
            "Emergency_API_KEY"
        )

        if not emergency_api_key:
            st.error(
                "응급실 API 키가 설정되지 않았습니다. "
                "Streamlit 비밀 금고에 Emergency_API_KEY를 등록해 주세요."
            )

        else:
            try:
                # 가장 중요한 병상정보를 먼저 조회합니다.
                with st.spinner(
                    "실시간 응급실 병상 정보를 확인하고 있습니다..."
                ):
                    bed_df = fetch_emergency_beds(
                        api_key=emergency_api_key,
                        sido=parsed_sido,
                        sigungu=parsed_sigungu,
                    )

                if bed_df.empty:
                    st.session_state.emergency_df = pd.DataFrame()

                    st.warning(
                        "해당 지역에서 조회된 응급실 정보가 없습니다. "
                        "시군구 이름을 확인하거나 인접 지역으로 다시 검색해 주세요."
                    )

                else:
                    # 위치정보는 별도로 조회합니다.
                    # 위치 API가 실패해도 병상 결과는 계속 표시합니다.
                    try:
                        with st.spinner(
                            "병원 위치정보를 확인하고 있습니다..."
                        ):
                            location_df = fetch_emergency_locations(
                                api_key=emergency_api_key,
                                sido=parsed_sido,
                                sigungu=parsed_sigungu,
                            )

                    except Exception as location_error:
                        location_df = pd.DataFrame()

                        st.warning(
                            "실시간 병상정보는 불러왔지만 병원 위치정보 서버에 "
                            "연결하지 못했습니다. 병상 결과는 정상적으로 표시하며, "
                            "이번 조회에서는 지도가 생략될 수 있습니다."
                        )

                        with st.expander("지도 조회 오류 내용 보기"):
                            st.code(str(location_error))

                    result_df = merge_bed_and_location_data(
                        bed_df=bed_df,
                        location_df=location_df,
                    )

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

                    st.session_state.selected_hpid = str(
                        result_df.iloc[0].get(
                            "기관코드",
                            "",
                        )
                    )

                    st.session_state.selected_hospital_name = str(
                        result_df.iloc[0].get(
                            "병원명",
                            "",
                        )
                    )

                    st.success(
                        f"{parsed_sido} {parsed_sigungu}에서 "
                        f"응급실 {len(result_df)}곳을 조회했습니다."
                    )

            except Exception as error:
                # 이전 검색 결과를 그대로 남기지 않도록 비웁니다.
                st.session_state.emergency_df = pd.DataFrame()
                show_api_error(error)


# =========================================================
# 21. 조회 결과
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
        "병원주소",
        "응급실전화",
        "응급실",
    ]

    for field in rule["numeric_fields"]:
        if field in result_df.columns and field not in display_columns:
            display_columns.append(field)

    for field in rule["yn_fields"]:
        if field in result_df.columns and field not in display_columns:
            display_columns.append(field)

    display_columns.append("입력일시")

    display_columns = [
        column
        for column in display_columns
        if column in result_df.columns
    ]

    display_df = result_df[
        display_columns
    ].copy()

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


# =========================================================
# 22. 응급실 지도
# =========================================================
if not result_df.empty:
    st.markdown(
        """
        <div class="map-banner">
            <h3>🗺️ 응급실 위치 지도</h3>
            <p>
                지도에서 확인할 병원을 선택하세요.
                선택한 응급실은 큰 빨간색 표식으로 강조됩니다.
                지도 위의 표식에 마우스를 올리면 병원 정보를 확인할 수 있습니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    map_df = prepare_map_dataframe(
        result_df
    )

    if map_df.empty:
        st.warning(
            "병상정보는 정상적으로 조회했지만 사용할 수 있는 병원 좌표가 없어 "
            "이번 결과에서는 지도를 표시하지 못했습니다."
        )

    else:
        map_df["선택표시"] = map_df.apply(
            lambda row: (
                f"{row['혼잡도표시']} · "
                f"{row['병원명']} · "
                f"가용 병상 {row['응급실']}개"
            ),
            axis=1,
        )

        display_to_hpid = dict(
            zip(
                map_df["선택표시"],
                map_df["기관코드"].astype(str),
            )
        )

        hpid_to_display = dict(
            zip(
                map_df["기관코드"].astype(str),
                map_df["선택표시"],
            )
        )

        current_hpid = str(
            st.session_state.selected_hpid
        )

        if current_hpid not in hpid_to_display:
            current_hpid = str(
                map_df.iloc[0]["기관코드"]
            )

        display_options = list(
            display_to_hpid.keys()
        )

        selected_display = st.selectbox(
            "지도에서 강조할 응급실",
            options=display_options,
            index=display_options.index(
                hpid_to_display[current_hpid]
            ),
        )

        selected_hpid = display_to_hpid[
            selected_display
        ]

        st.session_state.selected_hpid = selected_hpid

        selected_row = map_df[
            map_df["기관코드"].astype(str) == selected_hpid
        ].iloc[0]

        st.session_state.selected_hospital_name = str(
            selected_row.get(
                "병원명",
                "",
            )
        )

        selected_address = (
            selected_row.get("병원주소")
            or "주소 정보 없음"
        )

        selected_phone = (
            selected_row.get("응급실전화")
            or "전화번호 정보 없음"
        )

        st.markdown(
            f"""
            <div class="selected-hospital-card">
                <h4>📍 지도에서 선택한 응급실</h4>
                <p><strong>{selected_row.get("병원명", "정보 없음")}</strong></p>
                <p>
                    {selected_row.get("혼잡도표시", "정보 없음")}
                    · 응급실 가용 병상
                    <strong>{selected_row.get("응급실", 0)}개</strong>
                </p>
                <p>주소: {selected_address}</p>
                <p>응급실 전화: <strong>{selected_phone}</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        map_deck = create_hospital_map(
            map_df=map_df,
            selected_hpid=selected_hpid,
        )

        st.pydeck_chart(
            map_deck,
            use_container_width=True,
            height=550,
        )

        legend_col1, legend_col2, legend_col3, legend_col4 = st.columns(4)

        legend_col1.success("🟢 원활")
        legend_col2.warning("🟡 보통")
        legend_col3.warning("🟠 혼잡")
        legend_col4.error("🔴 매우 혼잡")

        st.caption(
            "표식 색상은 가용 병상 기반 추정 혼잡도입니다. "
            "큰 빨간 테두리는 현재 선택한 병원입니다."
        )


# =========================================================
# 23. 병원별 상세정보
# =========================================================
if not result_df.empty:
    st.subheader("🏨 병원별 자세한 정보")

    active_department = st.session_state.search_department

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
            st.markdown(f"### {hospital_name}")

            st.markdown(
                f"**☎ 응급실 전화번호: {phone_number}**"
            )

            st.write(
                f"**주소:** "
                f"{row.get('병원주소') or '주소 정보 없음'}"
            )

            left, right = st.columns(2)

            with left:
                st.write(
                    f"**응급실 가용 병상:** "
                    f"{emergency_beds}개"
                )

                st.write(
                    f"**수술실:** "
                    f"{row.get('수술실', 0)}개"
                )

                st.write(
                    f"**일반 중환자실:** "
                    f"{row.get('일반중환자실', 0)}개"
                )

                st.write(
                    f"**입원실:** "
                    f"{row.get('입원실', 0)}개"
                )

                st.write(
                    f"**선택 분야 관련 병상 합계:** "
                    f"{row.get('관련병상합계', 0)}개"
                )

            with right:
                st.write(
                    f"**CT:** "
                    f"{row.get('CT', '정보 없음')}"
                )

                st.write(
                    f"**MRI:** "
                    f"{row.get('MRI', '정보 없음')}"
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

            navigation_query = urllib.parse.quote(
                hospital_name
            )

            st.link_button(
                "🧭 네이버 지도에서 병원 검색",
                (
                    "https://map.naver.com/p/search/"
                    f"{navigation_query}"
                ),
                use_container_width=True,
            )

            if active_department == "치과 응급":
                st.info(
                    "치과나 구강악안면외과의 실제 진료 가능 여부는 "
                    "이 데이터로 알 수 없습니다. "
                    "전화로 치과 응급진료 가능 여부를 확인하세요."
                )

            st.warning(
                "출발 전 위 전화번호로 연락하여 "
                "현재 증상에 대한 수용 가능 여부를 확인하세요."
            )


# =========================================================
# 24. AI 상담
# =========================================================
st.divider()

st.markdown(
    """
    <div class="ai-chat-banner">
        <h2>🤖 3단계 · AI 응급실 추천 상담</h2>
        <p>
            위에서 조회한 실시간 병상과 병원 위치정보를 바탕으로,
            어느 응급실에 먼저 전화할지 AI에게 물어보세요.<br>
            병원명, 추정 혼잡도, 가용 병상, 주소와 전화번호를 비교해 안내합니다.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.session_state.emergency_df.empty:
    st.warning(
        "먼저 현재 위치와 진료 분야를 입력한 뒤 응급실을 조회해 주세요."
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

    if st.session_state.selected_hospital_name:
        st.info(
            "현재 지도에서 선택한 병원: "
            f"**{st.session_state.selected_hospital_name}**"
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
            <strong>선택 병원 확인</strong><br><br>
            지도에서 선택한 병원과 다른 병원을 비교해줘.
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
            selected_hospital_name=(
                st.session_state.selected_hospital_name
            ),
        )

        system_prompt = f"""
너는 냉철한, 단답형, 시크한 성격이야.
반드시 순수 한국어로만 답해.

너는 사용자가 조회한 실시간 응급실 가용 병상과 병원 위치정보를
정리하는 안내 도우미다.

반드시 지켜야 할 규칙:
1. 의학적 진단을 내리지 마라.
2. 약물 복용량이나 치료 방법을 지시하지 마라.
3. 실제 대기시간을 알고 있는 것처럼 말하지 마라.
4. 사용자의 정확한 좌표가 없으므로 가장 가까운 병원이라고 단정하지 마라.
5. 현재 자료는 같은 시군구 안의 병원 목록이다.
6. 생명이 위급해 보이면 다른 설명보다 먼저 119 신고를 안내한다.
7. 병원을 추천할 때는 최대 세 곳만 짧게 제시한다.
8. 병원명, 추정 혼잡도, 가용 병상, 주소와 전화번호를 함께 말한다.
9. 출발 전에 응급실에 전화하라고 반드시 안내한다.
10. 가용 병상이 있어도 실제 수용이 불가능할 수 있다고 말한다.
11. 조회 결과가 없으면 병원을 지어내지 마라.
12. 치과 응급에서는 치과 전용 진료 가능 여부를 단정하지 마라.
13. 치과 응급은 응급실 병상, 수술실과 CT를 참고한 것이라고 밝혀라.
14. 치과 또는 구강악안면외과 진료 가능 여부를 전화로 확인하라고 안내한다.
15. 지도에서 선택한 병원이 있으면 사용자의 질문에 따라 그 병원을 먼저 설명한다.
16. 답변은 짧고 분명하게 한다.

현재 앱의 조회 자료:
{hospital_context}
""".strip()

        api_messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        api_messages.extend(
            st.session_state.messages
        )

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
# 25. 사이드바 관리 도구
# =========================================================
st.sidebar.header("앱 관리")

if st.sidebar.button(
    "캐시 초기화",
    use_container_width=True,
):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.sidebar.success("캐시를 초기화했습니다.")
    st.rerun()

st.sidebar.caption(
    "공공데이터 서버가 일시적으로 실패한 뒤 같은 오류가 반복되면 "
    "캐시를 초기화하고 다시 조회해 보세요."
)


# =========================================================
# 26. 하단 안내
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
    "이 앱은 응급실 가용 병상과 위치정보를 보기 쉽게 정리한 참고용 서비스입니다. "
    "의료진의 진단이나 119 구급상황관리센터의 판단을 대신하지 않습니다."
)
