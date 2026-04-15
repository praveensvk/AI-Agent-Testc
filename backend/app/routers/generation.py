import uuid
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models.test_case import TestCase
from app.schemas.test_case import TestCaseDetailResponse
from app.services.test_generation import generate_test_case_steps
from app.services.test_output import generate_and_save_test_code, get_test_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test-cases", tags=["Generation"])

# In-memory store for generation progress (per case_id)
_generation_progress: dict[str, dict] = {}


async def _run_generation_background(case_id: uuid.UUID):
    """Background task that runs the generation workflow."""
    case_id_str = str(case_id)
    _generation_progress[case_id_str] = {
        "status": "running",
        "progress": ["Generation started..."],
        "error": None,
    }

    async def _progress_callback(messages: list[str]):
        """Update in-memory progress as each workflow node completes."""
        current = _generation_progress.get(case_id_str, {})
        existing = current.get("progress", [])
        # Merge new messages that aren't already tracked
        for msg in messages:
            if msg not in existing:
                existing.append(msg)
        _generation_progress[case_id_str] = {
            **current,
            "status": "running",
            "progress": existing,
        }

    try:
        async with async_session() as db:
            try:
                result = await generate_test_case_steps(
                    case_id, db, progress_callback=_progress_callback,
                )
                await db.commit()

                _generation_progress[case_id_str] = {
                    "status": result["status"],
                    "progress": result.get("progress", []),
                    "error": result.get("error"),
                    "steps_count": result.get("steps_count", 0),
                    "code_generated": result.get("code_generated", False),
                    "code_file": result.get("code_file"),
                }
            except Exception as e:
                await db.rollback()
                logger.error("Generation background task failed: %s", str(e))
                # Update case status to failed
                try:
                    stmt = select(TestCase).where(TestCase.id == case_id)
                    res = await db.execute(stmt)
                    case = res.scalar_one_or_none()
                    if case:
                        case.status = "failed"
                        await db.commit()
                except Exception:
                    await db.rollback()

                _generation_progress[case_id_str] = {
                    "status": "failed",
                    "progress": _generation_progress.get(case_id_str, {}).get("progress", []) + [f"Generation failed: {str(e)}"],
                    "error": str(e),
                }
    except Exception as e:
        logger.error("Background session creation failed: %s", str(e))
        _generation_progress[case_id_str] = {
            "status": "failed",
            "progress": [f"Internal error: {str(e)}"],
            "error": str(e),
        }


@router.post("/{case_id}/generate")
async def trigger_generation(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TestCase).where(TestCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")

    if case.status == "generating":
        raise HTTPException(status_code=409, detail="Generation already in progress")

    case.status = "generating"
    case.generation_attempts += 1
    await db.flush()
    await db.commit()

    # Use asyncio.create_task so it runs concurrently in the event loop
    # (BackgroundTasks runs after response but can delay connection cleanup)
    asyncio.create_task(_run_generation_background(case_id))

    return {
        "message": "Generation triggered",
        "case_id": str(case_id),
        "status": "generating",
        "attempt": case.generation_attempts,
    }


@router.get("/{case_id}/generate/status")
async def get_generation_status(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the current generation status for a test case."""
    # Check if case exists
    stmt = select(TestCase).where(TestCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")

    case_id_str = str(case_id)
    progress = _generation_progress.get(case_id_str)

    return {
        "case_id": case_id_str,
        "case_status": case.status,
        "generation": progress,
    }


@router.get("/{case_id}/code")
async def get_generated_code(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the generated Playwright test code for a test case."""
    code = await get_test_code(case_id, db)
    if not code:
        raise HTTPException(
            status_code=404,
            detail="No generated test code found for this case. Generate steps first.",
        )
    return code


@router.post("/{case_id}/code/generate")
async def trigger_code_generation(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Re-generate Playwright test code from existing test steps.
    Useful when steps have been manually edited and code needs to be refreshed.
    """
    stmt = select(TestCase).where(TestCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")

    if case.status not in ("generated", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Test case must have generated steps first (current status: {case.status})",
        )

    try:
        code_result = await generate_and_save_test_code(case_id, db)
        await db.commit()
        return {
            "message": "Test code generated successfully",
            "case_id": str(case_id),
            **code_result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Code generation failed for case %s: %s", case_id, str(e))
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")
