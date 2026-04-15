import uuid
from datetime import datetime
from pydantic import BaseModel, Field


# --- Request Schemas ---

TEST_TYPES = ["functional", "e2e", "integration", "accessibility", "visual", "performance"]


class CreateTestCaseRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    test_type: str = Field(default="functional", pattern="^(functional|e2e|integration|accessibility|visual|performance)$")


class UpdateTestStepRequest(BaseModel):
    order: int
    action: str = Field(..., min_length=1)
    selector: str | None = None
    value: str | None = None
    expected_result: str | None = None
    description: str | None = None


class UpdateTestStepsRequest(BaseModel):
    steps: list[UpdateTestStepRequest]


# --- Response Schemas ---

class TestStepResponse(BaseModel):
    id: uuid.UUID
    order: int
    action: str
    selector: str | None
    value: str | None
    expected_result: str | None
    description: str | None

    model_config = {"from_attributes": True}


class TestCaseResponse(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    title: str
    description: str
    test_type: str
    status: str
    generation_attempts: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestCaseDetailResponse(TestCaseResponse):
    test_steps: list[TestStepResponse] = []
