# AI 피부케어 앱 API 명세서

카메라 스캔·웨어러블·날씨 데이터를 교차 분석해 개인화 스킨케어를 안내하는 서비스의 백엔드 API입니다. 모든 엔드포인트는 `/api/v1`을 기본 경로로 사용합니다. 해커톤 MVP의 demo/test profile은 로그인 없이 `X-Mock-Persona-Id`로 합성 페르소나를 선택하고, production profile은 `Authorization: Bearer <token>`의 인증 주체를 사용합니다.

- base url: https://api.skincare-app.com/api/v1
- format: application/json
- MVP 소유자 컨텍스트: `X-Mock-Persona-Id`
- production 인증: JWT Bearer
- 문서 버전: v0.4

## 공통 계약

### 날짜와 시간

- 서비스 날짜 기준: `Asia/Seoul`
- 날짜 형식: `YYYY-MM-DD`
- 시각 저장·전송 형식: ISO 8601 UTC
- `today`는 요청 시점의 `Asia/Seoul` 날짜를 의미합니다.
- 잘못된 날짜 형식이나 허용 범위 밖 날짜에는 `422 invalid_date`를 반환합니다.

### 인증과 토큰

문서의 `인증 필요` 표기는 profile에 따라 다음과 같이 해석합니다.

- demo/test: 허용 목록에 존재하는 `X-Mock-Persona-Id` 필수. 누락·미등록 값은 `400 mock_persona_required`.
- production: `Authorization: Bearer <token>` 필수. `X-Mock-Persona-Id`는 거부.
- body·query의 `persona_id` 또는 `user_id`는 소유권 근거로 신뢰하지 않습니다.

MVP에서는 회원가입·로그인·토큰 발급 API와 실제 사용자 테이블을 배포하지 않습니다. 아래 토큰 정책과 `/auth/**`는 production 전환용 계약입니다.

- Access token 만료 시간: 1시간
- Refresh token 만료 시간: 30일
- JWT는 서버가 허용한 서명 알고리즘과 `iss`, `aud`, `sub`, `exp`, `nbf`, `iat` 클레임을 검증합니다.
- Refresh token은 서버 저장소에서 폐기 상태를 확인합니다. 회전과 재사용 탐지는 운영 단계에서 적용합니다.

### 리소스 소유권

요청 주체는 자신이 소유한 리소스만 조회·수정·삭제할 수 있습니다. 서버는 demo/test의 검증된 `persona_id` 또는 production 인증 주체의 `user_id`로 소유자 컨텍스트를 만들고 모든 리소스 접근과 관계 생성에 적용합니다. 다른 소유자의 `scan_id`, `cosmetic_id`, `session_id`, `report_id`는 존재 여부를 노출하지 않도록 `404 Not Found`를 반환합니다. 관리자 접근은 별도 관리자 정책을 따릅니다.

### 관리자 권한

- 역할은 `user`, `admin`으로 구분하며 관리자 API는 기본 거부(deny-by-default) 정책을 적용합니다.
- `/admin/**` API는 `admin` 역할만 호출할 수 있으며 일반 사용자에게 `403 Forbidden`을 반환합니다.
- 관리자 쓰기 작업은 작업자, 대상 리소스, 시각, 결과를 감사 로그에 기록합니다.
- 세부 scope, 관리자 재인증과 감사 로그 무결성 강화는 운영 단계에서 적용합니다.

### 공통 오류 응답

모든 오류는 다음 envelope를 사용합니다. `details`는 필드 validation 오류가 있을 때만 포함할 수 있습니다.

```json
{
  "error": {
    "code": "validation_error",
    "message": "요청 값이 올바르지 않습니다.",
    "details": [],
    "request_id": "req_123"
  }
}
```

| 상태 코드 | 사용 기준 |
| --- | --- |
| `400 Bad Request` | JSON 파싱 실패, 잘못된 `Content-Type` 등 요청 형식 오류 |
| `401 Unauthorized` | 인증 실패 또는 토큰 만료 |
| `403 Forbidden` | 인증됐지만 역할 또는 권한 부족 |
| `404 Not Found` | 리소스가 없거나 현재 사용자가 접근할 수 없음 |
| `409 Conflict` | 중복, 멱등성 키 재사용 또는 현재 리소스 상태와 충돌 |
| `422 Unprocessable Content` | 스키마 또는 도메인 validation 실패 |
| `429 Too Many Requests` | 요청 횟수 제한 초과. `Retry-After` 헤더 포함 |

### 멱등성

`POST /skin-scans`, `POST /integrations/health-data`와 관리자 생성 API는 `Idempotency-Key` 헤더를 사용합니다. 키는 인증 주체와 엔드포인트 범위에서 24시간 유효합니다. 같은 키와 같은 payload의 재요청은 최초 응답을 반환하고, 같은 키에 다른 payload를 보내면 `409 idempotency_key_reused`를 반환합니다. `POST /daily-metrics/manual`은 사용자와 `metric_date`를 고유 키로 upsert합니다.

### GET · `/personas` · demo/test 전용

선택 가능한 합성 Mock 페르소나 목록과 개인화에 영향을 주는 요약 특성을 반환합니다. production profile에서는 이 라우트를 등록하지 않습니다.

### GET · `/personas/{persona_id}` · demo/test 전용

지정한 Mock 페르소나의 표시 정보와 기능별 데이터 가용성을 반환합니다. 허용 목록에 없는 ID는 `404 Not Found`입니다.

### Mock Persona 데이터 생성 규칙 · demo/test 전용

