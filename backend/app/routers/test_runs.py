import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.artifact import Artifact
from app.models.test_run import TestRun
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.schemas.test_run import (
    CreateTestRunRequest,
    TestRunResponse,
    TestRunDetailResponse,
)
from app.services.test_execution import execute_test_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test-runs", tags=["Test Runs"])


@router.post("", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
async def create_test_run(
    request: CreateTestRunRequest,
    db: AsyncSession = Depends(get_db),
):
    # Verify test case exists
    case_stmt = select(TestCase).where(TestCase.id == request.case_id)
    case_result = await db.execute(case_stmt)
    if not case_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test case not found")

    run = TestRun(**request.model_dump())
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Trigger test execution in background
    asyncio.create_task(execute_test_run(run.id))

    return run


@router.get("", response_model=list[TestRunResponse])
async def list_test_runs(
    case_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TestRun).order_by(TestRun.created_at.desc())
    if case_id:
        stmt = stmt.where(TestRun.case_id == case_id)
    if status_filter:
        stmt = stmt.where(TestRun.status == status_filter)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{run_id}", response_model=TestRunDetailResponse)
async def get_test_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TestRun)
        .where(TestRun.id == run_id)
        .options(selectinload(TestRun.artifacts))
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Fetch suite base_url via case → suite
    base_url: str | None = None
    case_res = await db.execute(select(TestCase).where(TestCase.id == run.case_id))
    tc = case_res.scalar_one_or_none()
    if tc:
        suite_res = await db.execute(select(TestSuite).where(TestSuite.id == tc.suite_id))
        suite = suite_res.scalar_one_or_none()
        if suite:
            base_url = suite.base_url

    resp = TestRunDetailResponse.model_validate(run)
    resp.base_url = base_url
    return resp


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TestRun).where(TestRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    await db.delete(run)
    await db.commit()


@router.get("/{run_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    run_id: uuid.UUID,
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download an artifact file."""
    stmt = select(Artifact).where(
        Artifact.id == artifact_id,
        Artifact.run_id == run_id,
    )
    result = await db.execute(stmt)
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if not os.path.isfile(artifact.file_path):
        raise HTTPException(status_code=404, detail="Artifact file not found on disk")

    return FileResponse(
        path=artifact.file_path,
        filename=artifact.file_name,
        media_type=artifact.mime_type or "application/octet-stream",
    )
