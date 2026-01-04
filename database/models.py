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
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from enum import Enum

from database.db import Base


class Role(Enum):
    ADMIN = "admin"
    USER = "user"
    MANAGER = "manager"


class Status(Enum):
    WAITING = "waiting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StatusPartner(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    DELETED = "deleted"


class StatusProcessed(Enum):
    DELETED = "deleted"
    CREATED = "created"
    UPDATED = "updated"
    NOT_PROCESSED = "not_processed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[Role] = mapped_column(SAEnum(Role), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)
    link: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    cars: Mapped[List["Car"]] = relationship(
        back_populates="link",
        cascade="all, delete-orphan"
    )

class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[StatusPartner] = mapped_column(
        SAEnum(StatusPartner), nullable=False
    )

    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    cars: Mapped[List["Car"]] = relationship(
        secondary="partner_cars",
        back_populates="partners",
    )

    cars_count: Mapped[int] = mapped_column(Integer, default=0)


from sqlalchemy import Table, Column

partner_cars = Table(
    "partner_cars",
    Base.metadata,
    Column("partner_id", ForeignKey("partners.id"), primary_key=True),
    Column("car_id", ForeignKey("cars.id"), primary_key=True),
)

planed_tasks_cars = Table(
    "planed_tasks_cars",
    Base.metadata,
    Column("planed_task_id", ForeignKey("planed_tasks_partners.id"), primary_key=True),
    Column("car_id", ForeignKey("cars.id"), primary_key=True),
)


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True)

    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), nullable=False)
    link: Mapped["Link"] = relationship(back_populates="cars")

    car_type: Mapped[str] = mapped_column(String(50), nullable=False)
    brand: Mapped[str] = mapped_column(String(50), nullable=False)
    fuel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    transmission: Mapped[str] = mapped_column(String(50), nullable=False)

    price: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    mileage: Mapped[int] = mapped_column(Integer, nullable=False)

    color: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[Optional[str]] = mapped_column(String(50))

    car_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_status: Mapped[StatusProcessed] = mapped_column(
        SAEnum(StatusProcessed), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    partners: Mapped[List["Partner"]] = relationship(
        secondary="partner_cars",
        back_populates="cars",
    )

    planed_tasks: Mapped[List["PlanedTask"]] = relationship(
        secondary="planed_tasks_cars",
        back_populates="processed_cars",
    )


class PlanedTask(Base):
    __tablename__ = "planed_tasks_partners"

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id"), nullable=False)

    status: Mapped[Status] = mapped_column(SAEnum(Status), nullable=False)

    planed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    started_processing_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    failed_reason: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    processed_cars: Mapped[List["Car"]] = relationship(
        secondary="planed_tasks_cars",
        back_populates="planed_tasks",
    )

    processed_cars_count: Mapped[int] = mapped_column(Integer, default=0)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    before_data: Mapped[Optional[dict]] = mapped_column(JSON)
    after_data: Mapped[Optional[dict]] = mapped_column(JSON)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
