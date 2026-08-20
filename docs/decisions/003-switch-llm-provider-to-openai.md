---
authored_with: Copilot CLI
features_used: []
date: 2026-08-21
---

# ADR 003: LLM 공급자를 Anthropic에서 OpenAI로 전환

## 상태

승인됨

## 맥락

챗봇 저신뢰도 escalation(`app/modules/triggers/llm_escalation.py`), 카메라 스캔 Vision
분석(`app/modules/scans/vision.py`), Morning Briefing/기간 Report 문장 다듬기
(`app/modules/briefings/narration.py`, `app/modules/reports/narration.py`) 네 곳 모두
Anthropic Claude(`anthropic` SDK, `AAC_ANTHROPIC_API_KEY`)를 호출하도록 구현돼 있었다.
운영 중 실제로 발급/보유하고 있는 키가 OpenAI 키였고, 앞으로도 OpenAI를 사용하기로
결정해 네 모듈 전부를 OpenAI로 전환한다.

## 결정

- `anthropic` 의존성을 제거하고 `openai>=3,<4`로 교체한다(`pyproject.toml`).
- `Settings.anthropic_api_key` → `Settings.openai_api_key`로 이름을 바꾼다
  (환경변수 `AAC_ANTHROPIC_API_KEY` → `AAC_OPENAI_API_KEY`).
- `chat_llm_model`/`vision_llm_model`/`narration_llm_model` 기본값을 `gpt-5.4-mini`로
  바꾼다(기존과 동일하게 세 용도 모두 같은 저비용 모델 하나로 통일).
- 네 모듈 모두 Anthropic Messages API(`messages.parse`, `system=`, `output_format=`)
  대신 OpenAI Chat Completions 구조화 출력(`chat.completions.parse`,
  `response_format=`, 시스템 프롬프트는 별도 `role: "system"` 메시지)으로 호출부를
  재작성한다. 이미지 입력은 Anthropic의 `{"type": "image", "source": {"type": "base64", ...}}`
  대신 OpenAI의 `{"type": "image_url", "image_url": {"url": "data:<mime>;base64,<...>"}}`
  포맷을 쓴다.
- 예외 처리(타임아웃/연결 오류/429·5xx 등 일시적 장애를 재시도 가능 실패로, 401/403/404/400을
  서버 로그로만 구분)는 `openai.*Error` 계열로 대체하되 기존과 동일한 분류 로직을 유지한다.
- 카메라 스캔 응답 계약의 `model.provider` 값도 `"anthropic"` → `"openai"`로 바뀐다(프론트가
  이미 이 필드를 그대로 노출만 하고 분기하지 않는다는 전제 — 분기한다면 프론트도 함께
  업데이트해야 한다).
- `render.yaml`/`.env.example`의 `AAC_ANTHROPIC_API_KEY` 항목을 `AAC_OPENAI_API_KEY`로
  바꾼다.

## 고려한 대안

- Anthropic 유지 + OpenAI 병행 지원(공급자 추상화 레이어 도입): 향후 공급자 교체가
  잦을 걸 대비하면 유리하지만, 지금 당장 필요하지도 않고 4개 모듈 모두 구조가 거의
  동일해 추상화 없이도 유지보수 부담이 크지 않다. 요청 범위를 넘는 과설계로 판단해 채택하지
  않았다.
- 응답 계약의 `failure_code`를 공급자별로 세분화: 프론트가 이미 `model_not_implemented`
  단일 코드 기준으로 연동을 마쳤으므로, 이번 전환에서는 응답 계약을 바꾸지 않고 원인 구분은
  서버 로그로만 남긴다(선행 결정, 이 ADR 범위 밖).

## 결과와 트레이드오프

- 네 모듈의 실제 LLM 호출 로직과 관련 테스트(`tests/test_vision.py`,
  `tests/test_llm_escalation.py`, `tests/test_briefing_narration.py`,
  `tests/test_report_narration.py`)를 OpenAI SDK 기준으로 다시 작성했다.
- `tests/conftest.py`에 `openai_api_key`를 매 테스트마다 `None`으로 강제하는 autouse
  fixture를 추가했다 — 로컬 `.env`에 실제 키가 있어도 테스트가 실제 OpenAI API를 호출하는
  비결정적 상태가 되지 않도록 격리하기 위함(이 격리가 없으면 로컬 `.env`에 유효한 키가 있을 때
  일부 테스트가 실제 네트워크 호출 결과에 따라 값이 달라져 실패한다 — 이번 전환 중 실제로
  재현됨).
- 배포 환경(Render)에서는 `AAC_ANTHROPIC_API_KEY` 대신 `AAC_OPENAI_API_KEY`를 새로
  등록해야 한다. 기존 `AAC_ANTHROPIC_API_KEY` 값은 더 이상 읽히지 않는다.
- 모델명(`gpt-5.4-mini`)은 OpenAI Models API로 실제 사용 가능 여부를 확인했고, 실제
  Vision 호출(`chat.completions.parse`)도 로컬에서 200 OK로 검증했다.
