"""SQLAlchemy Run / EventLog store (sqlite stand-in). Not GATE-P0 verified."""

from __future__ import annotations

from datetime import UTC, datetime

from pivot.db.models import AgentEvent, Conversation, Message, Run, User
from pivot.db.runs import SqlAlchemyRunStore
from pivot.runs.models import RunBundle, RunRecord, run_fingerprint, synthetic_user_message_id
from pivot.stream.buffer import EventLog


def _seed_conversation(db_session, user_id: str = "usr_alice") -> None:
    db_session.add(
        User(
            id=user_id,
            username=user_id.removeprefix("usr_"),
            password_hash="hash",
            role="user",
            status="active",
        )
    )
    db_session.add(
        Conversation(
            id="conv_policy",
            owner_id=user_id,
            title="迟到规则",
            scope_type="global",
        )
    )
    db_session.commit()


def _bundle(**overrides: object) -> RunBundle:
    now = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "id": "run_policy",
        "conversation_id": "conv_policy",
        "message_id": "msg_assistant",
        "owner_id": "usr_alice",
        "question": "迟到三次怎么处理",
        "idempotency_key": "idem-policy",
        "fingerprint": run_fingerprint("迟到三次怎么处理", "global", None),
        "scope_type": "global",
        "scope_document_id": None,
        "state": "refused",
        "error_code": None,
        "answer_markdown": "",
        "created_at": now,
    }
    values.update(overrides)
    return RunBundle(run=RunRecord(**values))  # type: ignore[arg-type]


def test_M03_sqlalchemy_run_store_persists_spec_fields(db_session):
    _seed_conversation(db_session)
    store = SqlAlchemyRunStore(db_session)
    bundle = _bundle()
    store.save(bundle)

    loaded = store.get("run_policy")
    assert loaded is not None
    assert loaded.run.id == "run_policy"
    assert loaded.run.conversation_id == "conv_policy"
    assert loaded.run.message_id == "msg_assistant"
    assert loaded.run.owner_id == "usr_alice"
    assert loaded.run.question == "迟到三次怎么处理"
    assert loaded.run.idempotency_key == "idem-policy"
    assert loaded.run.fingerprint == run_fingerprint("迟到三次怎么处理", "global", None)
    assert loaded.run.scope_type == "global"
    assert loaded.run.scope_document_id is None
    assert loaded.run.state == "refused"
    assert loaded.run.created_at == datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    row = db_session.get(Run, "run_policy")
    assert row is not None
    assert "fingerprint" not in {column.key for column in Run.__table__.columns}
    assert "owner_id" not in {column.key for column in Run.__table__.columns}
    assert "answer_markdown" not in {column.key for column in Run.__table__.columns}
    assert store.get("missing") is None
    listed = store.list_for_conversation("conv_policy")
    assert [item.run.id for item in listed] == ["run_policy"]
    by_key = store.get_by_idempotency("conv_policy", "idem-policy")
    assert by_key is not None
    assert by_key.run.id == "run_policy"


def test_M03_sqlalchemy_run_store_persists_event_log(db_session):
    _seed_conversation(db_session)
    store = SqlAlchemyRunStore(db_session)
    bundle = _bundle(state="answered", answer_markdown="三次书面警告")
    log = EventLog(bundle.run.id, bundle.run.message_id)
    log.emit("run_started", "received", {})
    log.emit("stage", "normalize", {"stage": "normalize"})
    log.emit("token", "drafting", {"text": "三次书面警告"})
    log.emit("completed", "answered", {"error_code": None})
    store.save(bundle, log)

    loaded_log = store.get_log("run_policy", "msg_assistant")
    assert loaded_log is not None
    frames = loaded_log.replay()
    assert [name for name, _data in frames] == [
        "run_started",
        "stage",
        "token",
        "completed",
    ]
    assert [data["seq"] for _name, data in frames] == [1, 2, 3, 4]
    assert frames[1][1]["payload"] == {"stage": "normalize"}
    assert frames[2][1]["payload"] == {"text": "三次书面警告"}
    assert loaded_log.terminal == "completed"
    later = loaded_log.replay(last_event_id=2)
    assert [data["seq"] for _name, data in later] == [3, 4]
    loaded = store.get("run_policy")
    assert loaded is not None
    assert loaded.run.answer_markdown == "三次书面警告"
    assistant = db_session.get(Message, "msg_assistant")
    assert assistant is not None
    assert assistant.sender == "assistant"
    assert assistant.content == "三次书面警告"
    user = db_session.get(Message, synthetic_user_message_id("run_policy"))
    assert user is not None
    assert user.sender == "user"
    assert user.content == "迟到三次怎么处理"
    events = db_session.query(AgentEvent).filter_by(run_id="run_policy").all()
    assert {column.key for column in AgentEvent.__table__.columns} >= {
        "id",
        "run_id",
        "stage",
        "summary",
        "seq",
        "duration_ms",
        "created_at",
    }
    assert len(events) == 4
    blob = " ".join(row.summary for row in events)
    assert "thinking" not in blob.lower()
    assert "SYSTEM_PROMPT" not in blob
