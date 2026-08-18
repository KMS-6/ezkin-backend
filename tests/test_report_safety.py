import pytest

from app.modules.reports.safety import is_safe


@pytest.mark.parametrize(
    "text",
    [
        "수면 부족이 홍조의 원인입니다.",
        "건조한 환경이 트러블을 유발했습니다.",
        "스트레스가 피부를 유발합니다.",
        "이 성분 때문에 생겼습니다.",
        "과도한 자외선 때문에 악화됐습니다.",
        "환경 변화로 인해 발생했습니다.",
    ],
)
def test_causal_text_is_not_safe(text):
    assert is_safe(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "지난 14일 중 8일에 홍조 점수가 0.5 이상이었습니다.",
        "이는 이전 14일(3일)보다 높습니다.",
        "홍조 점수 상승일과 수면 5시간 미만이 함께 나타난 경우가 4회 있었습니다.",
        "수분 지수가 0.3 미만인 날이 6일 관찰됐습니다.",
        "권장 사항: 보습제를 아침저녁으로 적용해 보세요.",
    ],
)
def test_safe_text_is_allowed(text):
    assert is_safe(text) is True
