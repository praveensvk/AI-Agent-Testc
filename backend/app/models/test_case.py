import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    test_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="functional"
    )  # functional, e2e, integration, accessibility, visual, performance
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft"
    )  # draft, generating, generated, failed
    generation_attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    test_suite: Mapped["TestSuite"] = relationship("TestSuite", back_populates="test_cases")
    test_steps: Mapped[list["TestStep"]] = relationship(
        "TestStep", back_populates="test_case", cascade="all, delete-orphan",
        order_by="TestStep.order"
    )
    test_runs: Mapped[list["TestRun"]] = relationship(
        "TestRun", back_populates="test_case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TestCase(id={self.id}, title='{self.title}', status='{self.status}')>"