Mock Persona는 별도 분석 응답 타입을 만들지 않으며, 각 Persona의 실제 목데이터를 동일한 API 스키마에 넣어 demo/test 응답으로 사용합니다. 데이터가 없는 항목은 임의 값을 생성하지 않습니다.

- 워치 데이터가 없는 Persona는 `sleep_hours`, `hrv_ms` 등 Health 값을 임의 생성하지 않습니다.
- baseline이 없는 Persona는 `delta_vs_baseline` 개인 평균 비교값을 임의 생성하지 않고 `null`로 반환합니다.
- `active_energy_kcal` 값이 없는 Persona는 활동량 값을 임의 생성하지 않습니다.
- 수분은 `water_intake_level`, 식단은 `diet_flag` 값을 그대로 사용합니다.

## 공통 · 인증(production 전환용, MVP 비활성)

회원가입, 로그인 등 세션 발급과 관련된 production 전환용 엔드포인트입니다. 해커톤 MVP에서는 라우트를 등록하지 않습니다.

### POST · `/auth/signup` · 인증 불필요

이메일 또는 소셜 계정으로 신규 회원을 등록합니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| auth_type **required** | enum | `email`, `social` |
| email | string | `auth_type=email`일 때 필수 |
| password | string | `auth_type=email`일 때 필수, 최소 8자 |
| nickname | string | 표시 닉네임, 미입력 시 기본값 부여 |
| social_provider | enum | `auth_type=social`일 때 필수, `apple`, `kakao` |
| social_token | string | `auth_type=social`일 때 필수 |

`auth_type`과 다른 인증 방식의 필드는 함께 전송할 수 없습니다. 소셜 토큰은 제공자의 공개키 또는 검증 API를 통해 서명, issuer, audience, nonce와 만료를 검증합니다.

```json
{ "auth_type": "email", "email": "user@example.com", "password": "password", "nickname": "사용자" }
```

```json
{ "auth_type": "social", "social_provider": "kakao", "social_token": "provider-token", "nickname": "사용자" }
```

#### Response 201

```json
{
  "user_id": "usr_8f2c...",
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "onboarding_completed": false
}
```

**상태 코드:** `201 Created`, `409 email_already_exists`, `422 validation_error`

### POST · `/auth/login` · 인증 불필요

이메일/비밀번호 또는 소셜 토큰으로 로그인해 액세스 토큰을 발급받습니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| auth_type **required** | enum | `email`, `social` |
| email | string | `auth_type=email`일 때 필수 |
| password | string | `auth_type=email`일 때 필수 |
| social_provider | enum | `auth_type=social`일 때 필수, `apple`, `kakao` |
| social_token | string | `auth_type=social`일 때 필수 |

회원가입과 같은 조건부 필수 및 상호 배타 규칙을 적용합니다. 계정 존재 여부와 관계없이 인증 실패 응답은 동일한 `401 invalid_credentials`를 사용합니다.

