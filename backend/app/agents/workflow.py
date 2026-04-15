"""
LangGraph Workflow — 7-Agent TDD Pipeline.

Pipeline (TDD order — test cases designed BEFORE steps):
  1. Planner         — decompose NL requirement into intent + strategic test plan
  2. Load Snapshots  — load pre-crawled DOM snapshots from disk (or live crawl)
  3. DOM Analyst     — identify semantic UI groups, stable selectors, nav patterns
  4. Test Generator  — produce IEEE 829 test cases from plan + DOM (BEFORE steps)
  5. Test Case Reviewer — validate coverage & feasibility (Loop A — retries Test Generator)
  6. Step Generator  — convert approved test cases + DOM into executable Playwright steps
  7. Step Reviewer   — validate/fix steps against real DOM (Loop B — retries Step Generator)
  8. QA Code Generator — produce final TypeScript .spec.ts file
"""

import logging
import os
from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.config import get_settings
from app.schemas.agent import (
    StructuredTestIntent,
    PageSnapshot,
    GeneratedTestStep,
    TestDesignOutput,
    StepReviewResult,
    TestPlan,
    DOMAnalysis,
    TestCaseReviewResult,
    IEEE829TestCase,
)
from app.agents.requirement_analyzer import plan_and_analyze
from app.agents.dom_analyst import analyze_dom
from app.agents.test_generator import generate_test_cases
from app.agents.test_case_reviewer import review_test_cases
from app.agents.step_generator import generate_steps, StepGeneratorOutput
from app.agents.reverifier import review_steps
from app.agents.code_generator import generate_test_suite_code
from app.services.crawler import crawl_pages
from app.services.site_crawl import load_crawl_snapshots

logger = logging.getLogger(__name__)

settings = get_settings()


# ── Workflow State ────────────────────────────────────────────────────

class WorkflowState(TypedDict):
    """State passed between nodes in the 7-agent TDD workflow."""
    # ── Inputs
    title: str
    description: str
    base_url: str
    app_description: str | None
    test_type: str  # functional, e2e, integration, accessibility, visual, performance

    # ── Authentication (optional)
    login_url: str | None
    login_username: str | None
    login_password: str | None

    # ── Suite ID and name for loading pre-crawled snapshots and naming output files
    suite_id: str | None
    suite_name: str | None

    # ── After Planner (node 1)
    intent: StructuredTestIntent | None
    plan: TestPlan | None

    # ── After DOM Analyst (node 3)
    dom_analysis: DOMAnalysis | None

    # ── After Snapshot loader (node 2)
    page_snapshots: list[PageSnapshot]

    # ── After Test Generator (node 4)
    test_design: TestDesignOutput | None

    # ── After Test Case Reviewer — Loop A (node 5)
    test_case_review: TestCaseReviewResult | None
    tc_iteration: int
    max_tc_iterations: int

    # ── After Step Generator (node 6)
    steps: list[GeneratedTestStep]

    # ── After Step Reviewer — Loop B (node 7)
    review: StepReviewResult | None
    iteration: int
    max_iterations: int

    # ── Final outputs
    final_steps: list[GeneratedTestStep]
    generated_code: str | None
    code_file_name: str | None
    status: str  # "running" | "success" | "failed" | "reviewed" | "tc_reviewed"
    error: str | None
    progress_messages: list[str]


def _add_progress(state: WorkflowState, message: str) -> list[str]:
    """Append a progress message to state."""
    msgs = list(state.get("progress_messages", []))
    msgs.append(message)
    return msgs


def _ensure_step_order(steps: list[GeneratedTestStep]) -> list[GeneratedTestStep]:
    """Ensure every step has a non-null order assigned sequentially."""
    for i, step in enumerate(steps, start=1):
        if step.order is None:
            step.order = i
    return steps


# ── Node: 1 – Orchestrator ───────────────────────────────────────────

