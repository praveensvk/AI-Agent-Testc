import uuid
from datetime import datetime
from pydantic import BaseModel, Field


# --- Request Schemas ---

class CreateTestSuiteRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    base_url: str = Field(..., min_length=1, max_length=2048)
    app_description: str | None = None
    login_url: str | None = Field(None, max_length=2048)
    login_username: str | None = Field(None, max_length=255)
    login_password: str | None = Field(None, max_length=255)


class UpdateTestSuiteRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    base_url: str | None = Field(None, min_length=1, max_length=2048)
    app_description: str | None = None
    login_url: str | None = Field(None, max_length=2048)
    login_username: str | None = Field(None, max_length=255)
    login_password: str | None = Field(None, max_length=255)


# --- Response Schemas ---

class TestSuiteResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    base_url: str
    app_description: str | None
    login_url: str | None = None
    login_username: str | None = None
    has_auth: bool = False
    created_at: datetime
    updated_at: datetime
    test_case_count: int = 0

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_count(cls, suite, test_case_count: int = 0):
        data = {
            "id": suite.id,
            "name": suite.name,
            "description": suite.description,
            "base_url": suite.base_url,
            "app_description": suite.app_description,
            "login_url": suite.login_url,
            "login_username": suite.login_username,
            "has_auth": bool(suite.login_url and suite.login_username),
            "created_at": suite.created_at,
            "updated_at": suite.updated_at,
            "test_case_count": test_case_count,
        }
        return cls(**data)


class TestSuiteDetailResponse(TestSuiteResponse):
    test_cases: list["TestCaseResponse"] = []


# Forward reference resolved below
from app.schemas.test_case import TestCaseResponse  # noqa: E402

TestSuiteDetailResponse.model_rebuild()
