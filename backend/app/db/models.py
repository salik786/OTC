import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Product(Base):
    """A physical OTC product the corpus can hold leaflets for, e.g. paracetamol, multivitamin."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String)

    documents: Mapped[list["Document"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class Document(Base):
    """One uploaded leaflet. Only one Document per product may be `active` at a time -
    re-ingest replaces the active document rather than appending duplicates."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    filename: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["Product"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """A retrievable unit of leaflet text. `vector_index` is the row position in the FAISS index
    at the time it was last rebuilt - the index is always rebuilt fully from Chunk rows, so this
    stays consistent (see rag/vectorstore.py)."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    section_label: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(Text)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class SessionRecord(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    participant_id: Mapped[str] = mapped_column(String)
    platform: Mapped[str] = mapped_column(String)
    condition: Mapped[str] = mapped_column(String, default="tablet_ai")
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    device_info: Mapped[dict] = mapped_column(JSON, default=dict)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_turns: Mapped[int] = mapped_column(Integer, default=0)
    errors_logged: Mapped[int] = mapped_column(Integer, default=0)

    turns: Mapped[list["Turn"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), index=True)
    turn_number: Mapped[int] = mapped_column(Integer)
    input_method: Mapped[str] = mapped_column(String)  # voice | typed
    query_text: Mapped[str] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    response_text: Mapped[str] = mapped_column(Text)
    in_scope: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["SessionRecord"] = relationship(back_populates="turns")