async def orchestrator_node(state: WorkflowState) -> dict:
    """Decompose the NL requirement into sub-goals + strategic test plan."""
    logger.info("Workflow node: planner")
    try:
        output = await plan_and_analyze(
            title=state["title"],
            description=state["description"],
            base_url=state["base_url"],
            app_description=state.get("app_description"),
            test_type=state.get("test_type", "functional"),
        )
        intent = output.intent
        plan = output.plan
        return {
            "intent": intent,
            "plan": plan,
            "status": "running",
            "progress_messages": _add_progress(
                state,
                f"Planner: {len(intent.goals)} goals, {len(intent.pages)} pages, "
                f"{len(intent.assertions)} assertions | "
                f"{len(plan.scenarios)} test scenarios (strategy: {plan.strategy[:60]})"
            ),
        }
    except Exception as e:
        logger.error("Planner failed: %s", str(e))
        return {
            "status": "failed",
            "error": f"Planner failed: {str(e)}",
            "progress_messages": _add_progress(state, f"Error: Planner failed – {str(e)}"),
        }


# ── Node: 2 – Snapshot Loader (replaces Page Crawler) ───────────────

async def load_snapshots_node(state: WorkflowState) -> dict:
    """Load pre-crawled page snapshots from disk.

    If cached crawl data exists for this suite, it is loaded directly from the
    stored JSON files (fast, no browser launch).  Falls back to a live on-demand
    crawl of the pages listed in the orchestrator intent if no cached data exists.
    """
    logger.info("Workflow node: load_snapshots")
    suite_id = state.get("suite_id")
    intent = state.get("intent")

    # ── Try loading from pre-crawled cache first ──
    if suite_id:
        try:
            cached = await load_crawl_snapshots(suite_id)
            if cached:
                # ── MCP accessibility enrichment ──
                from app.services.mcp_browser import enrich_snapshots_with_mcp
                cached = await enrich_snapshots_with_mcp(
                    cached,
                    login_url=state.get("login_url"),
                    login_username=state.get("login_username"),
                    login_password=state.get("login_password"),
                )

                total_elements = sum(len(s.elements) for s in cached)
                logger.info(
                    "load_snapshots_node: loaded %d pre-crawled snapshots (%d elements) for suite %s",
                    len(cached), total_elements, suite_id,
                )
                return {
                    "page_snapshots": cached,
                    "status": "running",
                    "progress_messages": _add_progress(
                        state,
                        f"Snapshots: loaded {len(cached)} pre-crawled pages, "
                        f"{total_elements} interactive elements (from Auto-Gen cache)"
                    ),
                }
        except Exception as e:
            logger.warning("load_snapshots_node: cache load failed (%s), falling back to live crawl", e)

    # ── Fallback: live crawl of pages from orchestrator intent ──
    if not intent:
        return {
            "status": "failed",
            "error": "No intent available and no cached snapshots — cannot determine pages to crawl",
            "progress_messages": _add_progress(state, "Error: No snapshots or intent for crawling"),
        }

    pages_to_crawl = intent.pages if intent.pages else ["/"]
    login_url = state.get("login_url")
    login_username = state.get("login_username")
    login_password = state.get("login_password")

    logger.info(
        "load_snapshots_node: falling back to live crawl — base_url=%s, pages=%s",
        state["base_url"], pages_to_crawl,
    )

    try:
        snapshots = await crawl_pages(
            state["base_url"],
            pages_to_crawl,
            login_url=login_url,
            login_username=login_username,
            login_password=login_password,
        )

        # ── MCP accessibility enrichment ──
        from app.services.mcp_browser import enrich_snapshots_with_mcp
        snapshots = await enrich_snapshots_with_mcp(
            snapshots,
            login_url=login_url,
            login_username=login_username,
            login_password=login_password,
        )

        total_elements = sum(len(s.elements) for s in snapshots)
        return {
            "page_snapshots": snapshots,
            "status": "running",
            "progress_messages": _add_progress(
                state,
                f"Crawler: crawled {len(snapshots)} pages on-demand, "
                f"{total_elements} interactive elements (tip: run Auto-Gen to cache pages)"
            ),
        }
    except Exception as e:
        logger.error("Fallback crawl failed: %s", str(e))
        return {
            "status": "failed",
            "error": f"Page crawling failed: {str(e)}",
            "progress_messages": _add_progress(state, f"Error: Crawling failed – {str(e)}"),
        }


