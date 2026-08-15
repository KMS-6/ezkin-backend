---
name: "senior-backend"
description: "Designs and implements backend systems including REST APIs, database architectures, authentication flows, and security hardening. Use when the user asks to design FastAPI endpoints, optimize SQLAlchemy queries, implement authentication, add a new module, review backend code, handle Alembic migrations, or load test APIs. Covers FastAPI/Python development, SQLAlchemy 2.0 async, PostgreSQL optimization, Pydantic schemas, and API security patterns."
---

# Senior Backend Engineer

FastAPI/Python 백엔드 개발 패턴 — SQLAlchemy 2.0 async, Pydantic v2, Alembic, PostgreSQL.

---

## 새 모듈 추가 체크리스트

```
1. app/models/<name>.py          — ORM 모델 (UUIDPrimaryKeyMixin + TimestampMixin)
2. app/models/__init__.py        — 모델 등록 (alembic autogenerate가 감지하도록)
3. app/modules/<name>/schemas.py — Pydantic v2 요청/응답 스키마
4. app/modules/<name>/router.py  — APIRouter 정의
5. app/api/router.py             — include_router() 등록
6. alembic revision --autogenerate -m "설명"
7. uv run pytest                 — 신규 엔드포인트 테스트 추가
```

---

## FastAPI 라우터 패턴

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.shelf import Cosmetic

router = APIRouter(prefix="/shelf/products", tags=["my-shelf"])

# X-User-Id 헤더 기반 인증 (개발 임시 — 추후 JWT 교체)
def get_current_user_id(
    x_user_id: Annotated[UUID, Header(alias="X-User-Id")],
) -> UUID:
    return x_user_id

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]

# 소유권 확인 헬퍼 (소프트 딜리트 필터 포함)
async def _owned_or_404(db: AsyncSession, product_id: UUID, user_id: UUID) -> Cosmetic:
    result = await db.execute(
        select(Cosmetic).where(
            Cosmetic.id == product_id,
            Cosmetic.user_id == user_id,
            Cosmetic.deleted_at.is_(None),
        )
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail="리소스를 찾을 수 없습니다.")
    return obj

@router.post("", response_model=ResponseSchema, status_code=status.HTTP_201_CREATED)
async def create(payload: CreateSchema, db: DbSession, user_id: CurrentUserId):
    obj = Model(user_id=user_id, **payload.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj

@router.patch("/{id}", response_model=ResponseSchema)
async def update(id: UUID, payload: UpdateSchema, db: DbSession, user_id: CurrentUserId):
    obj = await _owned_or_404(db, id, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await db.commit()
    await db.refresh(obj)
    return obj

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(id: UUID, db: DbSession, user_id: CurrentUserId) -> Response:
    from datetime import UTC, datetime
    obj = await _owned_or_404(db, id, user_id)
    obj.deleted_at = datetime.now(UTC)  # 소프트 딜리트 — is_active도 함께 변경
    obj.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

---

## ORM 모델 패턴

```python
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class MyModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "my_models"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    value: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

**공통 Mixin:**
- `UUIDPrimaryKeyMixin` — `id: UUID` (uuid4 기본값)
- `TimestampMixin` — `created_at`, `updated_at` (server_default + onupdate=func.now())
- 타임스탬프가 필요 없는 테이블(예: RoutineStep)은 Mixin 없이 선언

---

## Pydantic v2 스키마 패턴

```python
from pydantic import BaseModel, ConfigDict, Field

class MyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: str | None = None

class MyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    value: str | None = None
    # is_active 제외 — 소프트 딜리트 불변 조건: DELETE 엔드포인트에서만 변경

class MyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    value: str | None
    created_at: datetime
    updated_at: datetime
```

**주의:** `model_dump(exclude_unset=True)`는 명시적으로 보낸 `null`을 포함한다.
업데이트 시 `setattr(obj, field, value)`로 처리하면 의도치 않은 null 덮어쓰기 발생 가능.

---

## Alembic 마이그레이션 워크플로

```bash
# 1. 모델 변경 후 마이그레이션 생성
uv run alembic revision --autogenerate -m "add cosmetics table"

# 2. 생성된 파일 검토 (alembic/versions/*.py)
#    - upgrade() / downgrade() 확인
#    - server_default, onupdate 등 누락 여부 확인

# 3. 로컬 적용 (docker compose up db 필요)
uv run alembic upgrade head

# 4. 한 단계 롤백
uv run alembic downgrade -1

# 5. 현재 상태 확인
uv run alembic current
uv run alembic history --verbose
```

---

## DB 세션 / 의존성 패턴

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

---

## 소프트 딜리트 패턴

- `deleted_at: datetime | None` + `is_active: bool` 조합
- DELETE 엔드포인트에서만 두 필드를 함께 변경
- 조회 시 항상 `Cosmetic.deleted_at.is_(None)` 필터 적용
- Update 스키마에서 `is_active` 필드 제외 (불변 조건 강화)

---

## PostgreSQL 최적화

```sql
-- 자주 쓰는 필터 컬럼에 인덱스
CREATE INDEX ix_cosmetics_user_id ON cosmetics(user_id);

-- 복합 인덱스 (다중 컬럼 조회)
CREATE INDEX ix_orders_user_status ON orders(user_id, status);

-- 부분 인덱스 (활성 레코드만)
CREATE INDEX ix_cosmetics_active ON cosmetics(user_id) WHERE deleted_at IS NULL;
```

SQLAlchemy에서:
```python
user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
```

---

## 보안 체크리스트

- [ ] 인증 없는 엔드포인트 없음 (`X-User-Id` 헤더 필수)
- [ ] 소유권 확인 (`user_id` 필터 없이 `id`만으로 조회 금지)
- [ ] 환경변수 설정 (`AAC_*` prefix, `app/core/config.py`)
- [ ] `.env` 파일 커밋 금지 (`.gitignore` 확인)
- [ ] Pydantic 스키마로 입력값 검증 (`Field(min_length=1, max_length=N)`)
- [ ] SQL 인젝션 — SQLAlchemy ORM 사용으로 방지
- [ ] CORS 설정 (`AAC_CORS_ORIGINS` 환경변수, Render 대시보드에서 수동 설정)
