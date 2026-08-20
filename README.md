# EZkin Backend

생활·환경 데이터를 활용해 비의료적 피부 관리 정보를 제공하는 EZkin의 FastAPI 백엔드입니다.

> 이 서비스는 의료 진단이나 치료를 제공하지 않습니다. 응급 증상이 감지되면 일반 안내를 중단하고 전문 의료기관 이용을 권고합니다.

## 주요 기능

- 사용자 등록 및 서명된 Bearer 토큰 발급
- 사용자별 화장품 선반 등록·조회·수정·소프트 삭제
- 습도·자외선·사용자 불편 여부에 따른 케어 모드 미리보기
- 응급 증상 표현을 감지하는 Quick Care 안전 점검
- SQLAlchemy 모델과 Alembic 마이그레이션
- Docker, PostgreSQL, Render 배포 구성
- Ruff, pytest, Docker build 기반 GitHub Actions CI

## 기술 스택

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x / asyncpg
- PostgreSQL 17
- Alembic
- uv
- Docker / Docker Compose
- Render

## 프로젝트 구조

```text
app/
├── api/                 # API 라우터 조합
├── core/                # 환경 설정과 인증
├── db/                  # DB 엔진과 세션
├── models/              # SQLAlchemy 모델
└── modules/             # 도메인별 API와 규칙
alembic/                 # DB 마이그레이션
tests/                   # 테스트
docs/                    # 배포·컨벤션·ADR 문서
compose.yaml             # 로컬 PostgreSQL과 API 구성
render.yaml              # Render Blueprint
```

## 로컬 실행

### 1. 요구 사항

- Python 3.12 이상
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop 또는 Docker Engine

### 2. 환경변수 준비

```bash
cp .env.example .env
```

`.env`에서 `AAC_AUTH_SECRET`을 충분히 긴 무작위 값으로 변경합니다. 실제 비밀값이 포함된 `.env`는 커밋하지 않습니다.

`AAC_CORS_ORIGINS`는 쉼표 구분 문자열이 아닌 JSON 배열 형식으로 작성합니다.

```dotenv
AAC_CORS_ORIGINS=["http://localhost:5173"]
```

### 3. PostgreSQL 실행

```bash
docker compose up -d db
docker compose ps
```

### 4. 의존성 설치와 마이그레이션

```bash
uv sync --frozen
uv run alembic upgrade head
```

### 5. API 실행

```bash
uv run uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

현재 전체 `docker compose up` 실행 경로의 인증 환경변수 전달과 PostgreSQL 통합 검증은 [Issue #9](https://github.com/KMS-6/ezkin-backend/issues/9)에서 보완합니다.

## API 인증

`POST /api/v1/users`로 사용자를 등록하면 `access_token`이 발급됩니다. 선반 API는 토큰을 Authorization 헤더로 전달해야 합니다.

```http
Authorization: Bearer <access_token>
```

`X-User-Id`는 인증 수단으로 사용하지 않습니다.

## 주요 API

| Method | Endpoint | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/health` | 애플리케이션 상태 확인 | 불필요 |
| `POST` | `/api/v1/users` | 사용자 등록 및 토큰 발급 | 불필요 |
| `GET` | `/api/v1/shelf/products` | 내 선반 제품 목록 | Bearer |
| `POST` | `/api/v1/shelf/products` | 내 선반 제품 등록 | Bearer |
| `GET` | `/api/v1/shelf/products/{product_id}` | 내 선반 제품 조회 | Bearer |
| `PATCH` | `/api/v1/shelf/products/{product_id}` | 내 선반 제품 수정 | Bearer |
| `DELETE` | `/api/v1/shelf/products/{product_id}` | 내 선반 제품 삭제 | Bearer |
| `POST` | `/api/v1/care-contexts/preview` | 케어 모드 미리보기 | 불필요 |
| `POST` | `/api/v1/quick-care/safety-check` | 응급 증상 안전 점검 | 불필요 |

정확한 요청·응답 스키마는 실행 중인 Swagger UI에서 확인합니다.

## 테스트와 정적 검사

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
docker compose config --quiet
docker build -t ezkin-api:local .
```

## 배포

Render는 `main` 브랜치의 CI가 통과하면 `render.yaml`을 기준으로 FastAPI와 PostgreSQL을 배포합니다. 최초 Blueprint 생성, 필수 환경변수 설정, 검증 및 롤백 절차는 [배포 가이드](docs/deployment.md)를 참고합니다.

배포 전 다음 값을 Render 환경변수에 설정해야 합니다.

- `AAC_CORS_ORIGINS`
- `AAC_AUTH_SECRET`
- `AAC_ADMIN_API_KEY`
- `AAC_PARTNER_API_KEY`

`AAC_DATABASE_URL`은 Render PostgreSQL 연결 문자열에서 자동으로 주입됩니다.

## 협업 문서

- [배포 가이드](docs/deployment.md)
- [코드 리뷰 컨벤션](docs/conventions/code-review.md)
- [GitHub 워크플로](docs/conventions/github-workflow.md)
- [ADR: 서명된 사용자 토큰](docs/decisions/001-signed-user-token.md)
- [변경 이력](CHANGELOG.md)

## 현재 범위

- `CareContext`, `CareRoutine`, `RoutineStep`은 스키마만 존재하며 아직 DB 쓰기 경로가 없습니다.
- 이미지 스캔 기반 제품 등록과 AI confidence 기록은 후속 구현 대상입니다.
- 다중 인스턴스 Rate Limit은 Redis 등 공유 저장소와 함께 구성해야 합니다.
