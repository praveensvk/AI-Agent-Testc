"""
Code Generator Agent.

Converts validated Playwright test steps into executable TypeScript .spec.ts code.
This is the final stage of the pipeline – it receives reviewed/fixed steps from the
Step Reviewer and produces a Playwright test file.
"""

import re
import logging

from app.utils.llm_factory import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel

from app.config import get_settings
from app.schemas.agent import GeneratedTestStep, GeneratedTest, IEEE829TestCase
from app.utils.output_parser import RobustPydanticOutputParser

logger = logging.getLogger(__name__)

settings = get_settings()


class CodeGeneratorOutput(BaseModel):
    """Wrapper for code generator LLM output."""
    code_content: str
    imports: list[str] = []
    notes: str | None = None


_TEST_TYPE_CODE_GUIDANCE: dict[str, str] = {
    "functional": "Standard Playwright assertions: toBeVisible(), toContainText(), toHaveValue(). Verify form submissions and navigation outcomes.",
    "e2e": "Wrap logical journey phases in test.step() blocks for clear reporting. Ensure every page transition uses waitForURL() or waitForLoadState().",
    "integration": "Use page.waitForResponse() after form submissions to capture API responses. Assert on response status and the resulting UI state.",
    "accessibility": "Prefer getByRole(), getByLabel(), getByText() over CSS/XPath selectors. Import AxeBuilder from '@axe-core/playwright' and add an axe accessibility scan assertion per test.",
    "visual": "Add await expect(page).toHaveScreenshot('<name>.png'); after each significant UI state. Use { maxDiffPixels: 100 } tolerance option.",
    "performance": "Capture page.evaluate(() => performance.timing) after navigation. Assert that domContentLoadedEventEnd - navigationStart is below a threshold (e.g. 3000 ms).",
}


SYSTEM_PROMPT = """\
You are an expert Playwright + TypeScript test automation engineer.
Given a list of test steps (each with an action, selector, value, and expected result),
generate a complete, executable Playwright test file in TypeScript.

Test Type: {test_type}
Code guidance for this test type: {test_type_code_guidance}

Rules:
1. Use `import {{ test, expect }} from '@playwright/test';` as the main import.
2. Wrap tests in `test.describe('{suite_name}', () => {{ ... }})`.
3. Each test case becomes a `test('{test_name}', async ({{ page }}) => {{ ... }})`.
4. Map step actions to Playwright API calls:
   - **navigate**: `await page.goto('{value}');`
   - **click**: `await page.locator('{selector}').click();`
   - **type**: `await page.locator('{selector}').pressSequentially('{value}');`
   - **fill**: `await page.locator('{selector}').fill('{value}');`
   - **verify_text**: `await expect(page.locator('{selector}')).toContainText('{expected_result}');`
   - **verify_element**: `await expect(page.locator('{selector}')).toBeVisible();` (or toBeHidden, etc.)
   - **wait**: `await page.waitForSelector('{selector}');` or `await page.waitForURL('{value}');`
   - **screenshot**: `await page.screenshot({{ path: '{value}' }});`
5. Add `await page.waitForLoadState('networkidle');` after navigation steps.
6. Add brief inline comments for each step using the step description.
7. Use role-based locators when available: `page.getByRole(...)`, `page.getByLabel(...)`.
8. Apply the test-type code guidance above when selecting assertions and patterns.
9. Generate clean, well-formatted TypeScript code.
10. Do NOT include any markdown formatting or code fences in your output.

Output ONLY valid JSON with this exact structure:
{{
  "code_content": "<the complete TypeScript test file content as a single string>",
  "imports": ["@playwright/test"],
  "notes": "<any optional notes about the generated code>"
}}
"""

USER_PROMPT = """\
Generate a Playwright TypeScript test file for:

**Suite Name:** {suite_name}
**Test Name:** {test_name}
**Base URL:** {base_url}

**Test Steps:**
{steps_text}

Generate the complete .spec.ts file content as a JSON object with "code_content", "imports", and "notes" fields.
Remember: output ONLY valid JSON, no markdown or code fences.
"""


def _format_steps_for_prompt(steps: list[GeneratedTestStep]) -> str:
    """Format test steps into a readable text block for the LLM prompt."""
    lines = []
    for step in steps:
        parts = [f"Step {step.order}: action={step.action}"]
        if step.selector:
            parts.append(f"selector='{step.selector}'")
        if step.value:
            parts.append(f"value='{step.value}'")
        if step.expected_result:
            parts.append(f"expected='{step.expected_result}'")
        if step.description:
            parts.append(f"description='{step.description}'")
        lines.append(", ".join(parts))
    return "\n".join(lines)


