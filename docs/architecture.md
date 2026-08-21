# 아키텍처 개요

이 문서는 EZkin 백엔드가 전체 시스템에서 어떤 역할을 맡고, 요청이 어떤 계층을 거쳐 처리되는지 요약한다. 프런트엔드와 함께 시스템 전체를 이해하려면 [`KMS-6/ezkin-frontend`](https://github.com/KMS-6/ezkin-frontend)의 `docs/architecture.md`를 함께 참고한다.

## 1. 전체 시스템에서의 위치

```text
┌─────────────┐      HTTPS       ┌───────────────────────┐      SQL       ┌────────────┐
│  Frontend    │ ───────────────▶│  ezkin-backend (this)  │ ─────────────▶│ PostgreSQL │
│ (React/Vite) │◀─────────────── │  FastAPI               │◀───────────── │ (Render)   │
└─────────────┘   JSON response  └───────────────────────┘                └────────────┘
```

- 프런트엔드는 이 저장소가 배포된 Render URL(`docs/deployment.md` 참고)에 REST 호출을 보낸다.
- 백엔드는 도메인별 라우터(`app/api/router.py`)에서 요청을 받아 인증·권한 확인 후 도메인 모듈로 위임한다.
- 데이터는 PostgreSQL 한 곳에 저장하며, Alembic으로 스키마를 관리한다.

## 2. 요청 처리 계층

```text
요청
 → app/api/router.py         (모든 모듈 라우터 통합)
 → app/core/*                (설정, 인증/페르소나 컨텍스트 결정)
 → app/modules/<domain>/     (도메인별 router → schemas → 규칙/서비스 로직)
 → app/db/session.py         (AsyncSession)
 → app/models/*              (SQLAlchemy ORM)
 → PostgreSQL
```

각 도메인 모듈(`care`, `shelf`, `quick_care`, `users` 등)은 자신의 라우터·스키마·규칙 엔진을 캡슐화하고, 공통 의존성(`get_db`, 인증 의존성)만 `app/core`와 `app/db`에서 주입받는다.

## 3. 인증과 사용자 식별 (실제 구현 기준)

초기 설계 문서(`docs/planning`, `docs/architecture` — 상위 저장소 `EZkin_분석출력형식_수정본.md` 등)는 로그인 없이 `X-Mock-Persona-Id` 헤더만으로 개인화를 구현하는 MVP를 가정했다. 이후 실사용자 인증이 추가되면서 현재는 다음과 같이 동작한다.

| 사용자 유형 | 식별 방법 | 관련 문서 |
|---|---|---|
| 실사용자 | 회원가입 시 발급된 서명된 access token (`Authorization` 헤더) | `docs/decisions/001-signed-user-token.md` |
| Demo 페르소나 (persona_001/002/003 등) | `X-Mock-Persona-Id` 헤더, seed 데이터 | `docs/decisions/004-map-real-users-to-personas.md` |

`get_persona`/`get_persona_id` 의존성이 두 경로를 모두 지원한다. 실사용자 토큰이 있으면 `persona_id = str(user_id)`로 매핑된 전용 Persona row를 지연 생성해서 사용하고(있으면 토큰이 항상 우선), 토큰이 없으면 `X-Mock-Persona-Id`로 seed 페르소나를 사용한다. 즉 Briefing·Skin Scan·Daily Metrics·Risk·Reports 등 대부분의 도메인 모듈은 라우터/서비스 코드 변경 없이 두 경로를 그대로 지원한다.

Shelf(화장품 선반) API는 이 페르소나 매핑과 별개로, 서명된 사용자 토큰의 사용자 ID만 소유권 조회에 사용한다(IDOR 방지).

## 4. 개인 데이터와 공통 지식의 분리

- **개인 데이터**: Profile, Shelf, Event(스캔·브리핑·리포트 기록), Feedback — 모두 `persona_id`(또는 매핑된 실사용자)로 파티셔닝된다.
- **공통 지식**: 성분·공식 안전 안내 등 모든 사용자가 공유하는 Claim Card. `knowledge-rag-seed-data.md` 참고.
- 개인 검색 함수는 `persona_id` 없이 실행되지 않는 것을 원칙으로 한다.

전체 데이터 흐름과 설계 배경(Retrieval Orchestrator, Claim Card 구조, Chatbot 규칙 기반 처리 등)은 상위 저장소의 `docs/architecture/system_architecture.md`에 더 자세히 설명되어 있다. 이 문서는 그 설계가 백엔드 코드에서 실제로 어떻게 구현·변형되었는지를 요약한 것이다.

## 5. 배포

- `develop` 브랜치 push → GitHub Actions CI 통과 → Render 자동 배포.
- 컨테이너 시작 시 `alembic upgrade head` 실행 후 `uvicorn` 기동. 자세한 절차는 `docs/deployment.md` 참고.