# ── Node: 3 – DOM Analyst ────────────────────────────────────────────

async def dom_analyst_node(state: WorkflowState) -> dict:
    """Analyse page snapshots to identify semantic UI groups and stable selectors."""
    logger.info("Workflow node: dom_analyst")
    snapshots = state.get("page_snapshots", [])
    plan = state.get("plan")

    if not plan:
        from app.schemas.agent import TestPlan as _TestPlan
        plan = _TestPlan(
            strategy="General web application testing",
            scenarios=[
                g for g in (state["intent"].goals if state.get("intent") else ["Test the application"])
            ],
        )

    try:
        dom_analysis = await analyze_dom(
            snapshots=snapshots,
            plan=plan,
            test_type=state.get("test_type", "functional"),
        )
        return {
            "dom_analysis": dom_analysis,
            "status": "running",
            "progress_messages": _add_progress(
                state,
                f"DOMAnalyst: {len(dom_analysis.semantic_groups)} semantic groups, "
                f"{len(dom_analysis.critical_selectors)} critical selectors, "
                f"{len(dom_analysis.accessibility_issues)} accessibility issues"
            ),
        }
    except Exception as e:
        logger.warning("DOM analysis failed (%s) — continuing with empty analysis", str(e))
        from app.schemas.agent import DOMAnalysis as _DOMAnalysis
        return {
            "dom_analysis": _DOMAnalysis(),
            "status": "running",
            "progress_messages": _add_progress(
                state, f"Warning: DOM analysis skipped – {str(e)}"
            ),
        }


# ── Node: 4 – Test Generator (IEEE 829, TDD order) ───────────────────

async def test_generator_node(state: WorkflowState) -> dict:
    """Design IEEE 829 test cases from plan + DOM (TDD order — before step generation)."""
    logger.info("Workflow node: test_generator (tc_iteration %d)", state.get("tc_iteration", 1))
    intent = state.get("intent")
    plan = state.get("plan")
    dom_analysis = state.get("dom_analysis")

    if not intent or not plan:
        return {
            "status": "failed",
            "error": "No intent/plan available for test-case design",
            "progress_messages": _add_progress(state, "Error: No intent/plan for test design"),
        }

    from app.schemas.agent import DOMAnalysis as _DOMAnalysis
    effective_dom = dom_analysis if dom_analysis is not None else _DOMAnalysis()

    try:
        test_design = await generate_test_cases(
            plan=plan,
            dom_analysis=effective_dom,
            intent=intent,
            test_type=state.get("test_type", "functional"),
        )
        tc_ids = [tc.tc_id for tc in test_design.test_cases]
        return {
            "test_design": test_design,
            "status": "running",
            "progress_messages": _add_progress(
                state,
                f"TestGenerator: designed {len(test_design.test_cases)} IEEE 829 test cases "
                f"({', '.join(tc_ids)}) from {len(plan.scenarios)} plan scenarios"
            ),
        }
    except Exception as e:
        logger.error("Test design failed: %s", str(e))
        return {
            "status": "failed",
            "error": f"Test case design failed: {str(e)}",
            "progress_messages": _add_progress(state, f"Error: Test case design failed – {str(e)}"),
        }


# ── Node: 5 – Test Case Reviewer (Loop A) ────────────────────────────

