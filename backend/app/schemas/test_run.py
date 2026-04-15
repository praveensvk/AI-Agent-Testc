import uuid
from datetime import datetime
from pydantic import BaseModel, Field


# --- Request Schemas ---

class CreateTestRunRequest(BaseModel):
    case_id: uuid.UUID
    browser: str = Field(default="chromium", pattern="^(chromium|firefox|webkit)$")
    headed: bool = False


# --- Response Schemas ---

class ArtifactResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    artifact_type: str
    file_name: str
    mime_type: str | None
    file_size: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TestRunResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    status: str
    browser: str
    headed: bool
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TestRunDetailResponse(TestRunResponse):
    result_summary: dict | None = None
    artifacts: list[ArtifactResponse] = []
    base_url: str | None = None


class RunStatusUpdate(BaseModel):
    event: str  # status_change, test_step, artifact_ready
    status: str | None = None
    step: str | None = None
    screenshot_url: str | None = None
    artifact: ArtifactResponse | None = None
    timestamp: datetime
