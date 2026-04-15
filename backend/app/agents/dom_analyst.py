"""
DOM Analyst Agent.

Analyzes raw page snapshots and identifies semantic UI patterns — groups DOM elements
into logical components (loginForm, navMenu, checkoutForm, productCard, etc.).
Extracts stable selectors, navigation patterns, accessibility issues, and recommended
test paths to guide the downstream Test Generator and Step Generator.

Runs after snapshot loading and before the Test Generator (TDD order).
"""

import logging

from app.utils.llm_factory import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import get_settings
from app.schemas.agent import PageSnapshot, DOMAnalysis, TestPlan
from app.utils.output_parser import RobustPydanticOutputParser

logger = logging.getLogger(__name__)

settings = get_settings()


SYSTEM_PROMPT = """\
You are an expert DOM analyst specialising in web UI pattern recognition for test automation.

Test Type: {test_type}

Given raw page snapshots (elements, forms, selectors) and a strategic test plan, your task is to:

1. **SEMANTIC GROUPS**: Identify logical UI component groups across all pages.
   Group related elements together — e.g. email field + password field + submit button → "loginForm".
   Common group types: loginForm, registrationForm, navMenu, primaryNav, productCard, productGrid,
   checkoutForm, shippingForm, paymentForm, cartSummary, searchBar, modal, alertMessage,
   userProfile, dataTable, filterPanel, paginationControl, footer, header.
   Use descriptive camelCase names if a type isn't in the list.

2. **NAVIGATION PATTERNS**: Describe the navigational flow of the application.
   Example: "Main nav: Home → Products → Cart → Checkout"

3. **CRITICAL SELECTORS**: Extract the most stable selectors for key UI elements.
   Preference order: data-testid > role-based > aria-label > id > name > text-content.
   Name them descriptively: "loginEmailInput", "loginSubmitButton", "navCartIcon".
   Include 5-15 critical selectors covering the most important interactive elements.
   When an accessibility tree is provided, cross-reference it with DOM elements to
   identify the most stable selectors — prefer role-based selectors that match both
   the DOM and the accessibility tree.

4. **ACCESSIBILITY ISSUES**: Flag anything visible in element attributes or the
   accessibility tree:
   - Inputs without labels or aria-label
   - Buttons without accessible text
   - Images without alt text
   - Missing ARIA roles on interactive elements
   - Non-descriptive link text (e.g. "click here")
   If an accessibility tree is provided, use it as the primary source for
   accessibility issue detection — it reflects how assistive technologies see the page.

5. **RECOMMENDED TEST PATHS**: Based on the navigation and forms, suggest 2-4 user
   flow paths to test. Example: "login → browse products → add to cart → checkout"

Rules:
- Only report elements that actually exist in the provided snapshots.
- For primary_selectors, include 2-5 key selectors for each group's most important elements.
- Set priority: "critical" for auth/payment flows, "high" for core features,
  "medium" for secondary features, "low" for informational/static content.
- If a page has no meaningful interactive groups, skip it — don't invent groups.

IMPORTANT: Respond with ONLY a valid JSON object. No markdown code fences.

{format_instructions}
"""

USER_PROMPT = """\
Strategic Test Plan Scenarios:
{scenarios}

Page Snapshots:
{page_context}

Analyze the DOM and identify all semantic groups, navigation patterns, critical selectors,
accessibility issues, and recommended test paths based on the scenarios above.
"""


def _format_page_context(snapshots: list[PageSnapshot]) -> str:
    """Format page snapshots into a readable context string for the LLM."""
    parts = []
    for snap in snapshots:
        part = f"\n=== Page: {snap.page_url} (Title: {snap.page_title}) ===\n"
        if snap.elements:
            part += f"Interactive Elements ({len(snap.elements)} total, showing first 60):\n"
            for el in snap.elements[:60]:
                attrs = ""
                if el.attributes:
                    # Highlight useful attributes
                    key_attrs = {k: v for k, v in el.attributes.items()
                                 if k in ("data-testid", "aria-label", "id", "name", "type",
                                          "placeholder", "href", "role", "class")}
                    attrs = " ".join(f'{k}="{v}"' for k, v in list(key_attrs.items())[:5])
                part += (
                    f"  [{el.element_type or el.tag}] selector='{el.selector}' "
                    f"text='{(el.text or '')[:60]}' role='{el.role or ''}' {attrs}\n"
                )
        if snap.forms:
            part += f"Forms ({len(snap.forms)}):\n"
            for form in snap.forms:
                part += f"  Form: action={form.get('action')} method={form.get('method')}\n"
                for field in form.get("fields", []):
                    part += (
                        f"    - {field.get('tag')} name={field.get('name')} "
                        f"type={field.get('type')} label='{field.get('label', '')}' "
                        f"id={field.get('id')}\n"
                    )
        if snap.accessibility_tree:
            part += f"Accessibility Tree:\n{snap.accessibility_tree}\n"
        parts.append(part)
    return "\n".join(parts) if parts else "No page data available."


async def analyze_dom(
    snapshots: list[PageSnapshot],
    plan: TestPlan,
    test_type: str = "functional",
) -> DOMAnalysis:
    """
    Analyze DOM snapshots to identify semantic UI patterns and stable selectors.

    Args:
        snapshots: Crawled page snapshots with real DOM elements.
        plan:      Strategic test plan (scenarios used as focus context).
        test_type: Testing category for type-specific guidance.

    Returns a DOMAnalysis with semantic groups, navigation patterns, and critical selectors.
    """
    llm = get_llm(temperature=0.1, num_predict=3072)

    parser = RobustPydanticOutputParser(pydantic_model=DOMAnalysis)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    chain = prompt | llm | StrOutputParser() | parser

    page_context = _format_page_context(snapshots)
    scenarios_text = (
        "\n".join(f"- {s}" for s in plan.scenarios)
        if plan.scenarios
        else "- No specific scenarios defined"
    )

    logger.info(
        "DOMAnalyst: analysing %d pages for %d scenarios (test_type=%s)",
        len(snapshots), len(plan.scenarios), test_type,
    )

    try:
        result: DOMAnalysis = await chain.ainvoke({
            "test_type": test_type,
            "scenarios": scenarios_text,
            "page_context": page_context,
            "format_instructions": parser.get_format_instructions(),
        })

        logger.info(
            "DOMAnalyst: found %d semantic groups, %d critical selectors, "
            "%d accessibility issues, %d recommended paths",
            len(result.semantic_groups),
            len(result.critical_selectors),
            len(result.accessibility_issues),
            len(result.recommended_test_paths),
        )
        return result

    except Exception as e:
        logger.warning("DOMAnalyst: LLM analysis failed (%s) — returning minimal fallback", e)
        # Minimal fallback so the pipeline can continue without DOM analysis
        return DOMAnalysis(
            semantic_groups=[],
            navigation_patterns=[
                f"Pages available: {', '.join(s.page_url for s in snapshots)}"
            ],
            critical_selectors={},
            accessibility_issues=[],
            recommended_test_paths=[plan.scenarios[0]] if plan.scenarios else [],
        )
