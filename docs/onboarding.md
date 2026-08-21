# 온보딩 가이드

이 저장소에 새로 합류한 개발자를 위한 첫 실행 순서와 필수로 알아야 할 개념을 정리한다. 프로젝트 전반 소개는 `README.md`를 먼저 읽는다.

## 0. PRD 핵심 요약 (반드시 먼저 읽기)

백엔드 API와 규칙 엔진은 모두 아래 제품 목표를 구현하기 위한 수단이다. 기능을 구현하기 전에 왜 이 데이터가 필요한지 확인한다.

- **목표**: 카메라 스캔, 웨어러블 생체 데이터, 날씨 데이터를 교차 분석해 사용자의 매일 달라지는 피부 상태에 맞는 개인화 스킨케어 처방을 제공한다. 수동 기록 부담을 최소화하고, 보유 화장품을 우선 활용한다.
- **핵심 제약**: 의료적 진단·치료·인과관계 단정을 하지 않는다. 피부 위험도는 낮음·보통·높음·매우 높음의 웰니스 안내로만 제공하며, 고위험 증상에는 전문가 상담을 안내한다.
- **타겟 사용자**: 생활 패턴 변화로 피부 고민을 겪지만 매일 기록하는 방식에는 피로를 느끼는 13~34세. 핵심 페르소나는 야근·회식으로 생활이 불규칙하고 생리 전 트러블을 겪는 25~34세 직장인.
- **핵심 지표**: 온보딩 완료율, 아침 브리핑 열람률, 7일·30일 유지율, 주간 피부 스캔 완료율, SOS 챗봇 이용률.
- 백엔드 코드에서 이 목표가 어떻게 도메인 모듈(Briefing/Scan/Risk/Reports)로 구현되는지는 `docs/architecture.md`를 참고한다. 전체 PRD 원문은 중앙 기획 문서 저장소의 `docs/planning/PRD.md`에 있다(이 저장소에는 포함되지 않음).

## 1. 첫날 체크리스트

1. Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker Desktop(또는 Engine) 설치를 확인한다.
2. `cp .env.example .env` 후 `AAC_AUTH_SECRET`을 무작위 값으로 교체한다. `.env`는 커밋하지 않는다.
3. `uv sync --frozen`으로 의존성을 설치한다.
4. `docker compose up db`로 로컬 PostgreSQL을 띄운다.
5. `uv run alembic upgrade head`로 마이그레이션을 적용한다.
6. `uv run uvicorn app.main:app --reload`로 개발 서버를 실행하고 `GET /health`가 `{"status": "ok"}`를 반환하는지 확인한다.
7. `uv run pytest`와 `uv run ruff check .`를 실행해 기본 검증이 통과하는지 확인한다.

## 2. 먼저 읽어야 할 문서 (순서대로)

1. `README.md` — 기술 스택, 프로젝트 구조, 로컬 실행
2. `docs/architecture.md` — 전체 시스템에서 이 저장소의 역할, 인증/페르소나 흐름
3. `docs/decisions/001-signed-user-token.md`, `004-map-real-users-to-personas.md` — 인증과 사용자 식별의 현재 동작 방식 (가장 헷갈리기 쉬운 부분)
4. `docs/conventions/code-review.md`, `docs/conventions/github-workflow.md` — PR과 브랜치 규칙
5. `docs/qa.md` — 알려진 이슈와 점검 항목
6. `docs/deployment.md` — Render 배포 절차

## 3. 반드시 이해해야 하는 개념

### 페르소나 vs 실사용자
- 대부분의 도메인 모듈(Briefing, Skin Scan, Daily Metrics, Risk, Reports 등)은 "페르소나"라는 단위로 개인화 데이터를 파티셔닝한다.
- **실사용자**는 회원가입 후 발급된 access token으로 요청하면, 내부적으로 자신만의 Persona row에 매핑되어 동일한 기능을 그대로 사용한다.
- **Demo 페르소나**(persona_001/002/003 등)는 `X-Mock-Persona-Id` 헤더로 seed 데이터를 사용한다.
- 두 경로 중 실사용자 토큰이 있으면 항상 우선한다. 자세한 내용은 `docs/decisions/004-map-real-users-to-personas.md` 참고.

### Shelf(화장품 선반) API의 별도 인증
- Shelf API는 페르소나 매핑과 무관하게, 서명된 사용자 토큰의 사용자 ID만으로 소유권을 검증한다. `X-User-Id`를 그대로 신뢰하지 않는다.
- `persona_001`/`persona_002`/`persona_003` 등 기본 Demo 페르소나는 애플리케이션 코드나 별도 시드 스크립트가 아니라 Alembic 마이그레이션(`20260816_0002`)의 `bulk_insert`로 생성된다.
- Admin 전용 엔드포인트는 `X-Admin-Key`, Partner 전용 엔드포인트는 `X-Partner-Key`로 별도 인증한다. 위 페르소나/실사용자 인증과는 다른 체계다.

### 모듈 추가 패턴
- ORM 모델: `app/models/<name>.py` → `app/models/__init__.py`에 등록
- 스키마: `app/modules/<name>/schemas.py`
- 라우터: `app/modules/<name>/router.py` → `app/api/router.py`에 등록
- 마이그레이션: `uv run alembic revision --autogenerate -m "설명"`

### 테스트 작성 패턴
- SQLite in-memory 엔진 + `Base.metadata.create_all`
- `app.dependency_overrides[get_db] = override_db`로 DB 교체
- `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`

## 4. 막힐 때

- 코드 패턴과 커맨드 요약은 저장소 루트의 `AGENTS.md` / `CLAUDE.md`에도 정리되어 있다.
- 되돌리기 어려운 결정(인증, DB, 인프라 등)은 `docs/decisions/`의 ADR을 먼저 확인한다. 새 결정을 내릴 때도 같은 형식으로 ADR을 추가한다.
