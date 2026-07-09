"""Peewee 数据库连接对象与绑定生命周期。"""

from pathlib import Path

from peewee import SqliteDatabase

database = SqliteDatabase(None)


def _normalize_db_path(db_path: str) -> str:
    return str(Path(db_path).expanduser().resolve())


def current_database_path() -> str | None:
    db_path = database.database
    return _normalize_db_path(str(db_path)) if db_path else None


def reset_database_binding() -> None:
    if not database.is_closed():
        _ = database.close()
    database.init(None)  # pyright: ignore[reportUnknownMemberType]


def bind_database(db_path: str, *, pragmas: dict[str, object] | None = None) -> str:
    expected_path = _normalize_db_path(db_path)
    current_path = current_database_path()
    if current_path is None:
        database.init(expected_path, pragmas=pragmas)  # pyright: ignore[reportUnknownMemberType]
        return expected_path
    if current_path == expected_path:
        return expected_path
    raise RuntimeError(f"peewee database already bound: current={current_path}, target={expected_path}")
