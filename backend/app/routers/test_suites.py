import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.test_suite import TestSuite
from app.models.test_case import TestCase
from app.schemas.test_suite import (
    CreateTestSuiteRequest,
    UpdateTestSuiteRequest,
    TestSuiteResponse,
    TestSuiteDetailResponse,
)

router = APIRouter(prefix="/test-suites", tags=["Test Suites"])


def _suite_response_dict(suite: TestSuite) -> dict:
    """Build response dict from a TestSuite, excluding login_password."""
    d = {c.name: getattr(suite, c.name) for c in suite.__table__.columns}
    d.pop("login_password", None)
    d["has_auth"] = bool(suite.login_url and suite.login_username)
    return d


@router.post("", response_model=TestSuiteResponse, status_code=status.HTTP_201_CREATED)
async def create_test_suite(
    request: CreateTestSuiteRequest,
    db: AsyncSession = Depends(get_db),
):
    suite = TestSuite(**request.model_dump())
    db.add(suite)
    await db.flush()
    await db.refresh(suite)
    return TestSuiteResponse(
        **_suite_response_dict(suite),
        test_case_count=0,
    )


@router.get("", response_model=list[TestSuiteResponse])
async def list_test_suites(
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            TestSuite,
            sa_func.count(TestCase.id).label("test_case_count"),
        )
        .outerjoin(TestCase, TestSuite.id == TestCase.suite_id)
        .group_by(TestSuite.id)
        .order_by(TestSuite.created_at.desc())
    )
    results = await db.execute(stmt)
    return [
        TestSuiteResponse(
            **_suite_response_dict(suite),
            test_case_count=count,
        )
        for suite, count in results.all()
    ]


@router.get("/{suite_id}", response_model=TestSuiteDetailResponse)
async def get_test_suite(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TestSuite)
        .where(TestSuite.id == suite_id)
        .options(selectinload(TestSuite.test_cases))
    )
    result = await db.execute(stmt)
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return TestSuiteDetailResponse(
        **_suite_response_dict(suite),
        test_case_count=len(suite.test_cases),
        test_cases=suite.test_cases,
    )


@router.patch("/{suite_id}", response_model=TestSuiteResponse)
async def update_test_suite(
    suite_id: uuid.UUID,
    request: UpdateTestSuiteRequest,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TestSuite).where(TestSuite.id == suite_id)
    result = await db.execute(stmt)
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(suite, key, value)

    await db.flush()
    await db.refresh(suite)

    # Count cases
    count_stmt = select(sa_func.count(TestCase.id)).where(TestCase.suite_id == suite_id)
    count_result = await db.execute(count_stmt)
    case_count = count_result.scalar() or 0

    return TestSuiteResponse(
        **_suite_response_dict(suite),
        test_case_count=case_count,
    )


@router.delete("/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_suite(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TestSuite).where(TestSuite.id == suite_id)
    result = await db.execute(stmt)
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    await db.delete(suite)
