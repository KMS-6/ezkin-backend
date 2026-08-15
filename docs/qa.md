# QA 및 테스트 전략

## 1. 목적

EZkin Backend의 테스트는 빠른 피드백과 실제 배포 환경의 신뢰성을 함께 확보하는 것을 목표로 한다.
MVP 단계에서는 테스트 인프라를 전면 개편하지 않고, 기능 회귀와 PostgreSQL 배포 실패를 막는 데
필요한 검증부터 적용한다.

## 2. 현재 테스트 구조

### pytest

대부분의 API 및 저장소 테스트는 SQLite in-memory DB를 사용한다.

- 설정과 운영 환경 변수 검증
- health 및 DB readiness 응답 검증
- 피부 관리 규칙과 Quick Care 안전 규칙 검증
- 사용자 인증과 선반 API의 대표 흐름 검증
- 제품 생성 및 soft delete 동작 검증

SQLite 테스트는 실행이 빠르고 테스트별 격리가 쉽다는 장점이 있다. 다만 PostgreSQL의 타입,
제약조건, transaction 및 드라이버 동작까지 보장하지는 않는다.

### PostgreSQL CI

GitHub Actions에서는 PostgreSQL 17 서비스에 빈 DB를 만들고 다음을 검증한다.

```bash
uv run alembic upgrade head
uv run alembic current --check-heads
```

이를 통해 실제 PostgreSQL 연결, asyncpg 드라이버, Alembic migration 적용과 head revision 도달 여부를
확인한다. pytest와 PostgreSQL CI는 같은 테스트를 중복하는 것이 아니라 각각 애플리케이션 동작과
배포 DB 호환성을 담당한다.

## 3. MVP 단계의 원칙

현재는 필수 검증만 보강하고 테스트 구조의 전면 고도화는 별도 작업으로 분리한다. 이슈 하나에서
PostgreSQL 설정과 테스트 인프라 리팩터링을 함께 수행하면 변경 범위가 커지고, 실패 원인과 회귀 지점을
추적하기 어려워지기 때문이다.

이번 단계에서 우선하는 항목은 다음과 같다.

- CI에서 실제 PostgreSQL의 DB readiness 검증
- migration을 반복 실행해도 안전한지 확인하는 멱등성 검증
- 운영 환경에서 누락되거나 잘못된 PostgreSQL URL을 거부하는 설정 테스트
- Alembic migration과 ORM 메타데이터 차이 추적

## 4. 후속 고도화 범위

다음 항목은 MVP의 핵심 흐름이 안정된 뒤 별도 이슈로 진행한다.

- SQLite 기반 API 테스트와 대표 PostgreSQL integration test 병행
- 테스트 fixture 및 DB 초기화 방식 공통화
- 인증, 사용자, 선반 API의 실패 케이스 세분화
- 테스트 coverage 측정과 최소 기준 도입
- 테스트 병렬 실행 및 CI 실행시간 최적화

PostgreSQL integration test는 모든 SQLite 테스트를 그대로 반복하지 않는다. migration, 실제 DB
readiness, 사용자와 제품 저장처럼 DB 차이의 영향을 받는 대표 경로만 검증한다.

## 5. 트레이드오프

### 지금 전면 고도화하는 경우

- 장점: SQLite와 PostgreSQL의 동작 차이를 더 일찍 발견하고 테스트 신뢰도를 높일 수 있다.
- 단점: 이슈 범위와 PR 크기가 커져 리뷰, 디버깅, 변경 원인 추적이 어려워진다.

### 필수 검증 후 분리하는 경우

- 장점: 현재 변경을 작고 독립적으로 검증할 수 있으며 MVP 개발 속도를 유지할 수 있다.
- 단점: 당분간 API 통합 테스트 대부분이 SQLite에 의존하므로 PostgreSQL 고유 회귀를 모두 잡지는 못한다.

MVP에서는 두 번째 접근을 선택한다. PostgreSQL integration test suite는 후속 작업으로 구축하고,
품질, 실행시간, CI 비용과 신뢰도를 비교해 확대 여부를 결정한다.

## 6. 로컬 검증 명령

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
docker compose config --quiet
docker compose up -d --wait db
docker compose run --rm migrate
docker compose run --rm migrate uv run --no-sync alembic current --check-heads
docker compose down
```

실제 PostgreSQL 검증 중 생성되는 데이터 볼륨은 `docker compose down`만으로 삭제되지 않는다.
볼륨 삭제는 데이터가 필요하지 않음을 확인한 뒤 별도로 수행한다.

## 7. 알려진 과제

초기 Alembic migration과 현재 ORM 메타데이터 사이에 일부 nullable 및 unique 정의 차이가 있다.
이는 `alembic check`에서 감지되며, 스키마 변경 범위를 검토한 뒤 별도 migration 작업으로 해결한다.