async def test_case_reviewer_node(state: WorkflowState) -> dict:
    """Review test cases for plan coverage and DOM feasibility (Loop A)."""
    logger.info("Workflow node: test_case_reviewer (tc_iteration %d)", state.get("tc_iteration", 1))
    test_design = state.get("test_design")
    plan = state.get("plan")
    dom_analysis = state.get("dom_analysis")

    if not test_design or not plan:
        return {
            "status": "failed",
            "error": "No test design or plan available for review",
            "progress_messages": _add_progress(state, "Error: No test design/plan for review"),
        }

    from app.schemas.agent import DOMAnalysis as _DOMAnalysis
    effective_dom = dom_analysis if dom_analysis is not None else _DOMAnalysis()

    try:
        review = await review_test_cases(
            test_design=test_design,
            plan=plan,
            dom_analysis=effective_dom,
            test_type=state.get("test_type", "functional"),
        )
        tc_iteration = state.get("tc_iteration", 1)

        if review.approved:
            return {
                "test_case_review": review,
                "status": "tc_reviewed",
                "progress_messages": _add_progress(
                    state,
                    f"TestCaseReviewer: APPROVED (confidence: {review.confidence:.0%}, "
                    f"{len(review.approved_cases)} cases, 0 coverage gaps)"
                ),
            }
        else:
            gaps = "; ".join(review.coverage_gaps[:3]) if review.coverage_gaps else ""
            issues = "; ".join(review.feedback[:2]) if review.feedback else "needs improvement"
            return {
                "test_case_review": review,
                "tc_iteration": tc_iteration + 1,
                "status": "running",
                "progress_messages": _add_progress(
                    state,
                    f"TestCaseReviewer: REJECTED (attempt {tc_iteration}): "
                    f"gaps=[{gaps}] issues=[{issues}]"
                ),
            }
    except Exception as e:
        logger.error("Test case review failed: %s", str(e))
        from app.schemas.agent import TestCaseReviewResult as _TCR
        fallback_review = _TCR(
            approved=True,
            feedback=[f"Review skipped: {str(e)}"],
            coverage_gaps=[],
            approved_cases=test_design.test_cases,
            confidence=0.5,
        )
        return {
            "test_case_review": fallback_review,
            "status": "tc_reviewed",
            "progress_messages": _add_progress(
                state,
                f"Warning: Test case review skipped – {str(e)}. Accepting generated cases."
            ),
        }


def tc_should_retry(state: WorkflowState) -> str:
    """Decide whether to retry test generation, proceed to step gen, or fail."""
    if state.get("status") == "failed":
        return "tc_failed"
    if state.get("status") == "tc_reviewed":
        return "proceed"

    tc_iteration = state.get("tc_iteration", 1)
    max_tc_iter = state.get("max_tc_iterations", 2)

    if tc_iteration > max_tc_iter:
        logger.info("TC review max iterations reached (%d), accepting test cases", max_tc_iter)
        return "tc_accept"

    return "tc_retry"


async def tc_accept_node(state: WorkflowState) -> dict:
    """Force-accept test cases after reaching max review iterations."""
    test_design = state.get("test_design")
    cases = test_design.test_cases if test_design else []
    tc_review = state.get("test_case_review")
    effective_cases = tc_review.approved_cases if tc_review and tc_review.approved_cases else cases
    confidence = tc_review.confidence if tc_review else 0.5

    from app.schemas.agent import TestCaseReviewResult as _TCR
    final_review = _TCR(
        approved=True,
        feedback=["Accepted after max TC review iterations"],
        coverage_gaps=[],
        approved_cases=effective_cases,
        confidence=confidence,
    )
    return {
        "test_case_review": final_review,
        "status": "tc_reviewed",
        "progress_messages": _add_progress(
            state,
            f"Accepted {len(effective_cases)} test cases after max iterations "
            f"(confidence: {confidence:.0%})"
        ),
    }


# ── Node: 6 – Step Generator ───────────────────────────────────────────

