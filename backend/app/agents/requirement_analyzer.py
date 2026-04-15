"""
Plan-and-Execute Orchestrator.

Decomposes a natural-language test requirement into structured sub-goals,
target pages, preconditions, assertions, and edge cases.
Acts as the *Planner* in a Plan-and-Execute loop: downstream agents
(Test Generator, Step Generator, Step Reviewer) execute the plan.
"""

import logging

from app.utils.llm_factory import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import get_settings
from app.schemas.agent import StructuredTestIntent, TestPlan, PlannerOutput
from app.utils.output_parser import RobustPydanticOutputParser

logger = logging.getLogger(__name__)

settings = get_settings()

SYSTEM_PROMPT = """\
You are a Plan-and-Execute orchestrator for web-application test automation.

Your role is to DECOMPOSE a natural-language test requirement into a detailed,
actionable plan that downstream agents will execute.

Application context:
- Name / Description: {app_description}
- Base URL: {base_url}
- Test Type: {test_type}

Test type guidance:
- "functional": Focus on individual feature behavior — form submissions, navigation,
  CRUD operations.  Test ONE feature flow per goal.
- "e2e": Focus on complete user journeys across multiple pages — login → browse → add
  to cart → checkout.  Goals should span the full flow.
- "integration": Focus on how components interact — API calls, data persistence,
  cross-page state.  Verify data flows correctly between systems.
- "accessibility": Focus on WCAG compliance — keyboard navigation, ARIA attributes,
  color contrast, screen reader compatibility, focus management.
- "visual": Focus on layout and visual appearance — element positioning, responsive
  breakpoints, visual regressions.
- "performance": Focus on load times, responsiveness, resource usage — page load speed,
  interaction latency, network requests.

Given the test description below, produce a structured plan with:
1. **goals** – ONLY the goals that are explicitly described or directly implied by
   the user's requirement.  Do NOT invent additional scenarios, negative tests, or
   edge cases that the user did not ask for.  If the user says "login with valid
   credentials", that is ONE goal — do not add "login with wrong password" etc.
2. **pages** – Relative URL paths the test must visit (e.g. "/login", "/dashboard").
3. **preconditions** – Setup needed before any test runs (e.g. "user account exists").
4. **assertions** – Concrete, observable outcomes to verify that correspond to the
   user's stated goals (visible text, URL changes, element states, etc.).
   Only include assertions for the goals above — no extras.
5. **edge_cases** – List them ONLY if the user explicitly mentions negative or
   boundary testing.  If the description is about a happy-path flow, leave this
   list EMPTY.  Never auto-generate edge cases the user did not request.

Think step-by-step:
- First, identify EXACTLY what the user wants tested — nothing more, nothing less.
- Produce goals that map 1-to-1 with the user's described scenarios.
- For each goal, note which page and which assertions apply.
- Do NOT expand scope beyond the user's description.

IMPORTANT: Respond with ONLY a valid JSON object. No markdown code fences.

{format_instructions}
"""

USER_PROMPT = """\
Test Case Title: {title}

Test Case Description:
{description}
"""


def create_orchestrator():
    """Create the Plan-and-Execute orchestrator chain."""
    llm = get_llm(num_predict=2048)

    parser = RobustPydanticOutputParser(pydantic_model=StructuredTestIntent)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm | StrOutputParser() | parser
    return chain, parser


async def analyze_requirements(
    title: str,
    description: str,
    base_url: str,
    app_description: str | None = None,
    test_type: str = "functional",
) -> StructuredTestIntent:
    """
    Decompose a test requirement into a structured plan (sub-goals, pages,
    assertions, edge-cases) that downstream agents will execute.
    """
    chain, parser = create_orchestrator()

    logger.info("Orchestrator: decomposing requirement – %s", title)

    result = await chain.ainvoke({
        "title": title,
        "description": description,
        "base_url": base_url,
        "app_description": app_description or "Web application",
        "test_type": test_type,
        "format_instructions": parser.get_format_instructions(),
    })

    logger.info(
        "Orchestrator plan ready: %d goals, %d pages, %d assertions, %d edge-cases",
        len(result.goals), len(result.pages),
        len(result.assertions), len(result.edge_cases),
    )
    return result


