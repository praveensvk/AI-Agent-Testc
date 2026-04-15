"""
Site Crawl Service.

Orchestrates a site-wide BFS crawl for a TestSuite:
- Fetches suite auth credentials from DB
- Runs crawl_site() with live WebSocket progress broadcasts
- Saves per-page JSON files + manifest.json to artifacts/{suite_id}/crawl/
- Provides load_crawl_snapshots() for the workflow to consume cached data
"""

import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.test_suite import TestSuite
from app.schemas.agent import PageSnapshot
from app.services.crawler import crawl_site

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _crawl_dir(suite_id: str) -> str:
    """Return (and create) the crawl artifact directory for a suite."""
    path = os.path.join(os.path.abspath(settings.artifacts_dir), suite_id, "crawl")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_filename(url: str) -> str:
    """Convert a URL to a safe filename (without extension)."""
    # Remove scheme and replace non-alphanumeric with _
    name = re.sub(r"https?://", "", url)
    name = re.sub(r"[^\w\-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:100] or "page"


# ---------------------------------------------------------------------------
# Crawl orchestration
# ---------------------------------------------------------------------------

async def crawl_suite_site(
    suite_id: str,
    db: AsyncSession,
    ws_broadcast,  # async callable(suite_id, message_dict)
) -> dict:
    """
    Run a site-wide crawl for the given suite.

    1. Fetch TestSuite from DB (base_url + auth creds)
    2. Call crawl_site() with a progress callback that broadcasts each event via WS
    3. Save per-page JSON files + manifest.json
    4. Return summary dict
    """
    # Fetch suite
    stmt = select(TestSuite).where(TestSuite.id == uuid.UUID(suite_id))
    result = await db.execute(stmt)
    suite = result.scalar_one_or_none()
    if not suite:
        raise ValueError(f"Test suite not found: {suite_id}")

    crawl_dir = _crawl_dir(suite_id)
    pages_crawled: list[dict] = []
    start_time = datetime.now(timezone.utc)
    # Map url → saved screenshot filename (populated in _progress_callback)
    _screenshot_files: dict[str, str] = {}

    async def _progress_callback(event: dict) -> None:
        """Broadcast event over WebSocket and persist per-page data."""
        event_type = event.get("event")

        if event_type == "crawl_page":
            url = event.get("url", "")
            filename = _safe_filename(url) + ".json"

            # Persist screenshot to disk if provided
            screenshot_file: str | None = None
            screenshot_b64 = event.get("screenshot_base64")
            if screenshot_b64:
                try:
                    img_data = screenshot_b64.split(",", 1)[-1] if "," in screenshot_b64 else screenshot_b64
                    screenshot_filename = _safe_filename(url) + ".png"
                    screenshot_path = os.path.join(crawl_dir, screenshot_filename)
                    with open(screenshot_path, "wb") as f_img:
                        f_img.write(base64.b64decode(img_data))
                    screenshot_file = screenshot_filename
                    _screenshot_files[url] = screenshot_filename
                except Exception as ss_err:
                    logger.warning("Failed to save screenshot for %s: %s", url, ss_err)

            pages_crawled.append({
                "url": url,
                "page_title": event.get("page_title"),
                "element_count": event.get("element_count", 0),
                "form_count": event.get("form_count", 0),
                "file": filename,
                "screenshot_file": screenshot_file,
            })
            logger.info(
                "Site crawl page %d: %s (%d elements)",
                event.get("pages_done", 0), url, event.get("element_count", 0),
            )

        # Always broadcast the event
        await ws_broadcast(suite_id, event)

    # Run the BFS crawl
    snapshots = await crawl_site(
        suite.base_url,
        login_url=suite.login_url,
        login_username=suite.login_username,
        login_password=suite.login_password,
        max_pages=20,
        progress_callback=_progress_callback,
    )

    # Persist per-page JSON files
    for snap in snapshots:
        filename = _safe_filename(snap.page_url) + ".json"
        file_path = os.path.join(crawl_dir, filename)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(snap.model_dump(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save crawl JSON for %s: %s", snap.page_url, e)

    # Write manifest
    total_elements = sum(len(s.elements) for s in snapshots)
    manifest = {
        "suite_id": suite_id,
        "base_url": suite.base_url,
        "crawled_at": start_time.isoformat(),
        "total_pages": len(snapshots),
        "total_elements": total_elements,
        "pages": [
            {
                "index": i,
                "url": s.page_url,
                "page_title": s.page_title,
                "element_count": len(s.elements),
                "form_count": len(s.forms),
                "file": _safe_filename(s.page_url) + ".json",
                "screenshot_file": _screenshot_files.get(s.page_url),
            }
            for i, s in enumerate(snapshots)
        ],
    }
    manifest_path = os.path.join(crawl_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    logger.info(
        "Site crawl complete for suite %s: %d pages, %d elements",
        suite_id, len(snapshots), total_elements,
    )
    return {
        "status": "completed",
        "total_pages": len(snapshots),
        "total_elements": total_elements,
    }


# ---------------------------------------------------------------------------
# Load cached snapshots (for workflow use)
# ---------------------------------------------------------------------------

async def load_crawl_snapshots(suite_id: str) -> list[PageSnapshot]:
    """
    Load pre-crawled PageSnapshot objects from JSON files on disk.
    Returns an empty list if no crawl data exists for this suite.
    """
    crawl_dir = os.path.join(os.path.abspath(settings.artifacts_dir), suite_id, "crawl")
    manifest_path = os.path.join(crawl_dir, "manifest.json")

    if not os.path.exists(manifest_path):
        logger.debug("No crawl manifest found for suite %s — will crawl on-demand", suite_id)
        return []

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        logger.warning("Failed to read crawl manifest for suite %s: %s", suite_id, e)
        return []

    snapshots: list[PageSnapshot] = []
    for page_meta in manifest.get("pages", []):
        file_path = os.path.join(crawl_dir, page_meta.get("file", ""))
        if not os.path.exists(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # raw_html is large — drop it to save LLM tokens; elements + forms are enough
            data.pop("raw_html", None)
            snapshots.append(PageSnapshot(**data))
        except Exception as e:
            logger.warning("Failed to load crawl page %s: %s", file_path, e)

    logger.info("Loaded %d pre-crawled snapshots for suite %s", len(snapshots), suite_id)
    return snapshots


def get_crawl_manifest(suite_id: str) -> dict | None:
    """Return the manifest dict for a suite's crawl, or None if it doesn't exist."""
    crawl_dir = os.path.join(os.path.abspath(settings.artifacts_dir), suite_id, "crawl")
    manifest_path = os.path.join(crawl_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to read manifest for suite %s: %s", suite_id, e)
        return None


def get_crawl_page(suite_id: str, page_index: int) -> dict | None:
    """Return the full element data for a specific crawled page by its index."""
    manifest = get_crawl_manifest(suite_id)
    if not manifest:
        return None
    pages = manifest.get("pages", [])
    if page_index < 0 or page_index >= len(pages):
        return None
    page_meta = pages[page_index]
    crawl_dir = os.path.join(os.path.abspath(settings.artifacts_dir), suite_id, "crawl")
    file_path = os.path.join(crawl_dir, page_meta.get("file", ""))
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to read page file %s: %s", file_path, e)
        return None
