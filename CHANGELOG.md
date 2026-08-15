# Changelog

이 프로젝트의 주요 변경 사항을 이 파일에 기록한다. 버전은 Semantic Versioning을 따른다.

## [Unreleased]

### Added

- PostgreSQL 연결 풀 검증, DB readiness endpoint, 실제 PostgreSQL migration CI를 추가함
- 로컬 PostgreSQL migration과 백업·복구 절차를 문서화함

### Fixed

- 선반 API가 서명된 사용자 토큰을 검증하도록 수정함
- 응급 증상의 다양한 표현을 감지하도록 보완함
- PostgreSQL migration 동시 실행을 advisory lock으로 직렬화함
- 운영 환경에서 `AAC_DATABASE_URL`이 없거나 SQLite를 가리키면 시작을 중단하도록 수정함

## [0.1.0] - 2026-08-15

### Added

- FastAPI 백엔드 기본 구조와 케어 API를 추가함
- SQLAlchemy 모델과 Alembic 초기 마이그레이션을 추가함
- Docker 및 Docker Compose 실행 환경을 추가함
- Render Web Service와 PostgreSQL Blueprint을 추가함
- Ruff, pytest, Docker build 기반 GitHub Actions CI를 추가함
- Render 배포 절차와 검증·롤백 절차를 문서화함
- PR 크기·코드 리뷰 컨벤션을 문서화함
