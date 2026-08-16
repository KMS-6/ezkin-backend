from app.modules.knowledge.chunker import TARGET_MAX, chunk_text


def test_empty_text_returns_empty() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_single_chunk() -> None:
    text = "짧은 텍스트"
    result = chunk_text(text)
    assert len(result) == 1
    assert result[0] == "짧은 텍스트"


def test_small_paragraphs_merged() -> None:
    """300자 미만 문단들은 병합된다."""
    para1 = "A" * 100
    para2 = "B" * 100
    text = para1 + "\n\n" + para2
    result = chunk_text(text)
    # 합이 200자 < 300이므로 하나로 병합
    assert len(result) == 1
    assert "A" in result[0] and "B" in result[0]


def test_large_text_split_with_overlap() -> None:
    """600자 초과 블록은 분할되고 오버랩이 적용된다."""
    big = "X" * 1200
    result = chunk_text(big)
    assert len(result) >= 2
    for chunk in result:
        assert len(chunk) <= TARGET_MAX
    # 두 번째 청크는 첫 번째 끝 100자를 포함해야 함 (오버랩)
    assert result[1][:100] == result[0][-100:]


def test_paragraph_boundary_respected() -> None:
    """문단 경계를 존중하면서 청크를 만든다."""
    # 각 문단이 300~400자인 경우: 각각 하나의 청크
    para1 = "가" * 350
    para2 = "나" * 350
    text = para1 + "\n\n" + para2
    result = chunk_text(text)
    # 두 문단을 합치면 700자 > TARGET_MAX(600)이므로 두 개 이상 청크
    assert len(result) >= 2


def test_chunk_sizes_within_range() -> None:
    """분할 후 각 청크의 길이 검증 (마지막 청크 제외)."""
    big_para = "테스트 텍스트 " * 200  # ~1400자
    result = chunk_text(big_para)
    assert len(result) > 1
    for chunk in result[:-1]:
        assert len(chunk) <= TARGET_MAX


def test_three_paragraphs_merge_boundary() -> None:
    """TARGET_MIN(300) 미만 버퍼는 다음 문단과 병합되고, 300자 이상이 되면 새 청크로 분리된다."""
    # para1(150자) + para2(160자) = 312자 (>= 300자) -> 1번 청크로 병합
    # para3(200자)는 새 청크로 분리
    para1 = "A" * 150
    para2 = "B" * 160
    para3 = "C" * 200
    text = f"{para1}\n\n{para2}\n\n{para3}"

    result = chunk_text(text)
    assert len(result) == 2
    assert result[0] == f"{para1}\n\n{para2}"
    assert result[1] == para3


def test_four_short_paragraphs_merge_until_min() -> None:
    """여러 개의 짧은 문단들이 TARGET_MIN 도달할 때까지 연속 병합된다."""
    # 80자 4개: 80 -> 162 -> 244 -> 326 (모두 합쳐져 단일 청크)
    paras = [f"문단{i} " + "글" * 74 for i in range(4)]
    text = "\n\n".join(paras)

    result = chunk_text(text)
    assert len(result) == 1
    for p in paras:
        assert p in result[0]
