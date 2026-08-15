---
name: "senior-devops"
description: "DevOps skill for CI/CD, containerization, and deployment. Use when setting up or debugging GitHub Actions workflows, Render Blueprint (render.yaml), Docker/Docker Compose config, Alembic migration deployment, or health check / rollback procedures. Covers GitHub Actions, Render Web Service + PostgreSQL, Docker, uv-based Python builds, and deployment runbooks."
---

# Senior DevOps Engineer

GitHub Actions + Render + Docker + uv 기반 Python 배포 파이프라인.

---

## GitHub Actions CI

실제 `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
    branches: [develop, main]
  push:
    branches: [develop, main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend:
    name: Backend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          version: "0.8.13"
          enable-cache: true
      - run: uv sync --frozen
      - run: uv run ruff format --check .
      - run: uv run ruff check .
      - run: uv run pytest

  deployment-config:
    name: Deployment config
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ruby -e 'require "yaml"; YAML.load_file("render.yaml")'
      - run: docker compose config --quiet
      - run: docker build -t ezkin-api:ci .
```

**포인트:**
- `uv sync --frozen` — lockfile 기준 재현 가능한 설치
- `ruff format --check` + `ruff check` — 포맷·린트 검사
- `deployment-config` 잡이 render.yaml 파싱, docker-compose, Dockerfile 빌드를 모두 검증

---

## Render Blueprint (render.yaml)

```yaml
services:
  - type: web
    name: ezkin-api
    runtime: docker
    plan: free
    region: singapore
    branch: develop              # develop 브랜치 push → 자동 배포
    dockerfilePath: ./Dockerfile
    dockerContext: .
    healthCheckPath: /health
    autoDeployTrigger: checksPass  # CI 통과 후 배포
    envVars:
      - key: AAC_DATABASE_URL
        fromDatabase:
          name: ezkin-db
          property: connectionString
      - key: AAC_API_PREFIX
        value: /api/v1
      - key: AAC_DEBUG
        value: "false"
      - key: AAC_CORS_ORIGINS
        sync: false              # Render 대시보드에서 수동 설정

databases:
  - name: ezkin-db
    plan: free
    region: singapore
    databaseName: ezkin
    user: ezkin
    postgresMajorVersion: "17"
```

**주의사항:**
- `AAC_CORS_ORIGINS`는 `sync: false` — Render 대시보드에서 JSON 배열로 직접 입력
- 무료 플랜: 15분 비활성 시 슬립, PostgreSQL 90일 만료
- `autoDeployTrigger: checksPass` — CI 실패 시 배포 차단

---

## Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv==0.8.13 && uv sync --frozen --no-dev
COPY . .

CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**포인트:**
- `uv sync --frozen --no-dev` — lockfile 기준 프로덕션 의존성만 설치
- `CMD`에서 `alembic upgrade head` → `uvicorn` 순서로 실행 (마이그레이션 먼저)
- `${PORT:-8000}` — Render가 `PORT` 환경변수 주입

---

## 로컬 개발 환경

```bash
# PostgreSQL 시작
docker compose up db

# 의존성 설치
uv sync --frozen

# 마이그레이션 적용
uv run alembic upgrade head

# 개발 서버 시작
uv run uvicorn app.main:app --reload
```

---

## 배포 절차

```
1. feature/* → develop PR 생성
2. CI 통과 (backend + deployment-config 잡 모두 green)
3. develop 머지 → Render 자동 배포 트리거
4. Render 대시보드에서 배포 로그 확인
5. GET /health → {"status": "ok"} 응답 확인
```

---

## 롤백 절차

```
1. Render 대시보드 → ezkin-api 서비스 → Deploy History
2. 이전 성공 배포 선택 → "Re-deploy" 클릭
3. GET /health 재확인
4. DB 마이그레이션 롤백이 필요한 경우:
   uv run alembic downgrade -1
   (이후 재배포 필요)
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 배포 후 500 에러 | alembic 마이그레이션 실패 | Render 로그에서 alembic 에러 확인 후 스키마 수정 |
| 슬립 후 첫 요청 지연 | 무료 플랜 15분 슬립 | 유료 플랜 업그레이드 또는 헬스체크 ping 설정 |
| CORS 오류 | AAC_CORS_ORIGINS 미설정 | Render 대시보드 환경변수에 JSON 배열 입력 |
| DB 연결 실패 | PostgreSQL 90일 만료 | 새 DB 인스턴스 생성, DATABASE_URL 갱신 |
| CI 실패 — ruff | 포맷·린트 오류 | `uv run ruff format .` 후 재커밋 |
| CI 실패 — pytest | 테스트 실패 | 로컬에서 `uv run pytest -v` 실행 후 수정 |
