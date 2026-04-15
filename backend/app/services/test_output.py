"""
Test Output Service.

Generates Playwright TypeScript test code from test steps and writes
spec files to the generated-tests directory.
"""

import logging
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.test_case import TestCase
from app.models.test_step import TestStep
from app.models.test_suite import TestSuite
from app.schemas.agent import GeneratedTestStep, GeneratedTest
from app.agents.code_generator import generate_test_code

logger = logging.getLogger(__name__)

settings = get_settings()


async def generate_and_save_test_code(
    case_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    Generate Playwright test code for a test case and save to filesystem.

    1. Fetch test case, suite, and steps from DB
    2. Call the Test Generator Agent to produce code
    3. Write the .spec.ts file to generated-tests directory
    4. Return file paths and metadata

    Returns a dict with file_path, file_name, code_content, and metadata.
    """
    # Fetch test case
    case_stmt = select(TestCase).where(TestCase.id == case_id)
    case_result = await db.execute(case_stmt)
    test_case = case_result.scalar_one_or_none()
    if not test_case:
        raise ValueError(f"Test case not found: {case_id}")

    # Fetch suite
    suite_stmt = select(TestSuite).where(TestSuite.id == test_case.suite_id)
    suite_result = await db.execute(suite_stmt)
    suite = suite_result.scalar_one_or_none()
    if not suite:
        raise ValueError(f"Test suite not found for case: {case_id}")

    # Fetch steps ordered
    steps_stmt = (
        select(TestStep)
        .where(TestStep.case_id == case_id)
        .order_by(TestStep.order)
    )
    steps_result = await db.execute(steps_stmt)
    db_steps = steps_result.scalars().all()

    if not db_steps:
        raise ValueError(f"No test steps found for case: {case_id}")

    # Convert DB steps to schema objects for the agent
    generated_steps = [
        GeneratedTestStep(
            order=s.order,
            action=s.action,
            selector=s.selector,
            value=s.value,
            expected_result=s.expected_result,
            description=s.description,
        )
        for s in db_steps
    ]

    logger.info("Generating test code for case '%s' (%d steps)",
                test_case.title, len(generated_steps))

    # Generate the test code via the agent
    generated_test: GeneratedTest = await generate_test_code(
        steps=generated_steps,
        suite_name=suite.name,
        test_name=test_case.title,
        base_url=suite.base_url,
        test_type=test_case.test_type,
    )

    # Write the spec file to disk
    suite_dir = os.path.join(
        settings.generated_tests_dir,
        str(suite.id),
    )
    os.makedirs(suite_dir, exist_ok=True)

    file_path = os.path.join(suite_dir, generated_test.file_name)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(generated_test.code_content)

    logger.info("Test code written to: %s", file_path)

    return {
        "file_path": file_path,
        "file_name": generated_test.file_name,
        "code_content": generated_test.code_content,
        "imports": generated_test.imports,
        "test_metadata": generated_test.test_metadata,
        "suite_id": str(suite.id),
        "case_id": str(case_id),
    }


async def get_test_code(
    case_id: uuid.UUID,
    db: AsyncSession,
) -> dict | None:
    """
    Retrieve the generated test code for a test case if it exists on disk.

    Returns dict with file_path and code_content, or None if not found.
    """
    case_stmt = select(TestCase).where(TestCase.id == case_id)
    case_result = await db.execute(case_stmt)
    test_case = case_result.scalar_one_or_none()
    if not test_case:
        return None

    suite_stmt = select(TestSuite).where(TestSuite.id == test_case.suite_id)
    suite_result = await db.execute(suite_stmt)
    suite = suite_result.scalar_one_or_none()
    if not suite:
        return None

    # Look for spec files in the suite directory
    suite_dir = os.path.join(settings.generated_tests_dir, str(suite.id))
    if not os.path.isdir(suite_dir):
        return None

    # Find any spec file matching this case
    from app.agents.code_generator import _sanitize_filename
    safe_suite = _sanitize_filename(suite.name)
    safe_test = _sanitize_filename(test_case.title)
    expected_name = f"{safe_suite}_{safe_test}.spec.ts"

    file_path = os.path.join(suite_dir, expected_name)
    if not os.path.isfile(file_path):
        # QA Code Generator node uses test_case.title as suite_name, producing
        # "{safe_test}_suite.spec.ts" instead of "{safe_suite}_{safe_test}.spec.ts"
        alt_names = [
            f"{safe_test}_suite.spec.ts",      # qa_code_generator_node inline path
            f"{safe_suite}_suite.spec.ts",     # suite-level fallback
        ]
        for alt in alt_names:
            alt_path = os.path.join(suite_dir, alt)
            if os.path.isfile(alt_path):
                file_path = alt_path
                expected_name = alt
                break
        else:
            # Last resort: find any .spec.ts file whose name contains the test title
            try:
                spec_files = [f for f in os.listdir(suite_dir) if f.endswith(".spec.ts")]
                # Prefer files that contain the test case name fragment
                matching = [f for f in spec_files if safe_test[:20] in f]
                chosen = matching[0] if matching else (spec_files[0] if spec_files else None)
                if chosen:
                    expected_name = chosen
                    file_path = os.path.join(suite_dir, expected_name)
                else:
                    return None
            except OSError:
                return None

    with open(file_path, "r", encoding="utf-8") as f:
        code_content = f.read()

    return {
        "file_path": file_path,
        "file_name": expected_name,
        "code_content": code_content,
        "suite_id": str(suite.id),
        "case_id": str(case_id),
    }
