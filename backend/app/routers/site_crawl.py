"""
Site Crawl Router.

Endpoints:
  POST /test-suites/{suite_id}/crawl          — trigger site-wide crawl (background)
  GET  /test-suites/{suite_id}/crawl/status   — in-memory progress
  GET  /test-suites/{suite_id}/crawl/results  — manifest.json summary
  GET  /test-suites/{suite_id}/crawl/pages/{index} — full element data for one page
"""

import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models.test_suite import TestSuite
from app.services.site_crawl import crawl_suite_site, get_crawl_manifest, get_crawl_page
from app.services.ws_manager import manager as ws_manager
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/test-suites", tags=["Site Crawl"])

# In-memory store: suite_id_str → progress dict
_crawl_progress: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

async def _run_crawl_background(suite_id: str) -> None:
    """Background task that runs the site crawl and broadcasts progress via WS."""

    async def _ws_broadcast(sid: str, event: dict) -> None:
        await ws_manager.broadcast(sid, event)

    try:
        async with async_session() as db:
            try:
                result = await crawl_suite_site(suite_id, db, _ws_broadcast)
                await db.commit()
                _crawl_progress[suite_id] = {
                    "status": "completed",
                    "total_pages": result["total_pages"],
                    "total_elements": result["total_elements"],
                    "error": None,
                }
                ws_manager.close_all(suite_id)
            except Exception as e:
                await db.rollback()
                logger.error("Crawl background task failed for suite %s: %s", suite_id, e)
                error_msg = str(e) or repr(e)
                _crawl_progress[suite_id] = {
                    "status": "failed",
                    "error": error_msg,
                }
                # Broadcast error to WS clients
                await ws_manager.broadcast(suite_id, {"event": "crawl_error", "error": error_msg})
                ws_manager.close_all(suite_id)
    except Exception as e:
        logger.error("Crawl session creation failed: %s", e)
        _crawl_progress[suite_id] = {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{suite_id}/crawl", status_code=202)
async def trigger_crawl(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a site-wide BFS crawl for the test suite. Returns 409 if already running."""
    suite_id_str = str(suite_id)

    # Check suite exists
    stmt = select(TestSuite).where(TestSuite.id == suite_id)
    result = await db.execute(stmt)
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")

    # Prevent duplicate crawls
    existing = _crawl_progress.get(suite_id_str, {})
    if existing.get("status") == "running":
        raise HTTPException(status_code=409, detail="Crawl already in progress for this suite")

    # Delete stale manifest so the status endpoint doesn't serve old data during the new run
    manifest_path = os.path.join(
        os.path.abspath(settings.artifacts_dir), suite_id_str, "crawl", "manifest.json"
    )
    if os.path.exists(manifest_path):
        try:
            os.remove(manifest_path)
        except Exception:
            pass

    # Mark as running and fire background task
    _crawl_progress[suite_id_str] = {"status": "running", "error": None}
    asyncio.create_task(_run_crawl_background(suite_id_str))

    return {"status": "started", "suite_id": suite_id_str}


@router.get("/{suite_id}/crawl/status")
async def get_crawl_status(suite_id: uuid.UUID):
    """Return in-memory crawl progress for the suite."""
    suite_id_str = str(suite_id)
    progress = _crawl_progress.get(suite_id_str)
    if progress is None:
        # Check if results already exist on disk (from a previous run)
        manifest = get_crawl_manifest(suite_id_str)
        if manifest:
            return {
                "status": "completed",
                "total_pages": manifest.get("total_pages", 0),
                "total_elements": manifest.get("total_elements", 0),
                "crawled_at": manifest.get("crawled_at"),
                "error": None,
            }
        return {"status": "idle", "error": None}
    return progress


@router.get("/{suite_id}/crawl/results")
async def get_crawl_results(suite_id: uuid.UUID):
    """Return the crawl manifest summary (list of crawled pages with metadata)."""
    suite_id_str = str(suite_id)
    manifest = get_crawl_manifest(suite_id_str)
    if not manifest:
        raise HTTPException(status_code=404, detail="No crawl results found. Run a crawl first.")
    return manifest


@router.get("/{suite_id}/crawl/pages/{page_index}")
async def get_crawl_page_detail(suite_id: uuid.UUID, page_index: int):
    """Return the full element/form data for a specific crawled page by its 0-based index."""
    suite_id_str = str(suite_id)
    page_data = get_crawl_page(suite_id_str, page_index)
    if not page_data:
        raise HTTPException(status_code=404, detail=f"Page index {page_index} not found in crawl results")
    return page_data