async def step_generator_node(state: WorkflowState) -> dict:
    """Convert approved test cases + DOM into executable Playwright steps."""
    logger.info("Workflow node: step_generator (iteration %d)", state.get("iteration", 1))
    intent = state.get("intent")
    snapshots = state.get("page_snapshots", [])

    if not intent:
        return {
            "status": "failed",
            "error": "No intent available for step generation",
            "progress_messages": _add_progress(state, "Error: No intent for step gen"),
        }

    # Get approved test cases from reviewer (Loop A output)
    tc_review = state.get("test_case_review")
    test_design = state.get("test_design")
    approved_cases: list[IEEE829TestCase] | None = None
    if tc_review and tc_review.approved_cases:
        approved_cases = tc_review.approved_cases
    elif test_design:
        approved_cases = test_design.test_cases

    # Include feedback from previous Step Reviewer if retrying (Loop B)
    review = state.get("review")
    feedback = None
    if review and not review.approved:
        parts = list(review.issues_found)
        parts.extend(review.selector_fixes)
        feedback = "\n".join(parts) if parts else None

    try:
        result: StepGeneratorOutput = await generate_steps(
            intent=intent,
            snapshots=snapshots,
            feedback=feedback,
            test_type=state.get("test_type", "functional"),
            approved_test_cases=approved_cases,
            login_username=state.get("login_username"),
            login_password=state.get("login_password"),
        )
        return {
            "steps": result.steps,
            "status": "running",
            "progress_messages": _add_progress(
                state,
                f"StepGenerator: produced {len(result.steps)} Playwright steps "
                f"({len(approved_cases or [])} test cases, confidence: {result.confidence:.0%})"
            ),
        }
    except Exception as e:
        logger.error("Step generation failed: %s", str(e))
        return {
            "status": "failed",
            "error": f"Step generation failed: {str(e)}",
            "progress_messages": _add_progress(state, f"Error: Step generation failed – {str(e)}"),
        }


# ── Node: 7 – Step Reviewer (Loop B) ───────────────────────────────────

async def step_reviewer_node(state: WorkflowState) -> dict:
    """Review steps against real DOM, fix hallucinated selectors."""
    logger.info("Workflow node: step_reviewer (iteration %d)", state.get("iteration", 1))
    steps = state.get("steps", [])
    snapshots = state.get("page_snapshots", [])

    if not steps:
        return {
            "status": "failed",
            "error": "No steps available for review",
            "progress_messages": _add_progress(state, "Error: No steps to review"),
        }

    try:
        review = await review_steps(steps, snapshots, test_type=state.get("test_type", "functional"))
        iteration = state.get("iteration", 1)

        if review.approved:
            final = _ensure_step_order(review.fixed_steps if review.fixed_steps else steps)
            return {
                "review": review,
                "final_steps": final,
                "status": "reviewed",
                "progress_messages": _add_progress(
                    state,
                    f"StepReviewer: APPROVED (confidence: {review.confidence:.0%}, "
                    f"fixes: {len(review.selector_fixes)})"
                ),
            }
        else:
            issues_summary = "; ".join(review.issues_found[:3]) if review.issues_found else "needs improvement"
            return {
                "review": review,
                "iteration": iteration + 1,
                "status": "running",
                "progress_messages": _add_progress(
                    state,
                    f"StepReviewer: REJECTED (attempt {iteration}): {issues_summary}"
                ),
            }
    except Exception as e:
        logger.error("Step review failed: %s", str(e))
        return {
            "review": None,
            "final_steps": _ensure_step_order(steps),
            "status": "reviewed",
            "error": f"Review skipped due to error: {str(e)}",
            "progress_messages": _add_progress(
                state,
                f"Warning: Step review skipped – {str(e)}. Accepting generated steps."
            ),
        }