# ── Planner: produces StructuredTestIntent + TestPlan together ─────────────

PLANNER_SYSTEM_PROMPT = """\
You are a Plan-and-Execute orchestrator for web-application test automation.

Your role is to produce TWO outputs simultaneously from a natural-language test requirement:
  1. A structured test INTENT (tactical: goals, pages, preconditions, assertions, edge_cases)
  2. A strategic test PLAN (strategic: scenarios, strategy, risk areas, coverage goals)

Application context:
- Name / Description: {app_description}
- Base URL: {base_url}
- Test Type: {test_type}

Test type guidance:
- "functional": Focus on individual feature behavior — form submissions, navigation, CRUD.
- "e2e": Focus on complete user journeys across multiple pages.
- "integration": Focus on component interactions — API calls, data persistence.
- "accessibility": Focus on WCAG compliance — keyboard nav, ARIA, screen reader.
- "visual": Focus on layout and visual appearance — positioning, responsiveness.
- "performance": Focus on load times, responsiveness, resource usage.

For the tactical INTENT:
- "goals": ONLY goals explicitly described or directly implied. Do NOT invent extra scenarios.
- "pages": Relative URL paths the test must visit.
- "preconditions": Setup needed before any test runs.
- "assertions": Concrete, observable outcomes. Only for stated goals.
- "edge_cases": ONLY if the user explicitly mentions negative/boundary testing.

For the strategic PLAN:
- "strategy": One sentence describing the overall testing approach.
- "scenarios": Distinct test scenarios to cover (can be same as goals initially, but
  phrased as user-story-level actions, e.g. 'User logs in with valid credentials').
- "risk_areas": Application areas that are complex or prone to bugs.
- "coverage_goals": What the test suite aims to achieve (e.g. 'Cover login happy path').
- "scope_in": Pages/flows explicitly included.
- "scope_out": Pages/flows explicitly excluded.

IMPORTANT: Respond with ONLY a valid JSON object. No markdown code fences.
The JSON must have exactly two top-level keys: "intent" and "plan".

{format_instructions}
"""

PLANNER_USER_PROMPT = """\
Test Case Title: {title}

Test Case Description:
{description}
"""


def create_planner():
    """Create the combined planner chain that produces PlannerOutput."""
    llm = get_llm(num_predict=3072)

    parser = RobustPydanticOutputParser(pydantic_model=PlannerOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_SYSTEM_PROMPT),
        ("human", PLANNER_USER_PROMPT),
    ])

    chain = prompt | llm | StrOutputParser() | parser
    return chain, parser


async def plan_and_analyze(
    title: str,
    description: str,
    base_url: str,
    app_description: str | None = None,
    test_type: str = "functional",
) -> PlannerOutput:
    """
    Produce both a StructuredTestIntent and a TestPlan from a NL test requirement.

    This is the entry point for the 7-agent TDD pipeline.
    Returns PlannerOutput containing both intent and plan.
    """
    chain, parser = create_planner()

    logger.info("Planner: decomposing requirement + building test plan – %s", title)

    result: PlannerOutput = await chain.ainvoke({
        "title": title,
        "description": description,
        "base_url": base_url,
        "app_description": app_description or "Web application",
        "test_type": test_type,
        "format_instructions": parser.get_format_instructions(),
    })

    logger.info(
        "Planner ready: %d goals, %d pages, %d assertions | %d scenarios, strategy='%s'",
        len(result.intent.goals), len(result.intent.pages), len(result.intent.assertions),
        len(result.plan.scenarios), result.plan.strategy[:60] if result.plan.strategy else "",
    )
    return result
