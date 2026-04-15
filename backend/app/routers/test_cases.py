import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.test_suite import TestSuite
from app.models.test_case import TestCase
from app.models.test_step import TestStep
from app.schemas.test_case import (
    CreateTestCaseRequest,
    TestCaseResponse,
    TestCaseDetailResponse,
    UpdateTestStepsRequest,
)
from app.services.test_output import generate_and_save_test_code

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Test Cases"])


@router.post(
    "/test-suites/{suite_id}/test-cases",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    suite_id: uuid.UUID,
    request: CreateTestCaseRequest,
    db: AsyncSession = Depends(get_db),
):
    # Verify suite exists
    suite_stmt = select(TestSuite).where(TestSuite.id == suite_id)
    suite_result = await db.execute(suite_stmt)
    if not suite_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test suite not found")

    case = TestCase(suite_id=suite_id, **request.model_dump())
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return case


@router.get(
    "/test-suites/{suite_id}/test-cases",
    response_model=list[TestCaseResponse],
)
async def list_test_cases(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TestCase)
        .where(TestCase.suite_id == suite_id)
        .order_by(TestCase.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/test-cases/{case_id}",
    response_model=TestCaseDetailResponse,
)
async def get_test_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TestCase)
        .where(TestCase.id == case_id)
        .options(selectinload(TestCase.test_steps))
    )
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    return case


@router.delete(
    "/test-cases/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TestCase).where(TestCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    await db.delete(case)


@router.put(
    "/test-cases/{case_id}/steps",
    response_model=TestCaseDetailResponse,
)
async def update_test_steps(
    case_id: uuid.UUID,
    request: UpdateTestStepsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Replace all test steps for a case and regenerate the .spec.ts file.
    """
    # Verify case exists
    case_stmt = (
        select(TestCase)
        .where(TestCase.id == case_id)
        .options(selectinload(TestCase.test_steps))
    )
    case_result = await db.execute(case_stmt)
    case = case_result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")

    # Delete existing steps
    await db.execute(
        sa_delete(TestStep).where(TestStep.case_id == case_id)
    )

    # Insert new steps
    for step_data in request.steps:
        db.add(TestStep(
            case_id=case_id,
            order=step_data.order,
            action=step_data.action,
            selector=step_data.selector,
            value=step_data.value,
            expected_result=step_data.expected_result,
            description=step_data.description,
        ))

    await db.flush()

    # Regenerate the .spec.ts file
    try:
        code_result = await generate_and_save_test_code(case_id, db)
        logger.info("Regenerated test script: %s", code_result.get("file_name"))
    except Exception as e:
        logger.warning("Script regeneration failed (steps still saved): %s", e)

    # Refresh and return
    await db.commit()
    refreshed = await db.execute(
        select(TestCase)
        .where(TestCase.id == case_id)
        .options(selectinload(TestCase.test_steps))
    )
    return refreshed.scalar_one()
