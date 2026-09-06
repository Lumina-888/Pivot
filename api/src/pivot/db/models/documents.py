"""Document, version, chunk and index-generation facts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pivot.db.base import Base
from pivot.shared.time import utc_now


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    space: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    tags: Mapped[list] = mapped_column(Text, nullable=False, default="[]")
    classification: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    creator: Mapped["User"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class IndexGeneration(Base):
    __tablename__ = "index_generations"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    retrieval_config_version: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    embedding_model_version: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="building")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="index_generation")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="index_generation")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "content_sha256", name="uq_document_versions_content_sha"),
        Index(
            "uq_document_versions_one_current",
            "document_id",
            unique=True,
            postgresql_where=text("current = true"),
            sqlite_where=text("current = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    version_label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_llm_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parser_version: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    chunking_version: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    embedding_model_version: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    index_generation_id: Mapped[str | None] = mapped_column(ForeignKey("index_generations.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="versions")
    index_generation: Mapped["IndexGeneration | None"] = relationship(back_populates="versions")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    parse_errors: Mapped[list["ParseError"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "text_hash", name="uq_chunks_version_text_hash"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    title_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    locator: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_char_start: Mapped[int | None] = mapped_column(Integer)
    raw_char_end: Mapped[int | None] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    index_generation_id: Mapped[str | None] = mapped_column(ForeignKey("index_generations.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")
    index_generation: Mapped["IndexGeneration | None"] = relationship(back_populates="chunks")


if TYPE_CHECKING:
    from pivot.db.models.identity import User
    from pivot.db.models.operations import ParseError
