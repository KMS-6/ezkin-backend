"""위도/경도 → 기상청 격자 변환 검증. ADR 003.

외부 호출이 없는 순수 함수라 알려진 기상청 예제 좌표의 격자값과 직접 비교한다.
"""

from app.modules.weather.grid import SEOUL_LATITUDE, SEOUL_LONGITUDE, latlon_to_grid


def test_known_kma_example_coordinate_maps_to_60_127() -> None:
    # 기상청 동네예보 변환 예제로 흔히 인용되는 좌표(서울 종로구 사직동) → (60, 127)
    assert latlon_to_grid(37.583, 126.983) == (60, 127)


def test_seoul_default_coordinate_maps_to_60_127() -> None:
    assert latlon_to_grid(SEOUL_LATITUDE, SEOUL_LONGITUDE) == (60, 127)


def test_busan_coordinate_maps_to_known_grid() -> None:
    assert latlon_to_grid(35.1796, 129.0756) == (98, 76)
