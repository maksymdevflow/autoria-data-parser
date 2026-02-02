from typing import List, Optional
from sqlalchemy import (
    Integer,
    DateTime,
    JSON,
    Boolean,
    String,
    Text,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import TypeDecorator
from datetime import datetime
from enum import Enum
from database.db import Base


class StatusProcessed(Enum):
    DELETED = "deleted"
    CREATED = "created"
    UPDATED = "updated"
    NOT_PROCESSED = "not_processed"
    ACTIVE = "active"
    PROCESS = "process"  # в процесі відправки на TruckMarket
    FAILED = "failed"  # не вдалося спарсити — відправити в links_to_delete


class StatusProcessedType(TypeDecorator):
    """БД statusprocessed: всі значення в lowercase."""

    impl = postgresql.ENUM(
        "deleted", "created", "updated", "not_processed", "active", "process", "failed",
        name="statusprocessed"
    )
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, StatusProcessed):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        s = (value or "").strip().lower()
        if s == "process":
            return StatusProcessed.PROCESS
        if s == "failed":
            return StatusProcessed.FAILED
        if s == "deleted":
            return StatusProcessed.DELETED
        if s == "created":
            return StatusProcessed.CREATED
        if s == "updated":
            return StatusProcessed.UPDATED
        if s == "not_processed":
            return StatusProcessed.NOT_PROCESSED
        if s == "active":
            return StatusProcessed.ACTIVE
        return None


class StatusLinkChange(Enum):
    PROCESS = "process"
    COMPLETED = "completed"


class StatusLinkChangeType(TypeDecorator):
    """БД statuslinkchange: значення зберігаються як lowercase (process, completed) для збігу з PostgreSQL enum."""

    impl = postgresql.ENUM("process", "completed", name="statuslinkchange")
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, StatusLinkChange):
            return value.value  # 'process' або 'completed'
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        s = (value or "").strip().lower()
        if s == "process":
            return StatusLinkChange.PROCESS
        if s == "completed":
            return StatusLinkChange.COMPLETED
        return None


class LinkParseStatus(Enum):
    """Статус парсингу лінка: ще не парсили / вже спарсили."""

    PENDING = "pending"
    PARSED = "parsed"


class LinkParseStatusType(TypeDecorator):
    """БД очікує 'pending'/'parsed' (lowercase). При записі завжди відправляємо lowercase; при читанні приймаємо обидва регістри."""

    impl = postgresql.ENUM("pending", "parsed", name="linkparsestatus")
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, LinkParseStatus):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, LinkParseStatus):
            return value
        s = (value or "").strip().lower()
        if s == "parsed":
            return LinkParseStatus.PARSED
        return LinkParseStatus.PENDING


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    link: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    car_type: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # 3-5 тон, 5-15 тон, Тягач + (категорія від користувача)
    owner: Mapped[Optional[str]] = mapped_column(String(255))  # Власник (текст)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_recheck_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )  # Остання планова перевірка to_create/to_delete (понеділок)
    parse_status: Mapped[LinkParseStatus] = mapped_column(
        LinkParseStatusType(), nullable=False, default=LinkParseStatus.PENDING
    )

    cars: Mapped[List["Car"]] = relationship(
        back_populates="link", cascade="all, delete-orphan"
    )

    # Дочірні таблиці для відстеження змін по лінках
    links_to_delete: Mapped[List["LinkToDelete"]] = relationship(
        "LinkToDelete",
        back_populates="parent_link",
        cascade="all, delete-orphan",
    )
    links_to_create: Mapped[List["LinkToCreate"]] = relationship(
        "LinkToCreate",
        back_populates="parent_link",
        cascade="all, delete-orphan",
    )


class LinkToDelete(Base):
    __tablename__ = "links_to_delete"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), nullable=False)
    parent_link: Mapped["Link"] = relationship(back_populates="links_to_delete")
    link: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[StatusLinkChange] = mapped_column(
        StatusLinkChangeType(), nullable=False, default=StatusLinkChange.PROCESS
    )


class LinkToCreate(Base):
    __tablename__ = "links_to_create"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), nullable=False)
    parent_link: Mapped["Link"] = relationship(back_populates="links_to_create")
    link: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[StatusLinkChange] = mapped_column(
        StatusLinkChangeType(), nullable=False, default=StatusLinkChange.PROCESS
    )


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True)

    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), nullable=False)
    link: Mapped["Link"] = relationship(back_populates="cars")
    link_path: Mapped[str] = mapped_column(String(150), nullable=False)
    brand: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # Модель авто (наприклад "TGL")
    fuel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    transmission: Mapped[str] = mapped_column(String(50), nullable=False)

    price: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    mileage: Mapped[int] = mapped_column(Integer, nullable=False)

    color: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    path_to_images: Mapped[Optional[str]] = mapped_column(
        String(255)
    )  # Шлях до папки з обробленими зображеннями
    truck_car_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # ID оголошення в TruckMarket

    car_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    full_description: Mapped[Optional[str]] = mapped_column(
        Text
    )  # Детальний опис з //*[@id="col"]/div[6]/div/span/text()

    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_status: Mapped[StatusProcessed] = mapped_column(
        StatusProcessedType(), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ProcessRun(Base):
    """Моніторинг запусків процесів (Celery-таски): зберігається в БД, відображається в веб-адмінці."""
    __tablename__ = "process_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Історія логів під час виконання: список {t, level, msg}
    logs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
