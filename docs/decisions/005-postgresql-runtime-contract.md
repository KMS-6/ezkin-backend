---
authored_with: Codex
features_used:
  - github:github
date: 2026-08-16
---

# ADR 005: 운영 데이터베이스를 PostgreSQL로 강제한다

## 상태

Accepted

## 배경

개발 기본값인 SQLite가 운영 환경에서도 사용되면 배포는 성공해 보이지만 인스턴스 재시작 시 데이터가
유실될 수 있다. 또한 단위 테스트만으로는 PostgreSQL 드라이버, 연결, Alembic migration의 호환성을
검증할 수 없다.

## 결정

- `AAC_APP_ENV=production`에서는 명시적인 PostgreSQL `AAC_DATABASE_URL`을 필수로 한다.
- PostgreSQL 엔진은 연결 전 `pool_pre_ping`을 수행하고 제한된 QueuePool을 사용한다.
- 프로세스 health와 DB readiness를 `/health`, `/health/db`로 분리한다.
- CI에서 PostgreSQL 17 서비스의 빈 DB에 `alembic upgrade head`와
  `alembic current --check-heads`를 실행한다.
- 로컬 Compose와 Render는 동일한 production 검증 경로를 사용한다.

## 고려한 대안

- `DEBUG=false`로 운영 판별: 별도 환경 변수가 필요 없지만 로컬 기본 실행도 운영으로 오인한다.
- 모든 환경에서 PostgreSQL 강제: 운영과 개발의 차이는 줄지만 빠른 단위 테스트와 초기 로컬 실행이
  어려워진다.
- 애플리케이션 시작 시 DB 연결 강제: 장애를 빠르게 드러내지만 일시적인 DB 장애가 모든 프로세스
  시작을 막는다. readiness endpoint로 오케스트레이터가 상태를 판단하게 하는 편이 복구에 유리하다.

## 결과와 트레이드오프

- 운영 SQLite 오배포와 migration 호환성 회귀를 배포 전에 감지한다.
- 환경 종류를 나타내는 `AAC_APP_ENV` 설정을 배포 환경마다 관리해야 한다.
- readiness 요청마다 간단한 DB 쿼리가 발생하지만 풀의 연결 상태까지 검증할 수 있다.