async def generate_test_code(
    steps: list[GeneratedTestStep],
    suite_name: str,
    test_name: str,
    base_url: str,
    test_type: str = "functional",
) -> GeneratedTest:
    """
    Generate Playwright TypeScript test code from reviewed test steps.

    Returns a GeneratedTest with the complete spec file content.
    """
    logger.info("CodeGenerator: generating .spec.ts for '%s' (%d steps, test_type=%s)",
                test_name, len(steps), test_type)

    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    steps_text = _format_steps_for_prompt(steps)
    parser = RobustPydanticOutputParser(pydantic_model=CodeGeneratorOutput)
    test_type_code_guidance = _TEST_TYPE_CODE_GUIDANCE.get(
        test_type,
        _TEST_TYPE_CODE_GUIDANCE["functional"],
    )

    chain = prompt | llm | StrOutputParser() | parser

    try:
        result: CodeGeneratorOutput = await chain.ainvoke({
            "suite_name": suite_name,
            "test_name": test_name,
            "base_url": base_url,
            "steps_text": steps_text,
            "test_type": test_type,
            "test_type_code_guidance": test_type_code_guidance,
        })

        safe_suite = _sanitize_filename(suite_name)
        safe_test = _sanitize_filename(test_name)
        file_name = f"{safe_suite}_{safe_test}.spec.ts"

        return GeneratedTest(
            file_name=file_name,
            code_content=result.code_content,
            imports=result.imports,
            test_metadata={
                "suite_name": suite_name,
                "test_name": test_name,
                "base_url": base_url,
                "steps_count": len(steps),
                "notes": result.notes,
            },
        )

    except Exception as e:
        logger.error("CodeGenerator LLM failed: %s", str(e))
        logger.info("Falling back to template-based code generation")
        return _generate_from_template(steps, suite_name, test_name, base_url)


# ── Helpers ──────────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """Convert a name to a safe filename component."""
    sanitized = re.sub(r'[^\w\s-]', '', name.lower())
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    return sanitized[:50].strip('_')


def _escape_ts_string(s: str) -> str:
    """Escape a string for use in TypeScript single-quoted strings."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _generate_from_template(
    steps: list[GeneratedTestStep],
    suite_name: str,
    test_name: str,
    base_url: str,
) -> GeneratedTest:
    """
    Fallback template-based code generation when LLM fails.
    Produces valid Playwright TypeScript code from test steps directly.
    """
    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"test.describe('{_escape_ts_string(suite_name)}', () => {{",
        f"  test('{_escape_ts_string(test_name)}', async ({{ page }}) => {{",
    ]

    for step in steps:
        comment = f"    // {step.description}" if step.description else ""
        if comment:
            lines.append(comment)

        action_code = _step_to_playwright_code(step, base_url)
        lines.append(f"    {action_code}")
        lines.append("")

    lines.append("  });")
    lines.append("});")
    lines.append("")

    code_content = "\n".join(lines)

    safe_suite = _sanitize_filename(suite_name)
    safe_test = _sanitize_filename(test_name)
    file_name = f"{safe_suite}_{safe_test}.spec.ts"

    return GeneratedTest(
        file_name=file_name,
        code_content=code_content,
        imports=["@playwright/test"],
        test_metadata={
            "suite_name": suite_name,
            "test_name": test_name,
            "base_url": base_url,
            "steps_count": len(steps),
            "notes": "Generated using template fallback (LLM unavailable)",
        },
    )


def _step_to_playwright_code(step: GeneratedTestStep, base_url: str) -> str:
    """Convert a single test step to a Playwright TypeScript code line."""
    selector = step.selector or ""
    value = step.value or ""
    expected = step.expected_result or ""

    match step.action:
        case "navigate":
            url = value if value.startswith("http") else f"{base_url.rstrip('/')}/{value.lstrip('/')}"
            return f"await page.goto('{_escape_ts_string(url)}');\n    await page.waitForLoadState('networkidle');"
        case "click":
            return f"await page.locator('{_escape_ts_string(selector)}').click();"
        case "type":
            return f"await page.locator('{_escape_ts_string(selector)}').pressSequentially('{_escape_ts_string(value)}');"
        case "fill":
            return f"await page.locator('{_escape_ts_string(selector)}').fill('{_escape_ts_string(value)}');"
        case "verify_text":
            return f"await expect(page.locator('{_escape_ts_string(selector)}')).toContainText('{_escape_ts_string(expected)}');"
        case "verify_element":
            return _generate_verify_element_code(selector, expected)
        case "wait":
            if value and ("/" in value or "http" in value):
                return f"await page.waitForURL('{_escape_ts_string(value)}');"
            elif selector:
                return f"await page.waitForSelector('{_escape_ts_string(selector)}');"
            else:
                return "await page.waitForLoadState('networkidle');"
        case "screenshot":
            label = value or "screenshot"
            safe_label = re.sub(r'[^\w-]', '_', label)
            return f"await page.screenshot({{ path: '{safe_label}.png', fullPage: true }});"
        case _:
            return f"// Unknown action: {step.action}"


# ── Multi-test-case (Suite) Code Generator ───────────────────────────

SUITE_SYSTEM_PROMPT = """\
You are an expert Playwright + TypeScript test automation engineer.
Generate a complete, executable Playwright test file containing MULTIPLE test cases.

