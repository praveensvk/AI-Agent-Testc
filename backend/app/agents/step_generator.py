"""
Step Generator Agent  (ReAct with DOM context).

Takes a structured test intent (goals, assertions, pages) + page snapshots
(real DOM) and converts them into concrete, executable Playwright actions.

Supported actions:
  navigate, click, type, fill, verify_text, verify_element, wait, screenshot
"""

import logging

from app.utils.llm_factory import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, model_validator

from app.config import get_settings
from app.schemas.agent import (
    StructuredTestIntent,
    PageSnapshot,
    GeneratedTestStep,
    IEEE829TestCase,
)
from app.utils.output_parser import RobustPydanticOutputParser

logger = logging.getLogger(__name__)

settings = get_settings()


class StepGeneratorOutput(BaseModel):
    """Wrapper for step generator output."""
    steps: list[GeneratedTestStep]
    confidence: float = 1.0
    notes: str | None = None

    @model_validator(mode="after")
    def assign_missing_order(self) -> "StepGeneratorOutput":
        """Auto-assign order to steps if the LLM omitted it."""
        for i, step in enumerate(self.steps):
            if step.order is None:
                step.order = i + 1
        return self


SYSTEM_PROMPT = """\
You are an expert Playwright test-automation engineer.

Test Type: {test_type}

You receive:
 • A structured test intent with goals, assertions, preconditions, and edge cases.
 • Live DOM context: real interactive elements, selectors, and forms extracted from the
   target pages.

Your task: convert every goal and assertion into CONCRETE Playwright actions,
producing an ordered flat list of executable steps.

Allowed actions (use ONLY these):
  navigate       – go to a URL                         (value = URL)
  click          – click an element                    (selector required)
  type           – type into an input char-by-char     (selector + value)
  fill           – fill an input instantly              (selector + value)
  verify_text    – assert visible text on the page     (selector + expected_result)
  verify_element – assert element state (visible, hidden, enabled, disabled)
                                                       (selector + expected_result)
  wait           – wait for element / URL / networkidle (selector or value)
  screenshot     – capture a screenshot                (value = optional label)

ReAct reasoning – for each goal, think:
  THOUGHT: What concrete browser interactions does this goal require?
  ACTION:  Which DOM element (from page context) should I target?
           Use the EXACT selector from the DOM context – do NOT invent selectors.
  OBSERVE: What should the expected_result be so the Step Reviewer can verify it?

Rules:
1. Start with a "navigate" step to the correct page URL.
2. Add a "wait" step ONLY after navigate actions — do NOT add waits between
   every action (Playwright auto-waits for elements).
3. For form fills use "fill" (faster) unless character-by-character input matters.
4. Include "verify_text" or "verify_element" assertions that match each assertion
   from the test intent.
5. Prefer stable selectors: data-testid > role-based > aria-label > id > name > text.
   When an accessibility tree is provided, cross-reference it with DOM elements to
   choose role-based selectors (e.g. getByRole('button', {{ name: 'Submit' }})) that
   match the tree — these are the most resilient against DOM changes.
6. If test credentials are provided below, use them EXACTLY for login/authentication
   form fields (username, email, password). Otherwise, use realistic but safe test
   data (e.g. "testuser@example.com", "Password123!").
7. Include ONE "screenshot" step at the end of each goal for evidence — not after
   every assertion.
8. Every step MUST have a descriptive "description" field.
9. ONLY generate steps for the goals and assertions listed.  If edge_cases are
   provided, cover them.  If edge_cases is empty or "None", do NOT invent
   negative/boundary scenarios on your own.
10. Be CONCISE — aim for 3-8 steps per goal.  Combine related fills without
    inserting waits between them.  The total should typically be under 25 steps.
11. This is ONE test case — produce a SINGLE sequential flow, not multiple
    independent test scenarios concatenated together.
12. IMPORTANT: Each step MUST have its "tc_id" field set to the test-case ID it
    implements (e.g. "TC-001"). When covering multiple test cases, group all steps
    for TC-001 first, then all steps for TC-002, etc. If no test cases are provided,
    leave tc_id as null.
{reviewer_feedback}
{test_credentials}
Available page information:
{page_context}

IMPORTANT: Respond with ONLY a valid JSON object. No markdown code fences.

{format_instructions}
"""

USER_PROMPT = """\
{test_cases_slot}
Test Intent:
- Goals: {goals}
- Pages: {pages}
- Preconditions: {preconditions}
- Assertions: {assertions}
- Edge Cases: {edge_cases}

Generate the flat list of executable Playwright steps (with tc_id set on each step).
Order steps sequentially (step 1, 2, 3 … N) across all test cases.
"""


