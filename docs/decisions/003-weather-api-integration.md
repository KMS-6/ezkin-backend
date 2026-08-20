---
authored_with: Claude Code
features_used: []
date: 2026-08-21
---

# ADR 003: 기상청 공공데이터포털 연동 및 위치 기반 날씨 수집

## 상태

승인됨

## 맥락

`WeatherSnapshot` 테이블은 존재하지만 이를 채우는 외부 API 연동 코드가 전혀 없다.
risk/briefing 로직은 테이블을 읽기만 하고, 임의 날씨 생성은 금지돼 있어(기능명세서_briefing.md
4.1절) 행이 없으면 날씨 요인을 조용히 생략한다. 테스트에서만 mock 데이터를 직접
insert해 시나리오를 재현한다. 또한 Persona/OnboardingProfile에는 위치 정보가 전혀
없어, 실제 API를 호출하려 해도 어느 지역의 날씨를 조회해야 할지 알 수 없다.

이번 결정은 (1) 어떤 외부 날씨 API를 쓸지, (2) 위치를 어떻게 얻을지, (3) 언제
호출하고 실패 시 어떻게 대응할지를 확정한다.

## 결정

### API 제공자

기상청 공공데이터포털(data.go.kr)을 사용한다.

- 온도/습도: 초단기실황조회(`getUltraSrtNcst`) — 항목 T1H(기온), REH(습도)
- UV지수: 생활기상지수 조회서비스의 자외선지수(UV지수) API

무료이고 한국 로컬 데이터(습도, UV지수)를 국내 서비스 대상 MVP에 가장 적합하게
제공한다. 정확한 엔드포인트 경로/파라미터/응답 스키마는 구현 시점에 공식 문서로
재검증한다(버전이 바뀔 수 있음).

### 위치 입력 방식

`OnboardingProfile`에 `latitude`, `longitude`(둘 다 nullable) 컬럼을 추가하고,
`POST /onboarding/profile`에서 다른 필드(skin_concern_ids, birth_year)와 동일하게
저장한다. 위도/경도 → 기상청 격자(nx, ny) 변환은 기상청이 배포하는 Lambert
Conformal Conic 변환식을 순수 함수(`latlon_to_grid`)로 구현해 외부 호출 없이 단위
테스트할 수 있게 한다.

지역 코드/도시명 매핑 테이블 방식 대신 위도/경도를 선택한 이유는 프론트가 GPS
좌표를 그대로 전달할 수 있어 별도 지역 선택 UI나 매핑 테이블 유지보수가
필요 없기 때문이다.

위도/경도가 저장돼 있지 않은 persona는 서울 기본 좌표로 폴백한다. 위치가
없다고 날씨 기능 전체를 비활성화하지 않는다.

### 호출 시점과 캐싱

Briefing/Risk 조회 시점에 on-demand로 호출한다. 별도 스케줄러(cron)를 두지 않는
이유는 해커톤 MVP 범위에서 스케줄링 인프라를 추가로 운영할 필요가 없기 때문이다.
최근 `WeatherSnapshot`이 `weather_cache_ttl_minutes`(기본 60분) 이내면 재호출하지
않고 캐시된 행을 재사용해 과호출을 방지한다.

### 실패 시 폴백

`weather_api_key`(`AAC_WEATHER_API_KEY`)를 `anthropic_api_key`와 동일하게 선택적
`SecretStr | None`으로 관리한다. 키 미설정, 네트워크 오류, 응답 파싱 실패 시
예외를 상위로 전파하지 않고 조용히 `None`을 반환한다 — 기존 "임의 날씨 생성
금지" 원칙을 그대로 유지하며, Anthropic 키 미설정 시 LLM 문장화가 규칙 기반
템플릿으로 폴백하는 것과 동일한 패턴이다.

`weather_location` 동의(consent)가 없으면 위도/경도가 저장돼 있어도 API 호출
자체를 하지 않는다 — 기존 consent 게이팅 로직을 그대로 유지한다.

## 대안 검토

- **OpenWeatherMap / WeatherAPI.com**: 해외 서비스로 국내 습도·UV지수 데이터의
  현지화 정확도가 기상청 대비 낮을 것으로 예상되고, 무료 티어 제약이 있어
  채택하지 않았다.
- **지역코드/도시명 매핑 테이블**: 프론트 UI에 지역 선택 화면이 필요하고
  매핑 테이블을 직접 유지보수해야 해서, GPS 좌표를 그대로 받는 방식보다
  구현·유지보수 비용이 높다고 판단해 제외했다.
- **주기적 스케줄러(cron) 사전 수집**: 더 견고하지만 별도 워커/스케줄링
  인프라가 필요해 해커톤 MVP 범위를 벗어난다고 판단했다.

## 결과

- `OnboardingProfile`에 위치 필드가 추가돼 Alembic 마이그레이션이 필요하다.
- `app/modules/weather/` 신규 모듈(`grid.py`, `client.py`, `service.py`)이 추가된다.
- `risk/logic.py::load_today_risk_context`의 날씨 조회 호출부가 교체된다.
- API 키가 없는 개발/테스트 환경에서도 기존처럼 날씨 요인이 조용히 생략되는
  동작이 보존된다.