def should_retry(state: WorkflowState) -> str:
    """Decide whether to retry Step Generator, proceed to code gen, or end."""
    if state.get("status") == "failed":
        return "end"
    if state.get("status") == "reviewed":
        return "generate_code"

    iteration = state.get("iteration", 1)
    max_iter = state.get("max_iterations", settings.max_reverification_attempts)

    if iteration > max_iter:
        logger.info("Max step iterations reached (%d), accepting steps", max_iter)
        return "accept"

    return "retry"


async def step_accept_node(state: WorkflowState) -> dict:
    """Force-accept steps after reaching max Step Reviewer iterations."""
    steps = state.get("steps", [])
    review = state.get("review")
    if review and review.fixed_steps:
        steps = review.fixed_steps
    confidence = review.confidence if review else 0.5
    return {
        "final_steps": _ensure_step_order(steps),
        "status": "reviewed",
        "progress_messages": _add_progress(
            state,
            f"Accepted steps after max iterations (confidence: {confidence:.0%})"
        ),
    }


# ── Node: 8 – QA Code Generator (final node) ───────────────────────────

async def qa_code_generator_node(state: WorkflowState) -> dict:
    """Generate executable Playwright TypeScript code — the QA Agent final step."""
    logger.info("Workflow node: qa_code_generator")
    final_steps = state.get("final_steps", [])
    test_design = state.get("test_design")
    tc_review = state.get("test_case_review")

    # Prefer reviewer-approved cases, fall back to raw test design, then empty
    test_cases: list[IEEE829TestCase] = []
    if tc_review and tc_review.approved_cases:
        test_cases = tc_review.approved_cases
    elif test_design:
        test_cases = test_design.test_cases

    try:
        generated = await generate_test_suite_code(
            test_cases=test_cases,
            steps=final_steps,
            suite_name=state.get("suite_name") or state["title"],
            base_url=state["base_url"],
            test_type=state.get("test_type", "functional"),
        )

        # Write the spec file to disk
        suite_id = state.get("suite_id")
        code_file_path: str | None = None
        if suite_id:
            suite_dir = os.path.join(settings.generated_tests_dir, suite_id)
            os.makedirs(suite_dir, exist_ok=True)
            code_file_path = os.path.join(suite_dir, generated.file_name)
            with open(code_file_path, "w", encoding="utf-8") as f:
                f.write(generated.code_content)
            logger.info("QACodeGenerator: wrote %s", code_file_path)

        return {
            "generated_code": generated.code_content,
            "code_file_name": generated.file_name,
            "status": "success",
            "progress_messages": _add_progress(
                state,
                f"QACodeGenerator: generated '{generated.file_name}' "
                f"({len(test_cases)} test cases, {len(final_steps)} steps)"
            ),
        }
    except Exception as e:
        logger.error("QA code generation failed: %s", str(e))
        return {
            "status": "success",  # Steps + test cases are still valid
            "error": f"Code generation failed (steps still valid): {str(e)}",
            "progress_messages": _add_progress(
                state,
                f"Warning: QA code generation failed – {str(e)}. Steps available."
            ),
        }