Test Type: {test_type}
Code guidance: {test_type_code_guidance}

Rules:
1. Use `import {{ test, expect }} from '@playwright/test';` as the main import.
2. Wrap ALL tests in ONE `test.describe('{suite_name}', () => {{ ... }})` block.
3. Each test case becomes its own `test('<tc_title>', async ({{ page }}) => {{ ... }})` block.
4. Map step actions to Playwright API calls:
   - navigate  → `await page.goto('<value>'); await page.waitForLoadState('networkidle');`
   - click      → `await page.locator('<selector>').click();`
   - fill       → `await page.locator('<selector>').fill('<value>');`
   - type       → `await page.locator('<selector>').pressSequentially('<value>');`
   - verify_text → `await expect(page.locator('<selector>')).toContainText('<expected>');`
   - verify_element → `await expect(page.locator('<selector>')).toBeVisible();`
   - wait       → `await page.waitForSelector('<selector>');`
   - screenshot → `await page.screenshot({{ path: '<label>.png', fullPage: true }});`
5. Add inline comments for each step using the step description.
6. Use role-based locators where available: `page.getByRole(...)`, `page.getByLabel(...)`.
7. Apply test-type code guidance from above when choosing assertion patterns.
8. Output ONLY valid JSON — no markdown, no code fences.

Output format:
{{
  "code_content": "<complete TypeScript .spec.ts file as a single string>",
  "imports": ["@playwright/test"],
  "notes": "<optional notes>"
}}
"""

SUITE_USER_PROMPT = """\
**Suite Name:** {suite_name}
**Base URL:** {base_url}

**Test Cases with Steps:**
{test_cases_with_steps}

