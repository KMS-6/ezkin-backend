from logging.config import fileConfig

from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app import models  # noqa: F401
from app.core.config import settings
from app.db.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    uses_postgresql = connection.dialect.name == "postgresql"
    if uses_postgresql:
        connection.execute(text("SELECT pg_advisory_lock(hashtext('ezkin_alembic_migration'))"))
    try:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        # NOTE: pg_advisory_lock 실행이 SQLAlchemy 2.0 autobegin 트랜잭션을 먼저 열어버려서
        # context.begin_transaction()이 이를 "이미 열린 트랜잭션"으로 보고 커밋을 위임만 하고
        # 직접 커밋하지 않는다. 명시적으로 커밋하지 않으면 연결 종료 시 전체가 롤백된다.
        connection.commit()
    finally:
        if uses_postgresql:
            connection.execute(
                text("SELECT pg_advisory_unlock(hashtext('ezkin_alembic_migration'))")
            )


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
