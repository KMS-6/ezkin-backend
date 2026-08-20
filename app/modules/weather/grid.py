"""위도/경도 → 기상청 격자(nx, ny) 변환. ADR 003.

기상청이 배포하는 Lambert Conformal Conic 변환 공식을 그대로 구현한다. 외부 호출이
없는 순수 함수라 단위 테스트로 알려진 지역의 격자값과 직접 비교해 검증할 수 있다.
"""

import math

# 기상청 공식 변환 파라미터(격자 간격 5km 기준). 출처: 기상청 동네예보 좌표변환
# 프로그램 소스(공공데이터포털 배포본)의 상수를 그대로 옮겼다.
_RE = 6371.00877  # 지구 반경(km)
_GRID = 5.0  # 격자 간격(km)
_SLAT1 = 30.0  # 투영 위도1(degree)
_SLAT2 = 60.0  # 투영 위도2(degree)
_OLON = 126.0  # 기준점 경도(degree)
_OLAT = 38.0  # 기준점 위도(degree)
_XO = 43  # 기준점 X좌표(GRID)
_YO = 136  # 기준점 Y좌표(GRID)

# 서울 기본 좌표 — OnboardingProfile에 위도/경도가 없을 때 폴백용(ADR 003).
SEOUL_LATITUDE = 37.5665
SEOUL_LONGITUDE = 126.9780

_DEGRAD = math.pi / 180.0


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위도(lat)/경도(lon)를 기상청 격자 좌표(nx, ny)로 변환한다."""
    re = _RE / _GRID
    slat1 = _SLAT1 * _DEGRAD
    slat2 = _SLAT2 * _DEGRAD
    olon = _OLON * _DEGRAD
    olat = _OLAT * _DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * _DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * _DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + _XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + _YO + 0.5)
    return nx, ny


# 생활기상지수(UV지수) API는 5km 격자가 아니라 시/도 단위 행정구역코드(10자리)만
# 지원한다. 정밀한 시/군/구 경계 판정 대신 가장 가까운 시/도 중심좌표를 찾는
# 근사치 매핑을 사용한다(경계 근처 지역은 부정확할 수 있음, ADR 003 참고).
_SIDO_CENTROIDS: list[tuple[str, float, float]] = [
    ("1100000000", 37.5665, 126.9780),  # 서울특별시
    ("2600000000", 35.1796, 129.0756),  # 부산광역시
    ("2700000000", 35.8714, 128.6014),  # 대구광역시
    ("2800000000", 37.4563, 126.7052),  # 인천광역시
    ("2900000000", 35.1595, 126.8526),  # 광주광역시
    ("3000000000", 36.3504, 127.3845),  # 대전광역시
    ("3100000000", 35.5384, 129.3114),  # 울산광역시
    ("3600000000", 36.4800, 127.2890),  # 세종특별자치시
    ("4100000000", 37.4138, 127.5183),  # 경기도
    ("4200000000", 37.8228, 128.1555),  # 강원특별자치도
    ("4300000000", 36.6357, 127.4917),  # 충청북도
    ("4400000000", 36.5184, 126.8000),  # 충청남도
    ("4500000000", 35.7175, 127.1530),  # 전북특별자치도
    ("4600000000", 34.8679, 126.9910),  # 전라남도
    ("4700000000", 36.4919, 128.8889),  # 경상북도
    ("4800000000", 35.4606, 128.2132),  # 경상남도
    ("5000000000", 33.4996, 126.5312),  # 제주특별자치도
]


def nearest_sido_area_code(lat: float, lon: float) -> str:
    """위도/경도에 가장 가까운 시/도 중심좌표의 행정구역코드(10자리)를 반환한다."""

    def _distance_sq(centroid: tuple[str, float, float]) -> float:
        _, c_lat, c_lon = centroid
        return (lat - c_lat) ** 2 + (lon - c_lon) ** 2

    return min(_SIDO_CENTROIDS, key=_distance_sq)[0]
