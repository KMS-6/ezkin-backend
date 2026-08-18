# Render 배포 가이드

## 1. 배포 구조

```text
EZkin Frontend
  └─ HTTPS → ezkin-api (Render Web Service, FastAPI)
                  └─ private network → ezkin-db (Render PostgreSQL)
```

저장소 루트의 `render.yaml`이 API와 PostgreSQL 설정의 단일 기준이다. `develop` 브랜치 push → GitHub Actions CI 통과 → CD 잡이 Render Deploy Hook 호출 → Render 자동 배포 순으로 진행된다.

## 2. Render 선택 이유

해커톤 MVP의 우선순위는 배포 속도, 재현 강능성, 비용을 위해 Render를 선택했다.

- Docker FastAPI와 PostgreSQL을 한 플랫폼에서 관리할 수 있다.
- Blueprint로 인프라 설정을 코드 리뷰하고 PR에서 검토할 수 있다.
- `checksPass`로 CI가 실패한 코드의 자동 배포를 막는다.
- 아마존, Railway보다 배포와 로그 화인 지점이 더 단순하다.

무료 Web Service는 15분간 무요청 후 정지하고, 무료 PostgreSQL은 30일 후 만료된다. 30일 이상 운영하거나 실제 데이터를 보존해야 할 경우 유료 계획으로 이전한다.

## 3. 최초 Blueprint 생성

1. Render Dashboard에서 **New > Blueprint**를 선택한다.
2. `KMS-6/ezkin-backend` 저장소를 연결한다.
3. Blueprint branch를 `develop`로 설정한다.
4. `AAC_CORS_ORIGINS`에 실제 프런트 origin을 JSON 배열로 입력한다.
5. `AAC_AUTH_SECRET`, `AAC_ADMIN_API_KEY`, `AAC_PARTNER_API_KEY`에 각각 충분히 긴 무작위 비밀값을 입력한다. 저장소에 커밋하지 않는다.
6. GitHub 저장소 **Settings > Secrets and variables > Actions**에서 `RENDER_DEPLOY_HOOK_URL`을 추가한다.
   - Render 대시보드 → ezkin-api 서비스 → **Settings > Deploy Hook** 에서 URL을 복사한다.

```text
["https://<frontend-host>"]
```

`AAC_CORS_ORIGINS`는 쉼표 구분 문자열이 아니라 JSON 배열이어야 한다.

`AAC_DATABASE_URL`은 Blueprint가 `ezkin-db`의 내부 연결 문자열에서 자도 주입한다.

## 4. 배포 동작

1. 컨테이너가 시작하며 `alembic upgrade head`를 실행한다. PostgreSQL에서는 advisory lock으로 동시 migration을 직렬화한다.
2. Render가 주입한 `PORT`와 `0.0.0.0`에 API 서버를 바인딩한다.
3. `/health`가 HTTP 200을 반환해야 새 배포가 유효하다.
4. `develop` 브랜치에 push되면 GitHub Actions `backend` · `deployment-config` 잡이 실행된다.
5. 두 잡이 모두 통과하면 `deploy` 잡이 Render Deploy Hook을 POST 호출한다.
6. Render가 새 이미지를 빌드하고 `/health`가 200을 반환하면 배포가 완료된다.

## 5. 검증

```bash
curl --fail --show-error https://<api-host>/health
curl --fail --show-error https://<api-host>/openapi.json
```

- `/health`가 `{"status":"ok"}`를 응답한다.
- Render 로그에서 Alembic migration 성공을 화인한다.
- 프런트엔드에서 CORS 오류가 없는지 화인한다.

## 6. 롤백

1. Render Events와 로그에서 build, migration, health check 중 실패 단계를 화인한다.
2. 애플리케이션 오류라며 이전 성공 배포로 rollback한다.
3. DB migration이 하햐 호환되지 않으며 애플리케이션만 rollback해도 복구되지 않을 수 있다.
4. migration downgrade는 검증 없이 실행하지 않는다.

## 7. 로컬 점검

```bash
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run pytest
docker compose config --quiet
docker build -t ezkin-api:local .
```

## 8. MVP 범위와 남은 운영 과제

- `CareContext`, `CareRoutine`, `RoutineStep`은 스키마만 정의되어 있고 아직 쓰기 경로가 없다.
- `Cosmetic.ai_confidence`와 `image_scan` 등록 경로는 후속 구현 대상이다.
- 다중 인스턴스에서 공유하는 Rate Limit은 Redis 등 공유 저장소와 함께 후속 적용한다.
