"""SQLAlchemy conversation store (sqlite stand-in). Not GATE-P0 verified."""

from __future__ import annotations

from datetime import UTC, datetime

from pivot.db.conversations import SqlAlchemyConversationStore
from pivot.db.models import Conversation, User
from pivot.runs.conversations import ConversationRecord


def _seed_user(db_session, user_id: str = "usr_alice") -> None:
    db_session.add(
        User(
            id=user_id,
            username=user_id.removeprefix("usr_"),
            password_hash="hash",
            role="user",
            status="active",
        )
    )
    db_session.commit()


def _record(**overrides: object) -> ConversationRecord:
    now = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "id": "conv_policy",
        "owner_id": "usr_alice",
        "title": "迟到规则",
        "scope_type": "global",
        "created_at": now,
        "updated_at": now,
        "scope_document_id": None,
        "hidden": False,
    }
    values.update(overrides)
    return ConversationRecord(**values)  # type: ignore[arg-type]


def test_M03_sqlalchemy_conversation_store_persists_spec_fields(db_session):
    _seed_user(db_session)
    store = SqlAlchemyConversationStore(db_session)
    store.save(_record())

    loaded = store.get("conv_policy")
    assert loaded is not None
    assert loaded.id == "conv_policy"
    assert loaded.owner_id == "usr_alice"
    assert loaded.title == "迟到规则"
    assert loaded.scope_type == "global"
    assert loaded.scope_document_id is None
    assert loaded.hidden is False
    assert loaded.created_at == datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    row = db_session.get(Conversation, "conv_policy")
    assert row is not None
    assert "hidden" not in {column.key for column in Conversation.__table__.columns}
    assert store.get("missing") is None

    listed = store.list_for_owner("usr_alice")
    assert [item.id for item in listed] == ["conv_policy"]
    assert store.list_for_owner("usr_bob") == ()


def test_M03_sqlalchemy_conversation_store_hide_deletes_row(db_session):
    _seed_user(db_session)
    store = SqlAlchemyConversationStore(db_session)
    store.save(_record(scope_type="document", scope_document_id="doc_handbook"))
    loaded = store.get("conv_policy")
    assert loaded is not None
    loaded.hidden = True
    store.save(loaded)
    assert store.get("conv_policy") is None
    assert store.list_for_owner("usr_alice") == ()
    assert db_session.get(Conversation, "conv_policy") is None