def build_workflow() -> StateGraph:
    """Build and compile the 7-agent TDD workflow graph."""
    workflow = StateGraph(WorkflowState)

    # ── Register nodes
    workflow.add_node("orchestrator", orchestrator_node)          # 1 Planner
    workflow.add_node("load_snapshots", load_snapshots_node)      # 2 Snapshot Loader
    workflow.add_node("dom_analyst", dom_analyst_node)            # 3 DOM Analyst
    workflow.add_node("test_generator", test_generator_node)      # 4 Test Generator
    workflow.add_node("test_case_reviewer", test_case_reviewer_node)  # 5 TC Reviewer
    workflow.add_node("tc_accept", tc_accept_node)                # Loop A force-accept
    workflow.add_node("step_generator", step_generator_node)      # 6 Step Generator
    workflow.add_node("step_reviewer", step_reviewer_node)        # 7 Step Reviewer
    workflow.add_node("step_accept", step_accept_node)            # Loop B force-accept
    workflow.add_node("qa_code_generator", qa_code_generator_node)  # 8 QA Code Generator

    # ── Linear spine
    workflow.set_entry_point("orchestrator")
    workflow.add_edge("orchestrator", "load_snapshots")
    workflow.add_edge("load_snapshots", "dom_analyst")
    workflow.add_edge("dom_analyst", "test_generator")
    workflow.add_edge("test_generator", "test_case_reviewer")

    # ── Loop A: test_case_reviewer → retry test_generator | proceed to step_generator | fail
    workflow.add_conditional_edges(
        "test_case_reviewer",
        tc_should_retry,
        {
            "tc_retry":  "test_generator",
            "tc_accept": "tc_accept",
            "proceed":   "step_generator",
            "tc_failed": END,
        },
    )
    workflow.add_edge("tc_accept", "step_generator")  # after force-accept, proceed

    # ── Step generator → step reviewer
    workflow.add_edge("step_generator", "step_reviewer")

    # ── Loop B: step_reviewer → retry step_generator | force-accept | generate code | fail
    workflow.add_conditional_edges(
        "step_reviewer",
        should_retry,
        {
            "retry":         "step_generator",
            "accept":        "step_accept",
            "generate_code": "qa_code_generator",
            "end":           END,
        },
    )
    workflow.add_edge("step_accept", "qa_code_generator")

    # ── Final node
    workflow.add_edge("qa_code_generator", END)

    return workflow.compile()


# Module-level compiled workflow
_compiled_workflow = None


def get_workflow():
    """Get or create the compiled workflow."""
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_workflow()
    return _compiled_workflow


async def run_workflow(
    title: str,
    description: str,
    base_url: str,
    app_description: str | None = None,
    test_type: str = "functional",
    login_url: str | None = None,
    login_username: str | None = None,
    login_password: str | None = None,
    suite_id: str | None = None,
    suite_name: str | None = None,
    progress_callback=None,
) -> WorkflowState:
    """
    Run the complete 7-agent TDD pipeline with real-time progress streaming.

    Pipeline: Planner → LoadSnapshots → DOMAnalyst → TestGenerator → TestCaseReviewer
              → StepGenerator → StepReviewer → QACodeGenerator

    If suite_id is provided and the suite has been Auto-Gen crawled, pre-crawled snapshots
    are loaded from disk (fast). Otherwise falls back to a live on-demand crawl.

    Returns the final workflow state with generated test cases, steps, and Playwright code.
    """
    workflow = get_workflow()

    initial_state: WorkflowState = {
        "title": title,
        "description": description,
        "base_url": base_url,
        "app_description": app_description,
        "test_type": test_type,
        "login_url": login_url,
        "login_username": login_username,
        "login_password": login_password,
        "suite_id": suite_id,
        "suite_name": suite_name,
        "intent": None,
        "plan": None,
        "dom_analysis": None,
        "page_snapshots": [],
        "test_design": None,
        "test_case_review": None,
        "tc_iteration": 1,
        "max_tc_iterations": 2,
        "steps": [],
        "review": None,
        "iteration": 1,
        "max_iterations": settings.max_reverification_attempts,
        "final_steps": [],
        "generated_code": None,
        "code_file_name": None,
        "status": "running",
        "error": None,
        "progress_messages": ["Starting 7-agent TDD pipeline…"],
    }

    logger.info("Starting workflow for test case: %s", title)

    if progress_callback:
        await progress_callback(initial_state["progress_messages"])

    # Stream node outputs so we can report progress after each step
    final_state = initial_state
    async for event in workflow.astream(initial_state):
        for node_name, node_output in event.items():
            if isinstance(node_output, dict):
                final_state = {**final_state, **node_output}
                if progress_callback and "progress_messages" in node_output:
                    await progress_callback(node_output["progress_messages"])

    logger.info("Workflow completed with status: %s", final_state.get("status"))
    return final_state