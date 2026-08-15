# EZkin Backend

피부 케어 앱 백엔드. 생활·환경 데이터를 기반으로 비의료적 피부 관리 참고 정보를 제공한다.

## Tech Stack

- **Runtime**: Python 3.12+ / uv
- **Framework**: FastAPI 0.116+
- **ORM**: SQLAlchemy 2.0 (async) + Alembic
- **DB**: PostgreSQL (프로덕션) / SQLite in-memory (테스트)
- **Linter**: Ruff (포맷 + 린트)
- **Test**: pytest + pytest-asyncio (`asyncio_mode = "auto"`)
- **Deploy**: Render — `render.yaml` Blueprint, `develop` 브랜치 자동 배포
- **CI**: GitHub Actions (`.github/workflows/ci.yml`)

## Key Commands

```bash
uv sync --frozen                  # 의존성 설치
uv run ruff format --check .      # 포맷 검사
uv run ruff check .               # 린트
uv run pytest                     # 전체 테스트
docker compose up db              # 로컬 PostgreSQL 시작
uv run alembic upgrade head       # 마이그레이션 적용
uv run uvicorn app.main:app --reload  # 개발 서버
```

## Project Structure

```
app/
  core/config.py       # pydantic-settings (AAC_ 환경변수 prefix)
  db/
    base.py            # UUIDPrimaryKeyMixin, TimestampMixin, Base
    session.py         # get_db() dependency
  models/              # SQLAlchemy ORM 모델
    user.py, care.py, shelf.py
  modules/             # 기능 단위 모듈
    care/              # 케어 컨텍스트 + 규칙 엔진 (rules.py, router.py)
    quick_care/        # 안전 체크 엔드포인트
    shelf/             # 화장품 제품 CRUD (schemas.py, router.py)
    users/             # 사용자 등록
  api/router.py        # 모든 모듈 라우터 통합
alembic/               # DB 마이그레이션
tests/                 # pytest-asyncio, SQLite in-memory
docs/
  deployment.md        # Render 배포 절차
  conventions/
    code-review.md     # PR 크기·코드 리뷰 컨벤션
```

## Code Patterns

**모듈 추가 시:**
- ORM 모델: `app/models/<name>.py` → `app/models/__init__.py`에 등록
- 스키마: `app/modules/<name>/schemas.py`
- 라우터: `app/modules/<name>/router.py` → `app/api/router.py`에 등록
- 마이그레이션: `uv run alembic revision --autogenerate -m "설명"`

**공통 패턴:**
- Soft delete: `deleted_at` timestamp + `is_active` flag
- 인증: `X-User-Id` 헤더 기반 (개발 임시), 추후 JWT 교체 예정
- DB 세션: `Annotated[AsyncSession, Depends(get_db)]`
- 설정 주입: `from app.core.config import settings`

**테스트 패턴:**
- SQLite in-memory 엔진 + `Base.metadata.create_all`
- `app.dependency_overrides[get_db] = override_db`로 DB 교체
- `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`

## Deployment

- `develop` 브랜치 push → CI 통과 → Render 자동 배포
- 컨테이너 시작: `alembic upgrade head` → `uvicorn` 실행
- `AAC_CORS_ORIGINS`: Render 대시보드에서 JSON 배열로 수동 설정
- 헬스체크: `GET /health` → `{"status": "ok"}`
- 무료 플랜 주의: 15분 비활성 시 슬립, PostgreSQL 30일 만료

---

# Karpathy Guidelines

Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