Generate a single .spec.ts file implementing ALL test cases above.
Each test case gets its own `test()` block. Output ONLY valid JSON.
"""


def _format_suite_for_prompt(
    test_cases: list[IEEE829TestCase],
    steps: list[GeneratedTestStep],
    base_url: str,
) -> str:
    """Group steps by tc_id and format for the suite code generation prompt."""
    # Group steps by tc_id
    steps_by_tc: dict[str, list[GeneratedTestStep]] = {}
    ungrouped: list[GeneratedTestStep] = []
    for step in steps:
        if step.tc_id:
            steps_by_tc.setdefault(step.tc_id, []).append(step)
        else:
            ungrouped.append(step)

    parts: list[str] = []
    for i, tc in enumerate(test_cases):
        tc_steps = steps_by_tc.get(tc.tc_id, [])
        # Assign ungrouped steps to the first TC if no grouped steps exist anywhere
        if not tc_steps and ungrouped and not any(steps_by_tc.values()):
            tc_steps = ungrouped

        parts.append(f"\n--- {tc.tc_id}: {tc.title} [{tc.category} / {tc.priority}] ---")
        if tc.preconditions:
            parts.append(f"Preconditions: {'; '.join(tc.preconditions)}")
        if tc_steps:
            for step in tc_steps:
                line = f"  Step {step.order}: {step.action}"
                if step.selector:
                    line += f" selector='{step.selector}'"
                if step.value:
                    line += f" value='{step.value}'"
                if step.expected_result:
                    line += f" expected='{step.expected_result}'"
                if step.description:
                    line += f" — {step.description}"
                parts.append(line)
        else:
            # Fall back to high-level NL steps from the test case design
            for j, nl_step in enumerate(tc.test_steps, 1):
                expected = tc.expected_results[j - 1] if j <= len(tc.expected_results) else ""
                parts.append(f"  Step {j}: {nl_step}  → {expected}")

    return "\n".join(parts)


async def generate_test_suite_code(
    test_cases: list[IEEE829TestCase],
    steps: list[GeneratedTestStep],
    suite_name: str,
    base_url: str,
    test_type: str = "functional",
) -> GeneratedTest:
    """
    Generate a Playwright TypeScript spec file for multiple IEEE 829 test cases.

    Groups steps by tc_id to produce one test() block per test case inside a
    single test.describe() wrapper. Falls back to template generation on LLM failure.
    """
    logger.info(
        "SuiteCodeGenerator: generating .spec.ts for '%s' (%d test cases, %d steps, type=%s)",
        suite_name, len(test_cases), len(steps), test_type,
    )

    llm = get_llm(num_predict=6144)

    parser = RobustPydanticOutputParser(pydantic_model=CodeGeneratorOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SUITE_SYSTEM_PROMPT),
        ("human", SUITE_USER_PROMPT),
    ])

    chain = prompt | llm | StrOutputParser() | parser

    test_type_code_guidance = _TEST_TYPE_CODE_GUIDANCE.get(
        test_type, _TEST_TYPE_CODE_GUIDANCE["functional"]
    )
    test_cases_with_steps = _format_suite_for_prompt(test_cases, steps, base_url)

    try:
        result: CodeGeneratorOutput = await chain.ainvoke({
            "suite_name": suite_name,
            "base_url": base_url,
            "test_type": test_type,
            "test_type_code_guidance": test_type_code_guidance,
            "test_cases_with_steps": test_cases_with_steps,
        })

        file_name = f"{_sanitize_filename(suite_name)}_suite.spec.ts"
        return GeneratedTest(
            file_name=file_name,
            code_content=result.code_content,
            imports=result.imports,
            test_metadata={
                "suite_name": suite_name,
                "base_url": base_url,
                "test_type": test_type,
                "test_cases_count": len(test_cases),
                "steps_count": len(steps),
                "notes": result.notes,
            },
        )

    except Exception as e:
        logger.error("SuiteCodeGenerator LLM failed: %s — falling back to template", str(e))
        return _generate_suite_from_template(test_cases, steps, suite_name, base_url)


def _generate_suite_from_template(
    test_cases: list[IEEE829TestCase],
    steps: list[GeneratedTestStep],
    suite_name: str,
    base_url: str,
) -> GeneratedTest:
    """Fallback template-based suite code generation when LLM fails."""
    # Group steps by tc_id
    steps_by_tc: dict[str, list[GeneratedTestStep]] = {}
    ungrouped: list[GeneratedTestStep] = []
    for step in steps:
        if step.tc_id:
            steps_by_tc.setdefault(step.tc_id, []).append(step)
        else:
            ungrouped.append(step)

    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"test.describe('{_escape_ts_string(suite_name)}', () => {{",
    ]

    for tc in test_cases:
        tc_steps = steps_by_tc.get(tc.tc_id, ungrouped if not steps_by_tc else [])
        lines.append(f"  test('{_escape_ts_string(tc.title)}', async ({{ page }}) => {{")
        for step in tc_steps:
            if step.description:
                lines.append(f"    // {step.description}")
            lines.append(f"    {_step_to_playwright_code(step, base_url)}")
            lines.append("")
        lines.append("  });")
        lines.append("")

    lines.append("});")
    lines.append("")

    file_name = f"{_sanitize_filename(suite_name)}_suite.spec.ts"
    return GeneratedTest(
        file_name=file_name,
        code_content="\n".join(lines),
        imports=["@playwright/test"],
        test_metadata={"suite_name": suite_name, "base_url": base_url, "generated_by": "template"},
    )


# ── Inline helpers ────────────────────────────────────────────────────

def _generate_verify_element_code(selector: str, expected: str) -> str:
    """Generate Playwright assertion code for element state verification."""
    if not expected:
        return f"await expect(page.locator('{_escape_ts_string(selector)}')).toBeVisible();"

    expected_lower = expected.lower()
    if "hidden" in expected_lower or "not visible" in expected_lower:
        return f"await expect(page.locator('{_escape_ts_string(selector)}')).toBeHidden();"
    elif "enabled" in expected_lower:
        return f"await expect(page.locator('{_escape_ts_string(selector)}')).toBeEnabled();"
    elif "disabled" in expected_lower:
        return f"await expect(page.locator('{_escape_ts_string(selector)}')).toBeDisabled();"
    elif "visible" in expected_lower:
        return f"await expect(page.locator('{_escape_ts_string(selector)}')).toBeVisible();"
    elif "url" in expected_lower:
        return f"await expect(page).toHaveURL(/{_escape_ts_string(expected)}/);"
    else:
        return f"await expect(page.locator('{_escape_ts_string(selector)}')).toBeVisible();"
