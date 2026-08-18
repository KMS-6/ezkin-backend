import re

CAUSAL_PATTERNS = re.compile(r"(원인입니다|유발했|유발합니다|때문에 생겼|때문에 악화|로 인해 발생)")


def is_safe(text: str) -> bool:
    return not bool(CAUSAL_PATTERNS.search(text))
