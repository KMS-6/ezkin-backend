---
authored_with: Copilot CLI
features_used: []
date: 2026-08-21
---

# ADR 004: 실사용자를 페르소나로 매핑해 페르소나 전용 도메인 모듈에 편입

## 상태

승인됨

## 맥락

Briefing, Skin Scan, Daily Metrics, Risk(Analysis), Reports(Pattern Analysis 포함) 등
대부분의 도메인 모듈은 `X-Mock-Persona-Id` 헤더로 식별되는 `Persona`(문자열 id,
`personas` 테이블 seed 데이터)만으로 동작하며, 실사용자(`User`, UUID id, 실사용자
등록/인증 토큰)와는 아무 연결 고리가 없었다. 각 도메인 테이블(`briefing`, `scan`,
`metrics`, `report` 등)은 모두 `persona_id`(FK to `personas.id`)만 갖고 `user_id`
FK가 없어, 실사용자 인증 토큰을 받아도 이 기능들을 자신의 데이터로 호출할 방법이
없었다.

## 결정

각 도메인 테이블에 `user_id` 컬럼을 새로 추가하는 대신, 실사용자 인증 토큰이 있으면
`persona_id = str(user_id)`로 사용해 해당 사용자 전용 `Persona` row를 최초 요청 시
지연 생성한다(`app/core/mock_persona._get_or_create_user_persona`). 기존
`get_persona`/`get_persona_id` 의존성 하나만 이중 인증(실사용자 인증 토큰 우선,
없으면 `X-Mock-Persona-Id`)을 지원하도록 바꿔, 이를 사용하는 모든 모듈(약 10개)의
라우터/서비스 코드는 전혀 수정하지 않고 그대로 재사용한다. `personas.id`,
`generations.persona_id` 컬럼 폭은 UUID 문자열(36자)을 수용하도록 30→36자로
확장했다(Alembic `20260821_0017`).

## 고려한 대안

- 각 도메인 테이블에 `user_id`(UUID FK) 컬럼을 추가하고 `persona_id`와 XOR 제약으로
  분리: 데이터 모델은 명확해지지만 마이그레이션과 10개 모듈의 라우터·서비스 로직을
  모두 수정해야 해 작업량이 크다.
- 실사용자 요청마다 임시 페르소나를 생성하지 않고 매번 조회 실패 시 400 반환: 실사용자
  가입만으로는 기능을 쓸 수 없어 사용자 경험이 나쁘다.

## 결과와 트레이드오프

- 실사용자는 회원가입 시 발급받은 인증 토큰만으로 Briefing/Skin Scan/Daily
  Metrics/Risk/Reports 등 페르소나 전용 기능을 자신의 데이터로 즉시 호출할 수 있다.
  `X-Mock-Persona-Id`를 함께 보내도 인증 토큰이 우선한다.
- 장기 사용자 데모(`persona_001/002/003`, seed 데이터)는 기존과 동일하게
  `X-Mock-Persona-Id` 헤더로 계속 동작한다.
- `Persona.summary_traits`, `watch_status` 등 페르소나 전용 필드는 실사용자에게는
  의미 없는 기본값(`{}`, `no_watch`)으로 채워진다. 실사용자 온보딩 데이터로 이 필드를
  채우는 것은 이번 결정 범위 밖이다.
- 이후 실사용자 전용 데이터 모델이 필요해지면(예: 페르소나 개념 자체를 제거) 이
  암묵적 매핑을 걷어내고 `user_id` 기반으로 재구조화해야 한다.
