"""텍스트 청킹: 300~600자 목표, 100자 오버랩, 문단 경계 우선."""

TARGET_MIN = 300
TARGET_MAX = 600
OVERLAP = 100


def chunk_text(text: str) -> list[str]:
    """문단 경계를 우선하여 텍스트를 청크로 분할한다."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    # 문단을 TARGET_MIN 이상이 될 때까지 병합
    merged: list[str] = []
    buffer = ""
    for para in paragraphs:
        if not buffer:
            buffer = para
        elif len(buffer) < TARGET_MIN:
            buffer = buffer + "\n\n" + para
        else:
            merged.append(buffer)
            buffer = para
    if buffer:
        merged.append(buffer)

    # 병합 결과가 TARGET_MAX 초과하면 강제 분할
    chunks: list[str] = []
    for block in merged:
        if len(block) <= TARGET_MAX:
            chunks.append(block)
        else:
            start = 0
            while start < len(block):
                end = start + TARGET_MAX
                chunks.append(block[start:end])
                start = end - OVERLAP  # 오버랩 적용
                if start >= len(block):
                    break

    return [c for c in chunks if c.strip()]