def _format_page_context(snapshots: list[PageSnapshot]) -> str:
    """Format page snapshots into a readable context string for the LLM."""
    parts = []
    for snap in snapshots:
        part = f"\n--- Page: {snap.page_url} (Title: {snap.page_title}) ---\n"
        if snap.elements:
            part += "Interactive elements:\n"
            for el in snap.elements[:50]:
                attrs = ", ".join(f"{k}={v}" for k, v in el.attributes.items()) if el.attributes else ""
                part += f"  - [{el.element_type}] selector='{el.selector}' text='{el.text or ''}' {attrs}\n"
        if snap.forms:
            part += "Forms:\n"
            for form in snap.forms:
                part += f"  - Form action={form.get('action')} method={form.get('method')}\n"
                for field in form.get("fields", []):
                    part += f"    - {field.get('tag')} name={field.get('name')} type={field.get('type')} label={field.get('label')}\n"
        if snap.accessibility_tree:
            part += f"Accessibility Tree:\n{snap.accessibility_tree}\n"
        parts.append(part)
    return "\n".join(parts) if parts else "No page data available."


def create_step_generator():
    """Create the step generator chain."""
    llm = get_llm(num_predict=4096)

    parser = RobustPydanticOutputParser(pydantic_model=StepGeneratorOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm | StrOutputParser() | parser
    return chain, parser


async def generate_steps(
    intent: StructuredTestIntent,
    snapshots: list[PageSnapshot],
    feedback: str | None = None,
    test_type: str = "functional",
    approved_test_cases: list[IEEE829TestCase] | None = None,
    login_username: str | None = None,
    login_password: str | None = None,
) -> StepGeneratorOutput:
    """
    Generate executable Playwright steps from structured test intent + DOM.

    Args:
        intent:               Output of the Orchestrator (goals, assertions, pages).
        snapshots:            Crawled page snapshots with real DOM selectors.
        feedback:             Optional feedback from the Step Reviewer for re-generation.
        test_type:            Testing category for type-specific guidance.
        approved_test_cases:  Approved IEEE 829 test cases from Test Case Reviewer.
                              When provided, one step group per test case with tc_id set.
    """
    chain, parser = create_step_generator()

    page_context = _format_page_context(snapshots)

    reviewer_feedback = ""
    if feedback:
        reviewer_feedback = (
            f"\n**IMPORTANT – Step Reviewer feedback (you MUST address these issues):**\n"
            f"{feedback}\n"
        )

    # Format approved test cases as primary input when available
    test_cases_slot = ""
    if approved_test_cases:
        lines = ["Approved IEEE 829 Test Cases (generate steps for EACH, set tc_id on every step):"]
        for tc in approved_test_cases:
            lines.append(f"\n{tc.tc_id}: {tc.title} [{tc.category}/{tc.priority}]")
            if tc.preconditions:
                lines.append(f"  Preconditions: {'; '.join(tc.preconditions)}")
            lines.append("  Expected steps (high-level):")
            for i, step in enumerate(tc.test_steps, 1):
                expected = tc.expected_results[i - 1] if i <= len(tc.expected_results) else ""
                lines.append(f"    {i}. {step}  →  {expected}")
        test_cases_slot = "\n".join(lines) + "\n"

    # Build test credentials block for the prompt
    if login_username or login_password:
        cred_lines = ["Test Credentials (use these EXACTLY for login/authentication form fields):"]
        if login_username:
            cred_lines.append(f"  - Username/Email: {login_username}")
        if login_password:
            cred_lines.append(f"  - Password: {login_password}")
        test_credentials = "\n".join(cred_lines)
    else:
        test_credentials = ""

    logger.info(
        "StepGenerator: converting %d goals into Playwright steps "
        "(%d test cases, feedback=%s, credentials=%s)",
        len(intent.goals), len(approved_test_cases or []), bool(feedback),
        bool(login_username),
    )

    result: StepGeneratorOutput = await chain.ainvoke({
        "page_context": page_context,
        "goals": "\n".join(f"- {g}" for g in intent.goals),
        "pages": "\n".join(f"- {p}" for p in intent.pages),
        "preconditions": "\n".join(f"- {p}" for p in intent.preconditions) or "None",
        "assertions": "\n".join(f"- {a}" for a in intent.assertions) or "None",
        "edge_cases": "\n".join(f"- {e}" for e in intent.edge_cases) or "None",
        "reviewer_feedback": reviewer_feedback,
        "test_credentials": test_credentials,
        "test_type": test_type,
        "test_cases_slot": test_cases_slot,
        "format_instructions": parser.get_format_instructions(),
    })

    logger.info(
        "StepGenerator: produced %d executable steps (confidence: %.2f)",
        len(result.steps), result.confidence,
    )
    return result
