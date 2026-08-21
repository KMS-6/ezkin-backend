# EZkin 백엔드–프론트엔드 연동 계약 및 점검 현황

프론트가 사용하는 인증 방식과 API, 배포 후 확인해야 할 성공 조건을 정리한 문서다.
백엔드 구현 자체를 프론트에서 수정하지 않으며, API 계약과 실제 응답을 기준으로 연동한다.

> 정리일: 2026-08-21
> 백엔드 `main`: `25e56c2`
> 프론트 `main`: `fe84090`
> 배포 서버: `https://ezkin-api.onrender.com`
> 이 문서는 특정 시점의 스냅샷이다. `main`이 이후 갱신되면 아래 실측 결과와 커밋 SHA를 다시 확인한다.

## 1. 요청 인증·식별 계약

### 일반 사용자

- `POST /api/v1/users` 응답으로 사용자와 access token을 발급한다.
- 이후 요청은 `Authorization: ****** 사용한다.
- 프론트의 일반 사용자를 `persona_001`로 치환하지 않는다.
- 정식 로그인/회원 인증은 MVP 범위가 아니지만, 발급 토큰으로 사용자 데이터를 분리한다.

### Demo 사용자

- 토큰이 없고 지원되는 Demo ID인 경우 `X-Mock-Persona-Id`를 사용한다.
- 장기 Demo C `persona_long_term_yeonseo`는 `persona_003`으로 매핑된다.
- access token이 있으면 프론트는 페르소나 헤더를 함께 보내지 않는다.

인증/페르소나 매핑의 배경과 트레이드오프는 `docs/decisions/001-signed-user-token.md`,
`docs/decisions/004-map-real-users-to-personas.md`, 전체 구조는 `docs/architecture.md`를 참고한다.

## 2. 프론트가 사용하는 주요 API

| 영역 | Method | Endpoint |
|---|---|---|
| 상태 | `GET` | `/health` |
| 사용자 | `POST` | `/api/v1/users` |
| 온보딩 | 계약된 CRUD | `/api/v1/onboarding...` |
| 화장대 | 계약된 CRUD | `/api/v1/shelf...` |
| 수동 입력 | `PUT` | `/api/v1/daily-manual-metrics/{date}` |
| 브리핑 | `GET` | `/api/v1/briefings/today` |
| 피부 스캔 | `POST/GET` | `/api/v1/skin-scans`, `/api/v1/skin-scans/{scan_id}` |
| 분석 자격 | `GET` | `/api/v1/analysis/eligibility` |
| 리포트 | `POST/GET` | `/api/v1/reports`, `/api/v1/reports/{report_id}` |
| 트리거 분석 | `GET` | `/api/v1/pattern-analysis?scan_id=...` |
| SOS | `POST` | `/api/v1/sos/sessions`, `/api/v1/sos/sessions/{id}/messages` |
| 알림 설정 | 계약된 GET/PUT | `/api/v1/notifications/settings` |

정확한 body와 response schema는 배포 서버의 `/openapi.json`을 기준으로 확인한다.

## 3. 성공으로 판단하는 기준

### 피부 스캔

1. 이미지 업로드 요청이 성공한다.
2. 생성된 `scan_id` 상세 조회가 가능하다.
3. 상태가 `processing → completed`로 전환된다.
4. 결과에 실제 점수와 사용 모델 정보가 포함된다.

접수·DB 저장만 성공하고 `model_not_implemented`로 끝나면 AI 연동 완료가 아니다.

### 브리핑

- `/briefings/today`가 Ready 또는 명세된 Pending 상태를 반환한다.
- AI 피드백 기능을 연결하려면 응답에서 프론트가 사용할 `generation_id`를 제공해야 한다.

### 14일·30일 리포트

1. `/analysis/eligibility`가 실제 누적 일수를 반환한다.
2. `POST /reports`가 `report_id`를 반환한다.
3. `/reports/{report_id}`가 처리 중을 거쳐 완료 결과를 반환한다.
4. 14일과 30일을 각각 테스트한다.

### 일반 사용자 데이터

- 발급 토큰으로 온보딩, 화장대, 수동 지표, 스캔과 분석 데이터가 같은 사용자에게 저장된다.
- 다른 토큰의 데이터가 섞이지 않는다.
- migration을 새 DB에 `upgrade head`로 적용해도 동일하게 동작해야 한다.

## 4. 이전 실측 장애와 재검증 항목

2026-08-21 이전 배포 실측 (당시 커밋 기준, 이후 갱신 여부는 재확인 필요):

| 요청 | 관측 결과 |
|---|---|
| `GET /analysis/eligibility` | `200`, 14/14, eligible |
| `GET /pattern-analysis` | `200` |
| `POST /reports` 14일·30일 | `500` |
| 실제 피부 스캔 | 접수 후 `failed` |
| 스캔 실패 코드 | `model_not_implemented` |

백엔드 재배포 후에는 위 값을 현재 사실로 단정하지 말고 다시 호출해 갱신한다.

## 5. 백엔드 배포 점검

1. `alembic upgrade head` 성공 및 모델–DB 스키마 일치 확인
2. `AAC_OPENAI_API_KEY` 등 필요한 AI 키 설정 확인 (`docs/decisions/003-switch-llm-provider-to-openai.md`)
3. Vision/SOS/Report가 사용하는 모델 ID와 권한 확인
4. `AAC_CORS_ORIGINS`에 Vercel Production 도메인 허용 확인
5. `/health`, `/docs`, `/openapi.json` 확인
6. 실제 사용자 토큰과 Demo persona를 각각 테스트
7. Render 로그에서 5xx의 예외 유형 확인

## 6. 프론트에 공유할 내용

- 배포 commit SHA와 migration revision
- 변경된 endpoint 및 request/response 예시
- 사용자 토큰/페르소나별 실측 HTTP 상태
- 스캔, 브리핑, 14일·30일 리포트의 최종 상태
- 실패 시 예외 유형과 재현 조건

프론트 담당자는 공유받은 결과를 배포 앱에서 다시 확인하고, 오류를 Mock 성공으로 숨기지
않는다.