#### Response 200

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "expires_in": 3600
}
```

**상태 코드:** `200 OK`, `401 invalid_credentials`

회원가입과 로그인에는 IP 및 정규화된 계정 식별자 기준의 단기 요청 제한을 적용합니다. 제한 초과 시 공통 오류 envelope의 `429 rate_limit_exceeded`와 `Retry-After` 헤더를 반환합니다.

### POST · `/auth/refresh` · 인증 불필요

유효하고 폐기되지 않은 Refresh token으로 Access token을 갱신합니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| refresh_token **required** | string | 발급받은 Refresh token |

#### Response 200

```json
{ "access_token": "eyJhbGciOi...", "expires_in": 3600 }
```

### POST · `/auth/logout` · 인증 필요

전달된 Refresh token을 폐기합니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| refresh_token **required** | string | 폐기할 Refresh token |

**상태 코드:** `204 No Content`

## 기능 1 · 온보딩 및 데이터 연동

피부 고민·보유 화장품 등록과 Apple Health·날씨 데이터 수집 동의를 처리합니다. 동의하지 않은 항목은 어떤 분석 API에서도 조회·사용되지 않습니다.

### GET · `/onboarding/skin-concerns` · 인증 불필요

온보딩 화면에 노출할 피부 고민 마스터 목록을 반환합니다.

#### Response 200

```json
{
  "concerns": [
    { "id": "cn_acne", "label": "트러블·여드름" },
    { "id": "cn_oily_tzone", "label": "T존 유분" },
    { "id": "cn_dryness", "label": "건조·당김" },
    { "id": "cn_hormonal", "label": "생리 전 트러블" }
  ]
}
```

### POST · `/onboarding/profile` · 인증 필요

피부 고민, 보유 화장품, 선택적 바이오 정보를 등록합니다. 각 필드는 건너뛸 수 있습니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| skin_concern_ids | string[] | 선택한 피부 고민 id 목록 (0개 이상) |
| birth_year | int | 선택 입력, 나이대 기반 안내에 사용 |
| menstrual_cycle_tracking | boolean | 생리 주기 반영 여부 (선택) |

#### Response 200

```json
{ "onboarding_completed": true }
```

> **참고:** 진단·치료 목적의 문진 항목은 포함하지 않으며, 전 필드가 선택 사항입니다.

### GET · `/consents` · 인증 필요

사용자의 항목별 데이터 수집 동의 상태를 조회합니다.

#### Response 200

```json
{
  "consents": [
    { "type": "apple_health", "consented": true,  "updated_at": "2026-08-01T09:00:00Z" },
    { "type": "weather_location", "consented": false, "updated_at": null }
  ]
}
```

### PUT · `/consents/{consent_type}` · 인증 필요

특정 항목(`apple_health` · `weather_location`)의 동의 여부를 변경합니다. 동의 철회 즉시 신규 수집을 중단하고 해당 데이터와 진행 중 분석 결과를 이후 분석 대상에서 제외합니다. 원본·파생 결과·캐시·로그·백업의 삭제 또는 격리 기한은 개인정보 처리방침과 법적 검토 후 확정합니다. 재동의 전에는 기존 데이터를 자동으로 재사용하지 않습니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| consented **required** | boolean | true/false |

#### Response 200

```json
{ "type": "apple_health", "consented": true, "updated_at": "2026-08-12T10:00:00Z" }
```

### GET · `/me/feature-availability` · 인증 필요

현재 동의 상태를 기준으로 각 기능이 정상 제공되는지, 제한되어 대체 경로로 안내되는지를 반환합니다. 동의 거부가 기능 자체를 막지는 않되, 대체 경로 이용 시 분석 정확도가 낮아질 수 있음을 함께 전달합니다.

#### Response 200

```json
{
  "features": [
    {
      "feature": "risk_assessment_health",
      "status": "limited",
      "reason": "apple_health 동의 없음",
      "fallback": "간편 문진 기반 위험도 산출로 대체됩니다."
    },
    {
      "feature": "risk_assessment_weather",
      "status": "normal"
    }
  ]
}
```

## 기능 2 · 피부 상태 관찰 및 위험도 분석

카메라 스캔과 자동 수집 데이터를 교차 분석해 4단계 위험도를 산출합니다. 모든 응답에는 의료적 진단이 아닌 상대적 변화 관찰이라는 한계 안내 문구가 포함됩니다.

### 이미지 업로드 계약

해커톤 MVP는 애플리케이션 서버가 한 요청에서 인증, 검증과 저장을 처리하는 `multipart/form-data` 업로드를 사용합니다.

- 허용 MIME 타입: `image/jpeg`, `image/png`, `image/heic`
- 최대 파일 크기: 10 MiB
- 서버는 선언된 MIME 타입뿐 아니라 실제 이미지 디코딩 결과와 크기를 검증합니다.
- 이미지 필드는 검증된 소유자 요청의 목적(`skin_scan`, `cosmetic`)에만 사용합니다. 피부 스캔 원본은 `delete_after_analysis`가 기본이며, 화장품 이미지는 비공개 저장소에 둡니다.
- 잘못된 형식은 `422 invalid_image_type`, 크기 초과는 `422 image_too_large`를 반환합니다.
- 운영 단계에서 대용량 직접 업로드가 필요해지면 presigned URL, 일회성 키 소비, EXIF 제거와 미완료 객체 정리를 도입합니다.

### POST · `/skin-scans` · 인증 필요

피부 스캔 이미지를 업로드하고 홍조·건조·유분의 상대적 변화 분석을 요청합니다. `Content-Type`은 `multipart/form-data`입니다. 촬영 조건 미충족으로 이미지 스캔이 어려운 경우 `capture_method=questionnaire`로 간편 문진을 제출할 수 있습니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| capture_method | enum | camera(기본값), questionnaire |
| image | binary | camera 방식일 때 필수. 허용 형식과 크기는 이미지 업로드 계약 참조 |
| questionnaire_version | string | questionnaire 방식일 때 필수. 예: `v1` |
| answers | JSON string | questionnaire 방식일 때 필수. 아래 답변 배열을 JSON 문자열로 전송 |
| captured_at **required** | datetime | 촬영/응답 시각(ISO 8601) |
| lighting_ok | boolean | 촬영 조건 자가 체크 결과(camera 방식) |

`camera` 방식에서는 `image`가 필수이며 `questionnaire_version`, `answers`를 보낼 수 없습니다. `questionnaire` 방식에서는 `questionnaire_version`, `answers`가 필수이며 `image`, `lighting_ok`를 보낼 수 없습니다.

#### Questionnaire answers

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| question_id **required** | enum | `redness`, `tightness`, `oiliness`, `new_lesions` |
| value **required** | enum | `none`, `mild`, `moderate`, `severe` |

`v1`은 `redness`, `tightness`, `oiliness` 세 문항이 필수이며 `new_lesions`는 선택입니다. 동일한 `question_id`를 중복 제출할 수 없습니다.

#### Response 202

```json
{
  "scan_id": "scn_a91f...",
  "status": "processing",
  "capture_method": "camera",
  "status_url": "/api/v1/skin-scans/scn_a91f..."
}
```

응답에는 `Location: /api/v1/skin-scans/scn_a91f...`와 `Retry-After: 3` 헤더가 포함됩니다. 클라이언트는 3초 이상 간격으로 최대 2분 동안 조회합니다. 2분이 지나도 완료되지 않은 작업은 `failed`와 `analysis_timeout`으로 전환됩니다. 실패 후에는 새 `Idempotency-Key`로 다시 요청합니다.

#### Response 422 (촬영 실패 시)

```json
{
  "error": {
    "code": "low_image_quality",
    "message": "이미지 품질이 분석 기준을 충족하지 않습니다.",
    "details": {
      "fallback_available": true,
      "fallback_endpoint": "POST /api/v1/skin-scans (capture_method=questionnaire)"
    },
    "request_id": "req_123"
  }
}
```

**상태 코드:** `202 Accepted`, `422 low_image_quality`

> **참고:** questionnaire 방식으로 생성된 스캔 결과는 `GET /skin-scans/{scan_id}` 응답에 `lower_accuracy: true`가 함께 표시되어 카메라 스캔과 구분됩니다.

### GET · `/skin-scans/{scan_id}` · 인증 필요

스캔 분석 상태와 완료된 경우 이전 기록 대비 상대적 변화를 조회합니다. 상태 enum은 `processing`, `completed`, `failed`입니다.

#### Response 200 · processing

```json
{
  "scan_id": "scn_a91f...",
  "status": "processing",
  "created_at": "2026-08-12T10:00:00Z",
  "retry_after_seconds": 3
}
```

#### Response 200 · completed

```json
{
  "scan_id": "scn_a91f...",
  "status": "completed",
  "capture_method": "questionnaire",
  "lower_accuracy": true,
  "schema_version": "skin_observation.v1",
  "scores": { "redness": 0.42, "dryness": 0.18, "oiliness": 0.63 },
  "confidence": { "redness": 0.84, "dryness": 0.76, "oiliness": 0.88 },
  "delta_vs_baseline": { "redness": 0.08, "dryness": -0.02, "oiliness": 0.11 },
  "delta_vs_previous": { "redness": 0.05, "dryness": -0.01, "oiliness": 0.07 },
  "model": { "provider": "TBD", "name": "TBD", "version": "TBD" },
  "limitation_notice": "조명·기기 차이에 따라 오차가 있을 수 있는 개인 기준 상대 지표입니다."
}
```

#### Response 200 · failed

```json
{
  "scan_id": "scn_a91f...",
  "status": "failed",
  "failure": {
    "code": "analysis_failed",
    "message": "분석을 완료하지 못했습니다.",
    "retryable": true
  }
}
```

작업 접수 전 형식·크기 오류는 `4xx` 공통 오류로 반환하고, 동기 품질 검사는 `422 low_image_quality`, 비동기 모델·큐 실패는 `status=failed`로 구분합니다.

`delta_vs_baseline`은 최근 유효 스캔 중앙값과의 차이이고 기준선이 부족하면 `null`입니다. `delta_vs_previous`는 직전 완료 스캔과의 차이이며 직전 스캔이 없으면 `null`입니다. 두 값은 서로 대체하지 않습니다.

### GET · `/skin-scans` · 인증 필요

사용자의 스캔 이력을 최신순으로 조회합니다.

#### Query parameters

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| from | date | 조회 시작일 |
| to | date | 조회 종료일 |
| cursor | string | 이전 응답의 `next_cursor` (선택) |
| limit | int | 기본값 20, 최대 100 |

정렬은 `captured_at DESC, scan_id DESC`로 고정합니다.

#### Response 200

```json
{
  "items": [
    { "scan_id": "scn_a91f...", "status": "completed", "captured_at": "2026-08-12T10:00:00Z" }
  ],
  "next_cursor": "cursor_123",
  "has_more": true
}
```

### POST · `/integrations/health-data` · API 키(서버간)

Health Auto Export 등 외부 연동 앱이 수면·HRV·활동 데이터를 전송하는 webhook입니다. `apple_health` 동의가 없는 사용자의 데이터는 저장되지 않고 즉시 폐기됩니다.

#### Request headers

| 헤더 | 설명 |
| --- | --- |
| `X-Partner-Key` **required** | 파트너를 식별하는 API 키. 파트너별 `health_data:write` scope 필요 |
| `Idempotency-Key` **required** | 파트너와 엔드포인트 범위의 중복 방지 키 |

MVP는 TLS와 파트너별 API 키를 사용합니다. 동일 멱등성 키의 같은 payload는 최초 결과를 반환하며 한 건만 저장합니다. 키는 만료일을 두고 회전하며 폐기된 키는 즉시 거부합니다. HMAC-SHA256, timestamp, nonce와 mTLS는 외부 도구 지원 여부를 확인한 뒤 운영 단계에서 적용합니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| user_token **required** | string | 사용자 연동용 고유 토큰 |
| metric_date **required** | date | 측정 기준일 |
| sleep_hours | float | 수면 시간 |
| hrv_ms | float | HRV(ms) |
| active_energy_kcal | float | 활동 에너지 |

#### Response 200

```json
{ "received": true }
```

### POST · `/daily-metrics/manual` · 인증 필요

저녁 알림에서 수분·식단 상태를 탭 한 번으로 보완 입력합니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| metric_date **required** | date | 대상 날짜 |
| water_intake_level | enum | `under_3_glasses`, `three_to_five_glasses`, `over_5_glasses` |
| diet_flag | enum | `normal`, `spicy`, `late_night_meal` |

`water_intake_level`은 날짜별 최소 입력값이며 Mock Persona의 `daily_metrics.water_intake_level`과 동일한 enum을 사용합니다.

같은 사용자와 `metric_date`의 요청은 새 행을 만들지 않고 기존 값을 갱신합니다.

#### Response 200

```json
{
  "metric_date": "2026-08-12",
  "water_intake_level": "three_to_five_glasses",
  "diet_flag": "late_night_meal",
  "updated_at": "2026-08-12T12:30:00Z"
}
```

### GET · `/risk-assessments/today` · 인증 필요

최신 스캔·수면·HRV·날씨·UV와 선택 입력을 교차 분석한 당일 피부 위험도를 반환합니다.

`today`는 요청 시점의 `Asia/Seoul` 날짜입니다.

#### Response 200

```json
{
  "date": "2026-08-12",
  "risk_level": "high",
  "risk_levels_enum": ["low", "moderate", "high", "very_high"],
  "contributing_factors": ["수면 5시간 미만", "자외선지수 8 (매우 높음)"],
  "limitation_notice": "의료적 진단이 아닌 웰니스 목적의 상대적 변화 안내입니다."
}
```

### GET · `/analysis/eligibility` · 인증 필요

14/30일 기간 Report 생성에 필요한 유효 관찰 일수를 확인합니다.

```json
{
  "available_days": 11,
  "required_days": 14,
  "eligible": false,
  "missing_inputs": ["skin_observation"]
}
```

### POST · `/reports` · 인증 필요

14일 또는 30일의 기간 Report 생성을 비동기로 요청합니다.

```json
{
  "period_days": 14,
  "end_date": "2026-08-15",
  "locale": "ko-KR"
}
```

`period_days`는 `14`, `30`만 허용합니다. 유효 관찰 데이터가 서로 다른 14일에 미달하면 `409 insufficient_data_history`를 반환합니다.

#### Response 202

```json
{
  "report_id": "rpt_73ab",
  "status": "processing",
  "status_url": "/api/v1/reports/rpt_73ab"
}
```

### GET · `/reports/{report_id}` · 인증 필요

기간 Report의 처리 상태와 완료 결과를 조회합니다. 상태는 `processing`, `completed`, `failed`입니다.

#### Response 200 · completed

```json
{
  "report_id": "rpt_73ab",
  "status": "completed",
  "period": {
    "period_days": 14,
    "start_date": "2026-08-02",
    "end_date": "2026-08-15"
  },
  "summary": "최근 수면·HRV 저하와 홍조 상승이 함께 관찰됐어요.",
  "observations": [
    {
      "text": "수면 4시간과 HRV 33ms가 기록됐어요.",
      "evidence_ids": ["daily_metric:2026-08-14"]
    }
  ],
  "patterns": [
    {
      "text": "건조한 날씨가 겹친 날 홍조 상승이 함께 관찰되는 경향이 있었어요.",
      "evidence_ids": ["skin_scan:scn_c1_20"]
    }
  ],
  "recommendations": [
    {
      "text": "다음 기간에도 수면·HRV와 홍조 변화를 함께 확인해 보세요.",
      "evidence_ids": ["skin_scan:scn_c1_20"]
    }
  ],
  "limitations": "생활·생체·환경 데이터와 피부 변화가 함께 관찰된 패턴이며 인과관계를 의미하지 않습니다.",
  "safety_status": "wellness_only",
  "generated_at": "2026-08-16T00:30:00Z"
}
```

`summary`는 문자열이며, `observations`, `patterns`, `recommendations`는 각각 `text`와 `evidence_ids`를 가진 항목 배열입니다. 프론트 전용 `skin_summary`, `timeline` 등은 Report API 필수 응답 필드로 두지 않습니다.

**상태 코드:** `200 OK`, `404 Not Found`, `409 insufficient_data_history`, `422 invalid_report_period`

## 기능 3 · 개인화 스킨케어 처방

피부 위험도와 보유 화장품을 바탕으로 아침 브리핑과 레이어링 순서를 안내합니다. 새 제품 구매를 전제로 하지 않습니다.

### GET · `/briefings/today` · 인증 필요

잠금 화면 알림과 앱 첫 화면에 노출되는 당일 브리핑 요약을 조회합니다.

`today`는 요청 시점의 `Asia/Seoul` 날짜입니다.

#### Response 200

```json
{
  "status": "ready",
  "date": "2026-08-12",
  "risk_level": "high",
  "headline": "오늘은 피부 자극에 주의해 주세요.",
  "summary": "짧은 수면과 야식, 낮은 습도가 함께 관찰됐어요.",
  "contributing_factors": [
    { "type": "sleep", "text": "수면 4.5시간" },
    { "type": "weather", "text": "습도 20%" }
  ],
  "routine": [
    { "order": 1, "action": "use", "cosmetic_id": "csm_101", "name": "진정 토너", "note": "얇게 사용해 주세요." }
  ],
  "skip": [
    { "cosmetic_id": "csm_402", "name": "비타민C 앰플", "reason": "오늘은 자극 가능성을 줄이기 위해 쉬어 보세요." }
  ],
  "common_knowledge": {
    "claim_id": "claim_humidity_dryness_001",
    "version": 1,
    "sentence": "낮은 습도는 각질층 수분과 피부 건조 지표에 영향을 줄 수 있어요."
  },
  "data_coverage": {
    "weather": true,
    "watch": true,
    "skin_scan": true,
    "my_shelf": true,
    "baseline_established": true
  },
  "limitation_notice": "의료적 진단이 아닌 웰니스 목적의 상대적 변화 안내입니다.",
  "generated_at": "2026-08-12T06:30:00+09:00",
  "sent_at": "2026-08-12T07:00:00Z"
}
```

한 Briefing의 `common_knowledge`는 최대 1개입니다. `review_status=approved`, 기능·topic·population·`required_user_facts`가 모두 일치하고 `claim_id`+`version` 인용 검증을 통과할 때만 포함합니다. 조건을 만족하지 못하면 `null`로 두고 나머지 응답은 정상 반환합니다.

권장 생성 시각(06:30) 이전에는 다음처럼 `pending`을 반환합니다.

```json
{
  "status": "pending",
  "date": "2026-08-12",
  "generation_expected_at": "2026-08-12T06:30:00+09:00",
  "previous_briefing": {
    "date": "2026-08-11",
    "risk_level": "high",
    "headline": "오늘은 피부 자극에 주의해 주세요."
  }
}
```

발송된 Briefing은 이후 입력 갱신으로 변경하지 않으며 재생성은 발송 전에만 허용합니다. 생성 파이프라인은 최대 2회 재시도하고, 최종 실패 시 기능 명세의 최소 템플릿을 반환합니다. 푸시 실패는 Briefing 조회 실패와 분리합니다.

### GET · `/prescriptions/{date}` · 인증 필요

등록된 화장품 기준 사용 순서와 피해야 할 자극 요소를 조회합니다.

`date`는 `Asia/Seoul` 기준 `YYYY-MM-DD`이며 미래 날짜는 허용하지 않습니다.

#### Response 200

```json
{
  "date": "2026-08-12",
  "steps": [
    { "order": 1, "cosmetic_id": "csm_101", "name": "약산성 클렌저", "note": null },
    { "order": 2, "cosmetic_id": "csm_204", "name": "저자극 토너", "note": "알코올 성분 제품과 중복 사용 자제" }
  ],
  "avoid": ["고농도 각질 제거 성분", "새 향료 함유 제품"],
  "disclaimer": "일반적 관리 안내이며 치료·처방 목적이 아닙니다."
}
```

### PATCH · `/notifications/settings` · 인증 필요

아침 브리핑 알림 수신 여부를 변경합니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| morning_briefing_enabled **required** | boolean | 알림 on/off |

#### Response 200

```json
{
  "morning_briefing_enabled": true,
  "updated_at": "2026-08-12T10:00:00Z"
}
```

## 기능 4 · 보유 화장품 관리

사진 촬영 또는 직접 입력으로 보유 화장품을 등록·관리합니다. 초기 범위는 기초화장품 중심입니다.

### POST · `/cosmetics` · 인증 필요

화장품을 등록합니다. `Content-Type`은 `multipart/form-data`이며, `image` 전달 시 브랜드·성분을 자동 인식해 초안을 채웁니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| image | binary | 제품 사진(선택). 허용 형식과 크기는 이미지 업로드 계약 참조 |
| brand **required** | string | 브랜드명 |
| product_name **required** | string | 제품명 |
| product_type | enum | cleanser, toner, serum, moisturizer, sunscreen 등 |
| ingredients_raw | string[] | 확인 가능한 범위의 성분 원문 목록 |

#### Response 201

```json
{
  "cosmetic_id": "csm_204",
  "matched_ingredients": ["ing_niacinamide", "ing_salicylic_acid"],
  "risk_alerts": [
    { "ingredient": "살리실산", "risk_level": "caution", "target_concern": "청소년·여드름성 피부" }
  ]
}
```

> **참고:** 성분 사전(`/ingredients`)에 등록된 명칭과 매칭되면 `risk_alerts`가 함께 반환됩니다. 의약품 수준의 효능·부작용 단정 표현은 사용하지 않고 "주의가 필요한 성분" 수준으로 안내합니다.

### GET · `/cosmetics` · 인증 필요

등록된 화장품 목록을 조회합니다.

#### Response 200

```json
{
  "items": [
    {
      "cosmetic_id": "csm_204",
      "brand": "브랜드명",
      "product_name": "저자극 토너",
      "product_type": "toner",
      "ingredients_raw": ["나이아신아마이드"]
    }
  ]
}
```

등록 제품이 없으면 `items`는 빈 배열입니다.

### PATCH · `/cosmetics/{cosmetic_id}` · 인증 필요

등록된 화장품 정보 일부를 수정합니다. `Content-Type`은 `application/json`입니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| brand | string | 생략 시 기존 값 유지, `null` 불가 |
| product_name | string | 생략 시 기존 값 유지, `null` 불가 |
| product_type | enum \| null | 생략 시 기존 값 유지, `null`이면 값 제거 |
| ingredients_raw | string[] \| null | 생략 시 기존 값 유지, `null`이면 값 제거 |

`brand`, `product_name`에 `null`을 보내면 `422 validation_error`를 반환합니다. 이미지 변경은 기존 항목 수정과 분리해 화장품을 다시 등록합니다.

#### Response 200

```json
{
  "cosmetic_id": "csm_204",
  "brand": "브랜드명",
  "product_name": "저자극 토너",
  "product_type": "toner",
  "ingredients_raw": ["나이아신아마이드"],
  "updated_at": "2026-08-12T10:00:00Z"
}
```

### DELETE · `/cosmetics/{cosmetic_id}` · 인증 필요

화장품을 목록에서 삭제합니다. 과거 처방 기록의 참조는 유지됩니다.

**상태 코드:** `204 No Content`

### GET · `/ingredients` · 인증 필요

성분 사전을 조회합니다. 화장품 등록 시 성분 매칭과 위험도 표시에 사용됩니다.

#### Query parameters

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| risk_level | enum | safe, caution 필터링 (선택) |
| target_concern | string | 예: 청소년, 여드름성 피부 (선택) |

#### Response 200

```json
{
  "ingredients": [
    {
      "id": "ing_salicylic_acid",
      "name": "살리실산",
      "risk_level": "caution",
      "target_concern": "청소년·여드름성 피부",
      "description": "각질 개선에 쓰이나 민감 피부·저연령대는 자극이 있을 수 있어 사용량 주의가 필요합니다."
    }
  ]
}
```

### POST · `/admin/ingredients` · 관리자 인증

운영 관리자가 성분 사전에 항목을 등록합니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| name **required** | string | 성분명 |
| risk_level **required** | enum | safe, caution |
| target_concern | string | 주요 주의 대상 (예: 청소년·여드름성 피부) |
| description | string | 주의 안내 문구. 의약품 수준의 효능·부작용 단정 표현 금지 |

중복 판별 키는 정규화한 `name`입니다. 이미 존재하면 `409 ingredient_already_exists`를 반환합니다.

#### Response 201

```json
{
  "id": "ing_salicylic_acid",
  "name": "살리실산",
  "risk_level": "caution",
  "target_concern": "청소년·여드름성 피부",
  "description": "민감 피부·저연령대는 사용량 주의가 필요합니다."
}
```

## 기능 5 · 피부 트리거 대응

트러블 상황에서 완료된 피부 스캔 시점을 기준으로 직전 72시간의 생활·생체·환경 데이터를 역방향으로 확인하고 SOS 챗봇 안내를 제공합니다.

### GET · `/pattern-analysis?scan_id={scan_id}` · 인증 필요

완료된 스캔 시점 기준 직전 72시간 동안 실제로 관찰된 요인과 과거 유사 사례의 반복 여부를 반환합니다.

#### Response 200

```json
{
  "scan_id": "scn_c1_20",
  "window": {
    "start": "2026-08-11T08:00:00Z",
    "end": "2026-08-14T08:00:00Z"
  },
  "raw_facts": [
    {
      "type": "sleep",
      "text": "최근 3일 평균 수면 시간이 평소보다 1.8시간 짧았어요."
    },
    {
      "type": "hrv",
      "text": "HRV가 평소보다 크게 낮은 날이 이틀 연속 있었어요."
    },
    {
      "type": "weather",
      "text": "건조한 날씨가 겹친 날 홍조 점수가 함께 상승했어요."
    }
  ],
  "observed_pattern": {
    "text": "비슷한 조건에서 피부 변화가 함께 관찰되는 경향이 있었어요.",
    "sample_size": 3,
    "match_count": 2
  },
  "common_knowledge": null,
  "disclaimer": "통계적 인과관계나 의료 진단이 아닌 예방적 참고용 관찰입니다."
}
```

- `window`는 대상 스캔의 `captured_at` 직전 72시간 범위입니다.
- `raw_facts`는 해당 72시간에 실제 존재하는 데이터만 사용합니다.
- 과거 유사 사례가 충분할 때 `observed_pattern`을 제공하고, 충분하지 않으면 `null`로 반환합니다.
- `common_knowledge`는 현재 RAG 미연동 상태에서는 `null`입니다.
- `target_skin_event`, `timeline`, `next_action`은 Pattern Analysis API 필수 응답 필드로 두지 않습니다.
- 완료되지 않은 스캔은 패턴 분석 대상이 아니며 `409`를 반환합니다.
- 표현은 인과를 단정하지 않고 `함께 관찰됨`, `경향이 있었음` 수준으로 제한합니다.

**상태 코드:** `200 OK`, `400 mock_persona_required`, `404 Not Found`, `409 scan_not_completed`, `422 validation_error`

### POST · `/sos/sessions` · 인증 필요

SOS 챗봇 대화 세션을 시작합니다. 세션은 등록 제품과 당일 위험도를 컨텍스트로 참조합니다.

#### Response 201

```json
{ "session_id": "sos_77c1...", "quick_replies": ["야식을 먹었어요", "트러블이 났어요", "제품이 안 맞는 것 같아요"] }
```

### POST · `/sos/sessions/{session_id}/messages` · 인증 필요

빠른 답변 또는 직접 입력 메시지를 전송하고 안내를 받습니다. 응답은 규칙 기반 안전 필터를 통과한 후 반환됩니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| message **required** | string | 사용자 입력 또는 빠른 답변 텍스트 |

#### Response 200

```json
{
  "message_id": "msg_123",
  "reply_type": "answer",
  "reply": "오늘은 등록된 저자극 보습 제품 위주로 사용해 보세요.",
  "matched_faq": {
    "faq_id": "faq_after_late_night_meal",
    "version": 3,
    "match_score": 0.91
  },
  "decision": {
    "rule_id": "rule_reduce_irritation",
    "code": "REDUCE_IRRITATION"
  },
  "referenced_cosmetic_ids": ["csm_204"],
  "used_contexts": ["my_shelf", "latest_skin_scan"],
  "safety_flag": null,
  "expert_referral_suggested": false
}
```

> **참고:** 고위험 증상 키워드 감지 시 `expert_referral_suggested: true`와 함께 전문가 상담 안내 문구가 포함됩니다. 의료적 단정 표현은 필터에서 차단됩니다.

Chatbot은 런타임 공통 RAG를 호출하지 않습니다. 규칙 기반 파싱이 `parse_confidence < 0.60`일 때만 저비용 LLM으로 slot을 보정할 수 있고, FAQ·Rule 선택과 안전 판정은 결정적 코드가 수행합니다.

## 기능 6 · 맥락 기반 제품 추천 및 운영

보유 제품으로 보완하기 어려운 상황에 한해 맥락 기반 추천을 제공하며, 앱 내 결제·배송·환불은 다루지 않습니다.

### GET · `/recommendations` · 인증 필요

현재 피부 상태·필요 성분과 연결된 제품 추천을 조회합니다.

#### Response 200

```json
{
  "recommendations": [
    {
      "product_id": "prd_552",
      "name": "판테놀 진정 크림",
      "reason": "최근 홍조 지표 상승 및 보유 제품 중 진정 성분 부재",
      "external_url": "https://partner-shop.example.com/prd_552"
    }
  ]
}
```

### POST · `/admin/products` · 관리자 인증

운영 관리자가 추천 대상 품목을 등록합니다.

#### Request body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| name **required** | string | 제품명 |
| brand **required** | string | 브랜드명 |
| category | string | 제품 카테고리 |
| external_url **required** | string | 외부 구매 연결 URL |
| safety_policy_note | string | 노출 조건·주의 안내 메모 |

중복 판별 키는 정규화한 `brand`와 `name`의 조합입니다. 이미 존재하면 `409 product_already_exists`를 반환합니다.

#### Response 201

```json
{
  "product_id": "prd_552",
  "name": "판테놀 진정 크림",
  "brand": "브랜드명",
  "category": "moisturizer",
  "external_url": "https://partner-shop.example.com/prd_552",
  "safety_policy_note": null
}
```

### GET · `/admin/products` · 관리자 인증

등록된 추천 품목과 안전 정책 목록을 조회합니다.

#### Response 200

```json
{
  "items": [
    {
      "product_id": "prd_552",
      "name": "판테놀 진정 크림",
      "brand": "브랜드명",
      "category": "moisturizer",
      "external_url": "https://partner-shop.example.com/prd_552",
      "safety_policy_note": null
    }
  ]
}
```

등록 품목이 없으면 `items`는 빈 배열입니다.

## 공통 지식 RAG 운영

일반 클라이언트는 공통 지식 검색을 직접 호출하지 않습니다. Report와 Briefing 서비스만 검수된 Claim을 내부적으로 조회하며, 다음 API는 관리자 전용입니다.

### POST · `/admin/knowledge/documents` · 관리자 인증

출처 URL, 제목, 게시·수집 시각, 라이선스, 원문 해시와 근거 메타데이터를 가진 문서 후보를 등록합니다. 등록 직후 상태는 `draft`이며 사용자 응답에 사용하지 않습니다.

### POST · `/admin/knowledge/documents/{id}/approve` · 관리자 인증

문서와 파생 Claim Card의 검수를 승인합니다. Claim에는 `claim_id`, `version`, `topic`, `population`, `evidence_level`, `allowed_features`, `required_user_facts`, 허용·금지 표현, 검수자와 다음 검토 시점이 필요합니다.

### GET · `/admin/knowledge/documents/{id}` · 관리자 인증

문서 메타데이터, Claim 버전과 검수 상태를 조회합니다.

### POST · `/admin/knowledge/indexes` · 관리자 인증

승인된 활성 Claim과 문서 청크로 새 인덱스 버전을 생성합니다. 생성만으로 사용자 트래픽에 적용하지 않습니다.

### POST · `/admin/knowledge/indexes/{version}/activate` · 관리자 인증

평가를 통과한 인덱스 버전을 활성화합니다. 이전 Claim 버전은 과거 응답의 `claim_id`+`version` 재현을 위해 보존합니다.

관리자 쓰기 API는 `Idempotency-Key`, 재인증과 감사 로그가 필요합니다. `review_status=approved`, `version_active=true`가 아닌 Claim과 D·X 등급 근거는 사용자 응답 검색에서 제외합니다.

### POST · `/generations/{generation_id}/feedback` · 인증 필요

Report·Briefing·Chatbot 생성 결과에 대한 평가를 저장합니다.

```json
{
  "rating": "not_helpful",
  "reason_code": "not_personalized",
  "comment": "보유 제품이 반영되지 않았어요."
}
```

`reason_code`는 `helpful`, `not_helpful`, `factually_wrong`, `not_personalized`, `too_alarmist`, `unsafe_medical_expression`, `wrong_product`, `missing_context` 중 하나입니다. 다른 소유자의 `generation_id`는 `404`를 반환합니다. 피드백은 Claim을 자동 수정하지 않고 검수·새 버전 게시 절차의 입력으로만 사용합니다.

## 운영 전 강화 항목

- Presigned 업로드의 quarantine, EXIF 위치정보 제거, 악성 파일·이미지 폭탄 방어와 미완료 객체 lifecycle 정리
- Webhook HMAC canonicalization, timestamp·nonce 검증, 키 회전과 mTLS 검토
- Refresh token 회전·재사용 탐지, JWT 키 회전과 권한 변경 즉시 반영
- 관리자 scope 세분화, MFA, 감사 로그 무결성·보존·경보
- 개인정보 저장 위치별 삭제 증적, 백업 복원 후 재삭제와 수탁자 처리
- 다중 서버 Rate Limit 공유 저장소와 위험 기반 추가 인증

## 버전 관리 이력

> AI 피부케어 앱 백엔드 API 명세서 · 의료적 진단이 아닌 웰니스 목적의 상대적 변화 안내를 위한 계약입니다.

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| `v0.4` | 2026-08-18 | 수분·식단 enum 정리, 14/30일 Report 및 72시간 Pattern Analysis 응답 구조를 현재 Swagger와 정렬, Mock Persona 데이터 생성 규칙(워치·baseline·활동량 미보유 시 임의 생성 금지) 공통 계약에 추가 |
| `v0.3` | 2026-08-16 | Mock Persona MVP profile, 기간 Report, 확장 Briefing·트리거 분석·Chatbot 응답, Vision baseline/previous 변화값 분리, 공통 지식 Claim 관리 계약 반영 |
| `v0.2` | 2026-08-14 | Base URL 통일, 인증 분기·토큰 수명주기, 공통 오류·인가·관리자 정책, multipart 이미지 업로드, 비동기 스캔 상태, 성공 응답, 날짜·문진·PATCH·페이지네이션·멱등성·동의 철회·Rate Limit·Webhook 최소 보안 계약 반영 |
| `v0.1` | 2026-08-14 | 최초 Markdown API 명세 작성 |
