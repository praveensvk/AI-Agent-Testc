from pydantic import BaseModel


# ── Orchestrator (Plan-and-Execute) ──────────────────────────────────

class StructuredTestIntent(BaseModel):
    """Output of the Orchestrator: decomposed sub-goals and context."""
    goals: list[str]
    pages: list[str]
    preconditions: list[str] = []
    assertions: list[str] = []
    edge_cases: list[str] = []


class TestPlan(BaseModel):
    """Strategic test plan produced by the Planner alongside StructuredTestIntent."""
    strategy: str                          # overall testing strategy description
    scenarios: list[str]                   # high-level distinct test scenarios to cover
    risk_areas: list[str] = []             # risky/complex areas needing extra attention
    coverage_goals: list[str] = []         # what coverage the tests aim to achieve
    scope_in: list[str] = []               # pages/flows explicitly included
    scope_out: list[str] = []              # pages/flows explicitly excluded


class PlannerOutput(BaseModel):
    """Combined output of the Planner: structured test intent + strategic test plan."""
    intent: StructuredTestIntent
    plan: TestPlan


# ── Page Crawler ─────────────────────────────────────────────────────

class PageElement(BaseModel):
    """A single interactive element on a page."""
    tag: str
    role: str | None = None
    text: str | None = None
    selector: str
    element_type: str | None = None  # button, input, link, select, etc.
    attributes: dict[str, str] = {}


class PageSnapshot(BaseModel):
    """Output of the Page Crawler."""
    page_url: str
    page_title: str | None = None
    elements: list[PageElement] = []
    forms: list[dict] = []
    raw_html: str | None = None
    accessibility_tree: str | None = None  # MCP accessibility snapshot text


# ── DOM Analyst ───────────────────────────────────────────────────────

class SemanticGroup(BaseModel):
    """A logical grouping of DOM elements identified by the DOM Analyst."""
    group_type: str                        # loginForm, navMenu, checkoutForm, productCard, modal
    page_url: str
    description: str
    primary_selectors: list[str] = []     # 2-5 most stable selectors for the group's key elements
    priority: str = "medium"              # critical | high | medium | low


class DOMAnalysis(BaseModel):
    """Output of the DOM Analyst agent."""
    semantic_groups: list[SemanticGroup] = []
    navigation_patterns: list[str] = []   # "Main nav: Home → Products → Cart → Account"
    critical_selectors: dict[str, str] = {}   # descriptive_name → selector string
    accessibility_issues: list[str] = []
    recommended_test_paths: list[str] = []


# ── Test Generator (IEEE 829) ───────────────────────────────────────

class IEEE829TestCase(BaseModel):
    """An IEEE 829 format test case produced by the Test Generator."""
    tc_id: str                          # e.g. "TC-001"
    title: str
    category: str = "functional"        # functional, validation, navigation, security, usability
    priority: str = "medium"            # high, medium, low
    preconditions: list[str] = []
    test_steps: list[str]               # High-level NL step descriptions
    expected_results: list[str]         # Expected outcome per step


class TestDesignOutput(BaseModel):
    """Output of the Test Generator agent (IEEE 829 test design)."""
    test_cases: list[IEEE829TestCase]
    coverage_notes: str | None = None


# ── Step Generator (Playwright actions) ──────────────────────────────

class GeneratedTestStep(BaseModel):
    """A single executable Playwright step from the Step Generator."""
    order: int | None = None
    action: str   # navigate, click, type, fill, verify_text, verify_element, wait, screenshot
    selector: str | None = None
    value: str | None = None
    expected_result: str | None = None
    description: str | None = None
    tc_id: str | None = None              # which IEEE 829 test case this step implements


# ── Step Reviewer ────────────────────────────────────────────────────

class StepReviewResult(BaseModel):
    """Output of the Step Reviewer agent."""
    approved: bool
    fixed_steps: list[GeneratedTestStep] = []   # Steps with corrected selectors
    issues_found: list[str] = []
    selector_fixes: list[str] = []          # Human-readable fix descriptions
    confidence: float = 1.0


# ── Test Case Reviewer ───────────────────────────────────────────────

class TestCaseReviewResult(BaseModel):
    """Output of the Test Case Reviewer agent (Loop A)."""
    approved: bool
    feedback: list[str] = []              # specific, actionable issues found
    coverage_gaps: list[str] = []         # plan scenarios that have no test case
    approved_cases: list[IEEE829TestCase] = []  # full case list with minor fixes applied
    confidence: float = 1.0


# ── Code Generator ───────────────────────────────────────────────────

class GeneratedTest(BaseModel):
    """Output of the Code Generator - executable Playwright .spec.ts code."""
    file_name: str
    code_content: str
    imports: list[str] = []
    test_metadata: dict = {}
