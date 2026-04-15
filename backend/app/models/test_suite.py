import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TestSuite(Base):
    __tablename__ = "test_suites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    app_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Authentication (optional – for crawling login-protected sites)
    login_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    login_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    login_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    test_cases: Mapped[list["TestCase"]] = relationship(
        "TestCase", back_populates="test_suite", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TestSuite(id={self.id}, name='{self.name}')>"
