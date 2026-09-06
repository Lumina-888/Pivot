"""M03 SQLite 测试 Fixture。

SQLite 只用于快速测试；PostgreSQL partial unique index、DB 权限和生产触发器
必须在集成环境单独验证，详见 migrations/README.md。
"""

from collections.abc import Iterator

import pytest
from pivot.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
