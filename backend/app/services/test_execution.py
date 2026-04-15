"""
Test Execution Service.

Orchestrates Playwright test execution using the step executor:
- Fetches TestStep objects from DB
- Executes steps directly via playwright-python (no subprocess/npm)
- Broadcasts step-by-step progress via WebSocket
- Collects artifacts and updates DB records
"""

import logging
import os
import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session
from app.models.artifact import Artifact
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.test_step import TestStep
from app.models.test_suite import TestSuite
from app.services.artifact_manager import (
    collect_artifacts,
    get_artifact_dir,
    save_log_artifact,
)
from app.services.step_executor import execute_steps, StepResult
from app.services.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

settings = get_settings()


async def _get_run_context(
    run_id: uuid.UUID, db: AsyncSession
) -> tuple[TestRun, list[TestStep], str]:
    """
    Fetch the TestRun, its ordered TestSteps, and the suite's base_url.
    """
    run_result = await db.execute(
        select(TestRun).where(TestRun.id == run_id)
    )
    run = run_result.scalar_one_or_none()
    if not run:
        raise ValueError(f"Test run not found: {run_id}")

    # Fetch test case
    case_result = await db.execute(
        select(TestCase).where(TestCase.id == run.case_id)
    )
    test_case = case_result.scalar_one_or_none()
    if not test_case:
        raise ValueError(f"Test case not found: {run.case_id}")

    # Fetch suite for base_url
    suite_result = await db.execute(
        select(TestSuite).where(TestSuite.id == test_case.suite_id)
    )
    suite = suite_result.scalar_one_or_none()
    if not suite:
        raise ValueError(f"Test suite not found for case: {run.case_id}")

    # Fetch steps ordered by .order
    steps_result = await db.execute(
        select(TestStep)
        .where(TestStep.case_id == run.case_id)
        .order_by(TestStep.order)
    )
    steps = list(steps_result.scalars().all())
    if not steps:
        raise ValueError(f"No test steps found for case: {run.case_id}")

    return run, steps, suite.base_url


async def execute_test_run(run_id: uuid.UUID):
    """
    Execute a test run in the background.

    1. Fetch the run, steps, and suite context from DB
    2. Execute steps directly via playwright-python
    3. Broadcast step-by-step progress via WebSocket
    4. Collect artifacts and update DB record
    """
    run_id_str = str(run_id)

    async with async_session() as db:
        try:
            # --- Fetch context ---
            run, steps, base_url = await _get_run_context(run_id, db)

            # --- Mark as running ---
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            await ws_manager.broadcast(run_id_str, {
                "event": "status_change",
                "status": "running",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            await ws_manager.broadcast(run_id_str, {
                "event": "test_step",
                "step": f"Loaded {len(steps)} test steps",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            await ws_manager.broadcast(run_id_str, {
                "event": "test_step",
                "step": f"Starting Playwright ({run.browser}, {'headed' if run.headed else 'headless'})...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # --- Step progress callback ---
            async def on_step_complete(step_result: StepResult):
                status_icon = "✓" if step_result.status == "passed" else "✗"
                msg = (
                    f"{status_icon} Step {step_result.order}: "
                    f"{step_result.action}"
                )
                if step_result.description:
                    msg += f" — {step_result.description}"
                if step_result.status == "failed" and step_result.error_message:
                    msg += f"\n  Error: {step_result.error_message[:200]}"

                event_data: dict = {
                    "event": "test_step",
                    "step": msg,
                    "status": step_result.status,
                    "order": step_result.order,
                    "action": step_result.action,
                    "value": step_result.value,
                    "duration_ms": step_result.duration_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Include live screenshot as base64 data URI
                screenshot_b64 = getattr(step_result, "screenshot_base64", None)
                if screenshot_b64:
                    event_data["screenshot_base64"] = (
                        f"data:image/png;base64,{screenshot_b64}"
                    )

                await ws_manager.broadcast(run_id_str, event_data)

            # --- Execute via step executor ---
            exec_result = await execute_steps(
                steps=steps,
                browser_name=run.browser,
                base_url=base_url,
                run_id=run_id_str,
                headed=run.headed,
                on_step_complete=on_step_complete,
            )

            # --- Collect artifacts ---
            artifact_dir = get_artifact_dir(run_id_str)
            artifacts = await collect_artifacts(run_id, artifact_dir, db)

            # Save execution log
            log_lines = []
            for sr in exec_result.step_results:
                icon = "PASS" if sr.status == "passed" else "FAIL"
                log_lines.append(
                    f"[{icon}] Step {sr.order} ({sr.action}): "
                    f"{sr.description or ''} [{sr.duration_ms}ms]"
                )
                if sr.error_message:
                    log_lines.append(f"  Error: {sr.error_message}")
            await save_log_artifact(
                run_id, "\n".join(log_lines), "execution.log", db
            )

            # --- Update run record ---
            run_result2 = await db.execute(
                select(TestRun).where(TestRun.id == run_id)
            )
            run = run_result2.scalar_one_or_none()
            if run:
                run.status = exec_result.status
                run.completed_at = datetime.now(timezone.utc)
                run.duration_ms = exec_result.duration_ms
                run.result_summary = {
                    "total": exec_result.total,
                    "passed": exec_result.passed,
                    "failed": exec_result.failed,
                    "skipped": exec_result.skipped,
                    "duration": exec_result.duration_ms,
                }
                if exec_result.status == "failed":
                    run.error_message = (
                        exec_result.error_message or "Test failed"
                    )[:5000]

            await db.commit()

            # --- Broadcast completion ---
            await ws_manager.broadcast(run_id_str, {
                "event": "status_change",
                "status": exec_result.status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Broadcast artifact-ready events
            for artifact in artifacts:
                await ws_manager.broadcast(run_id_str, {
                    "event": "artifact_ready",
                    "artifact": {
                        "id": str(artifact.id),
                        "artifact_type": artifact.artifact_type,
                        "file_name": artifact.file_name,
                        "mime_type": artifact.mime_type,
                        "file_size": artifact.file_size,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            logger.info(
                "Test run %s completed: %s (%dms) — %d/%d passed",
                run_id,
                exec_result.status,
                exec_result.duration_ms,
                exec_result.passed,
                exec_result.total,
            )

            # Signal all WebSocket handlers to close now that the run is finished
            ws_manager.close_all(run_id_str)

        except Exception as e:
            tb = traceback.format_exc()
            error_msg = f"{str(e) or repr(e)}\n\n{tb}"[:5000]
            logger.error(
                "Test execution failed for run %s: %s\n%s", run_id, e, tb
            )

            try:
                await db.rollback()
            except Exception:
                pass

            # Persist error status in a fresh session
            try:
                async with async_session() as err_db:
                    err_run_result = await err_db.execute(
                        select(TestRun).where(TestRun.id == run_id)
                    )
                    err_run = err_run_result.scalar_one_or_none()
                    if err_run:
                        err_run.status = "error"
                        err_run.completed_at = datetime.now(timezone.utc)
                        err_run.error_message = error_msg or "Unknown error"
                        if err_run.started_at:
                            err_run.duration_ms = int(
                                (err_run.completed_at - err_run.started_at).total_seconds()
                                * 1000
                            )
                    await err_db.commit()
            except Exception:
                logger.error(
                    "Failed to update run status: %s", traceback.format_exc()
                )

            await ws_manager.broadcast(run_id_str, {
                "event": "status_change",
                "status": "error",
                "error_message": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Signal all WebSocket handlers to close now that the run has errored
            ws_manager.close_all(run_id_str)
