"""
Artifact Manager Service.

Collects, stores, and manages test execution artifacts:
screenshots, videos, traces, and logs from Playwright runs.
"""

import logging
import os
import shutil
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.artifact import Artifact

logger = logging.getLogger(__name__)

settings = get_settings()

# Extension -> MIME type mapping
_MIME_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".zip": "application/zip",
    ".json": "application/json",
    ".txt": "text/plain",
    ".log": "text/plain",
}


def get_artifact_dir(run_id: str) -> str:
    """Get the absolute artifact directory for a specific run."""
    return os.path.abspath(os.path.join(settings.artifacts_dir, run_id))


def _classify_artifact(filename: str, ext: str) -> str | None:
    """Classify a file as an artifact type based on extension and name."""
    if ext in (".png", ".jpg", ".jpeg"):
        return "screenshot"
    if ext in (".webm", ".mp4"):
        return "video"
    if ext == ".zip" or "trace" in filename.lower():
        return "trace"
    if ext in (".json", ".txt", ".log"):
        return "log"
    return None


async def collect_artifacts(
    run_id: uuid.UUID,
    output_dir: str,
    db: AsyncSession,
) -> list[Artifact]:
    """
    Collect artifacts from a Playwright test results directory.

    Walks the output directory, identifies screenshots, videos, traces,
    and logs, and creates DB records pointing to their locations.
    """
    run_id_str = str(run_id)
    artifact_dir = get_artifact_dir(run_id_str)
    os.makedirs(artifact_dir, exist_ok=True)

    artifacts: list[Artifact] = []

    if not os.path.isdir(output_dir):
        logger.warning("Output directory does not exist: %s", output_dir)
        return artifacts

    for root, _dirs, files in os.walk(output_dir):
        for fname in files:
            src_path = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()

            artifact_type = _classify_artifact(fname, ext)
            if artifact_type is None:
                continue

            # Copy to artifact directory (skip if already there)
            dest_path = os.path.join(artifact_dir, fname)
            if os.path.abspath(src_path) != os.path.abspath(dest_path):
                # Handle name conflicts
                base, extension = os.path.splitext(fname)
                counter = 1
                while os.path.exists(dest_path):
                    new_name = f"{base}_{counter}{extension}"
                    dest_path = os.path.join(artifact_dir, new_name)
                    fname = new_name
                    counter += 1
                shutil.copy2(src_path, dest_path)

            file_size = os.path.getsize(dest_path)

            artifact = Artifact(
                run_id=run_id,
                artifact_type=artifact_type,
                file_path=dest_path,
                file_name=fname,
                mime_type=_MIME_TYPES.get(ext),
                file_size=file_size,
            )
            db.add(artifact)
            artifacts.append(artifact)

    await db.flush()
    logger.info("Collected %d artifacts for run %s", len(artifacts), run_id_str)
    return artifacts


async def save_log_artifact(
    run_id: uuid.UUID,
    content: str,
    file_name: str,
    db: AsyncSession,
) -> Artifact | None:
    """Save a text log as an artifact."""
    if not content.strip():
        return None

    run_id_str = str(run_id)
    artifact_dir = get_artifact_dir(run_id_str)
    os.makedirs(artifact_dir, exist_ok=True)

    log_path = os.path.join(artifact_dir, file_name)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(content)

    artifact = Artifact(
        run_id=run_id,
        artifact_type="log",
        file_path=log_path,
        file_name=file_name,
        mime_type="text/plain",
        file_size=os.path.getsize(log_path),
    )
    db.add(artifact)
    await db.flush()
    return artifact
