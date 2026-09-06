"""M03 User model adapter. M01 does not own the table; it only maps the port."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pivot.auth.ports import UserAccount
from pivot.db.models import User


def to_account(user: User) -> UserAccount:
    return UserAccount(
        id=user.id,
        username=user.username,
        password_hash=user.password_hash,
        role=user.role,
        status=user.status,
        token_version=user.token_version,
    )


def apply_account(user: User, account: UserAccount) -> None:
    user.username = account.username
    user.password_hash = account.password_hash
    user.role = account.role
    user.status = account.status
    user.token_version = account.token_version


class SqlAlchemyUserDirectory:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: str) -> UserAccount | None:
        row = self._session.get(User, user_id)
        return to_account(row) if row is not None else None

    def get_by_username(self, username: str) -> UserAccount | None:
        row = self._session.scalars(select(User).where(User.username == username)).one_or_none()
        return to_account(row) if row is not None else None

    def save(self, user: UserAccount) -> None:
        row = self._session.get(User, user.id)
        if row is None:
            self._session.add(
                User(
                    id=user.id,
                    username=user.username,
                    password_hash=user.password_hash,
                    role=user.role,
                    status=user.status,
                    token_version=user.token_version,
                )
            )
            return
        apply_account(row, user)

    def list(self) -> tuple[UserAccount, ...]:
        rows = self._session.scalars(select(User)).all()
        return tuple(to_account(row) for row in rows)
