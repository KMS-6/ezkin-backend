from sqlalchemy import String

import app.models  # noqa: F401
from app.db.base import Base


def test_all_string_persona_id_columns_allow_uuid_length() -> None:
    too_short_columns: list[str] = []
    inspected_columns: list[str] = []

    for table in Base.metadata.sorted_tables:
        column = table.columns.get("persona_id")
        if column is None or not isinstance(column.type, String):
            continue

        inspected_columns.append(table.name)
        length = column.type.length
        if length is None or length < 36:
            too_short_columns.append(f"{table.name}.persona_id(length={length})")

    assert inspected_columns, "persona_id String 컬럼을 찾지 못했습니다."
    assert not too_short_columns, (
        "실사용자 UUID persona_id(36자)를 저장할 수 있도록 persona_id 길이는 최소 36이어야 합니다: "
        + ", ".join(too_short_columns)
    )
