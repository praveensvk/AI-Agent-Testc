"""
Test Generator Agent  (IEEE 829 · ReAct pattern).

Receives the strategic test plan, DOM analysis, and structured test intent to design
IEEE 829 test cases. Runs BEFORE Step Generation (TDD order) — test cases define
WHAT to test; the Step Generator later derives HOW to implement each case.

Each test case contains:
  TC-ID, Title, Category, Priority, Preconditions, Steps (NL), Expected Results.
"""

import logging

from app.utils.llm_factory import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import get_settings
from app.schemas.agent import (
    StructuredTestIntent,
    PageSnapshot,
    GeneratedTestStep,
    IEEE829TestCase,
    TestDesignOutput,
    TestPlan,
    DOMAnalysis,
)
from app.utils.output_parser import RobustPydanticOutputParser

logger = logging.getLogger(__name__)

settings = get_settings()


_TEST_TYPE_GUIDANCE: dict[str, str] = {
    "functional": "Focus on correctness of user-visible behaviour: form submissions, navigation, CRUD operations, and validation messages.",
    "e2e": "Cover complete multi-page user journeys from entry-point to final outcome. Each test case should span the full flow (login → action → assertion).",
    "integration": "Verify interactions between UI and backend: API request/response cycles, data persistence after form submission, and cross-component state synchronisation.",
    "accessibility": "Design test cases that verify WCAG 2.1 AA compliance: keyboard navigation, ARIA roles, colour-contrast ratios, focus management, and screen-reader labels.",
    "visual": "Each test case must capture full-page or component screenshots as expected results. Use visual comparison assertions and note pixel/layout tolerances.",
    "performance": "Test cases should measure load times, time-to-interactive, and resource counts. Flag test cases where wait durations would indicate a performance regression.",
}


SYSTEM_PROMPT = """\
You are a senior QA test-design engineer using the IEEE 829 standard.

Test Type: {test_type}
Test-type guidance: {test_type_guidance}

You receive:
 • A strategic test plan with defined scenarios, risk areas, and coverage goals
 • A DOM analysis identifying semantic UI groups and stable selectors on each page
 • A structured test intent with goals, assertions, and preconditions

Your task: produce IEEE 829 test cases that:
 1. Cover EVERY scenario listed in the test plan (one test case minimum per scenario)
 2. Reference real UI groups from the DOM analysis in the test_steps descriptions
 3. Produce concrete, measurable expected_results

Each test case must include:
  "tc_id"            – unique ID like "TC-001"
  "title"            – short descriptive title
  "category"         – one of: functional, validation, navigation, security, usability
  "priority"         – high / medium / low
  "preconditions"    – list of setup requirements
  "test_steps"       – ordered list of HIGH-LEVEL human-readable step descriptions
                        (use UI group names from DOM analysis where possible,
                         e.g. "Fill loginForm email field" not "fill input#email")
  "expected_results" – one expected outcome per step, in the same order

ReAct reasoning – per scenario:
  THOUGHT: Which DOM groups and UI elements does this scenario involve?
  ACTION:  Design test_steps that flow through those groups logically.
  OBSERVE: What observable outcome proves each step succeeded?

Rules:
1. One test case per plan scenario — don’t merge multiple scenarios into one TC.
2. Map each assertion from the test intent to at least one expected_result.
3. Use the DOM analysis semantic groups to name UI elements naturally.
4. Apply the test-type guidance to shape category, priority, and expected_results.
5. Number tc_ids sequentially: TC-001, TC-002, …
6. If DOM analysis is empty, rely on the intent and scenarios — write abstract steps.

Test Plan Summary:
{plan_summary}

DOM Analysis:
{dom_summary}

IMPORTANT: Respond with ONLY a valid JSON object. No markdown code fences.

{format_instructions}
"""

USER_PROMPT = """\
Test Intent context:
- Goals: {goals}
- Pages: {pages}
- Preconditions: {preconditions}
- Assertions: {assertions}
- Edge Cases: {edge_cases}

Design one IEEE 829 test case per plan scenario above.
Each test case should describe WHAT to test at a human-readable level.
"""


def _format_plan_summary(plan: TestPlan) -> str:
    """Format the test plan into a summary for the LLM."""
    parts = [f"Strategy: {plan.strategy}"]
    parts.append("Scenarios (one TC per scenario):\n" + "\n".join(f"  - {s}" for s in plan.scenarios))
    if plan.risk_areas:
        parts.append("Risk Areas: " + "; ".join(plan.risk_areas))
    if plan.coverage_goals:
        parts.append("Coverage Goals: " + "; ".join(plan.coverage_goals))
    return "\n".join(parts)


def _format_dom_summary(dom: DOMAnalysis) -> str:
    """Format the DOM analysis into a compact summary for the LLM."""
    if not dom.semantic_groups and not dom.critical_selectors:
        return "No DOM analysis available."
    parts = []
    if dom.semantic_groups:
        parts.append("Semantic UI Groups:")
        for g in dom.semantic_groups:
            parts.append(
                f"  [{g.priority.upper()}] {g.group_type} on {g.page_url}: {g.description}"
            )
    if dom.navigation_patterns:
        parts.append("Navigation: " + "; ".join(dom.navigation_patterns))
    if dom.recommended_test_paths:
        parts.append("Recommended paths: " + "; ".join(dom.recommended_test_paths))
    return "\n".join(parts)


def create_test_generator():
    """Create the IEEE 829 test-generator chain."""
    llm = get_llm(num_predict=4096)

    parser = RobustPydanticOutputParser(pydantic_model=TestDesignOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm | StrOutputParser() | parser
    return chain, parser


async def generate_test_cases(
    plan: TestPlan,
    dom_analysis: DOMAnalysis,
    intent: StructuredTestIntent,
    test_type: str = "functional",
) -> TestDesignOutput:
    """
    Generate IEEE 829 test cases from the strategic test plan and DOM analysis.

    Runs BEFORE Step Generation (TDD order). Test cases define WHAT to test;
    the Step Generator derives HOW to implement each case against the real DOM.

    Args:
        plan:         Strategic test plan (scenarios, strategy, risk_areas).
        dom_analysis: DOM analysis with semantic groups and stable selectors.
        intent:       Structured test intent (goals, assertions, preconditions).
        test_type:    Testing category for type-specific guidance.

    Returns a TestDesignOutput containing one or more IEEE829TestCase objects.
    """
    chain, parser = create_test_generator()
    plan_summary = _format_plan_summary(plan)
    dom_summary = _format_dom_summary(dom_analysis)
    test_type_guidance = _TEST_TYPE_GUIDANCE.get(
        test_type,
        _TEST_TYPE_GUIDANCE["functional"],
    )

    logger.info(
        "TestGenerator: designing IEEE 829 cases for %d scenarios, %d DOM groups (test_type=%s)",
        len(plan.scenarios), len(dom_analysis.semantic_groups), test_type,
    )

    result: TestDesignOutput = await chain.ainvoke({
        "test_type": test_type,
        "test_type_guidance": test_type_guidance,
        "plan_summary": plan_summary,
        "dom_summary": dom_summary,
        "goals": "\n".join(f"- {g}" for g in intent.goals),
        "pages": "\n".join(f"- {p}" for p in intent.pages),
        "preconditions": "\n".join(f"- {p}" for p in intent.preconditions) or "None",
        "assertions": "\n".join(f"- {a}" for a in intent.assertions) or "None",
        "edge_cases": "\n".join(f"- {e}" for e in intent.edge_cases) or "None",
        "format_instructions": parser.get_format_instructions(),
    })

    logger.info(
        "TestGenerator: produced %d IEEE 829 test cases",
        len(result.test_cases),
    )
    return result

    logger.info(
        "TestGenerator: produced %d IEEE 829 test cases",
        len(result.test_cases),
    )
    return result
