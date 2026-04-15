"""
Page Crawler using Playwright (Python).

Crawls a target URL and extracts DOM structure, interactive elements,
form structures, and selectors for use by the Step Generator Agent.

For single/batch page crawls (used by the AI workflow):
  Uses playwright.sync_api in a background thread (asyncio.to_thread).

For site-wide BFS crawl (used by Auto-Gen):
  Uses playwright.async_api directly on FastAPI's event loop — avoids
  all Windows ProactorEventLoop/SelectorEventLoop thread conflicts.
"""

import asyncio
import base64
import logging
from urllib.parse import urljoin, urlparse

from playwright.async_api import (
    async_playwright,
    TimeoutError as AsyncPWTimeoutError,
    BrowserContext as AsyncBrowserContext,
)
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError, BrowserContext, Browser

from app.config import get_settings
from app.schemas.agent import PageSnapshot, PageElement

logger = logging.getLogger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# JavaScript extraction snippets (evaluated inside the Playwright page)
# ---------------------------------------------------------------------------

EXTRACT_ELEMENTS_JS = """
() => {
    const results = [];
    const interactiveSelectors = 'a, button, input, select, textarea, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [onclick]';
    const elements = document.querySelectorAll(interactiveSelectors);

    elements.forEach((el, index) => {
        if (index > 200) return;

        const rect = el.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) return;

        const tag = el.tagName.toLowerCase();
        const role = el.getAttribute('role') || null;
        const text = (el.textContent || '').trim().substring(0, 200);
        const ariaLabel = el.getAttribute('aria-label') || null;
        const testId = el.getAttribute('data-testid') || el.getAttribute('data-test-id') || null;
        const name = el.getAttribute('name') || null;
        const id = el.getAttribute('id') || null;
        const type = el.getAttribute('type') || null;
        const placeholder = el.getAttribute('placeholder') || null;
        const href = el.getAttribute('href') || null;

        let selector = '';
        if (testId) {
            selector = `[data-testid="${testId}"]`;
        } else if (role && ariaLabel) {
            selector = `role=${role}[name="${ariaLabel}"]`;
        } else if (role && text && text.length < 50) {
            selector = `role=${role}[name="${text}"]`;
        } else if (ariaLabel) {
            selector = `[aria-label="${ariaLabel}"]`;
        } else if (id) {
            selector = `#${id}`;
        } else if (name) {
            selector = `${tag}[name="${name}"]`;
        } else if (placeholder) {
            selector = `${tag}[placeholder="${placeholder}"]`;
        } else if (text && text.length < 50) {
            selector = `text="${text}"`;
        } else {
            selector = `${tag}:nth-of-type(${index + 1})`;
        }

        let elementType = tag;
        if (tag === 'input') elementType = type ? `input-${type}` : 'input-text';
        if (tag === 'a') elementType = 'link';
        if (tag === 'button' || role === 'button') elementType = 'button';

        const attrs = {};
        if (href) attrs['href'] = href;
        if (type) attrs['type'] = type;
        if (name) attrs['name'] = name;
        if (placeholder) attrs['placeholder'] = placeholder;
        if (id) attrs['id'] = id;
        if (ariaLabel) attrs['aria-label'] = ariaLabel;

        results.push({
            tag,
            role,
            text: text || null,
            selector,
            element_type: elementType,
            attributes: attrs,
        });
    });

    return results;
}
"""

EXTRACT_FORMS_JS = """
() => {
    const forms = [];
    document.querySelectorAll('form').forEach((form, i) => {
        if (i > 20) return;
        const fields = [];
        form.querySelectorAll('input, select, textarea').forEach(field => {
            fields.push({
                tag: field.tagName.toLowerCase(),
                name: field.getAttribute('name') || null,
                type: field.getAttribute('type') || null,
                placeholder: field.getAttribute('placeholder') || null,
                required: field.hasAttribute('required'),
                label: field.getAttribute('aria-label') ||
                       (field.id && document.querySelector(`label[for="${field.id}"]`)?.textContent?.trim()) || null,
            });
        });
        forms.push({
            action: form.getAttribute('action') || null,
            method: form.getAttribute('method') || 'get',
            fields,
        });
    });
    return forms;
}
"""

EXTRACT_LINKS_JS = """
(baseOrigin) => {
    const links = new Set();
    document.querySelectorAll('a[href]').forEach(a => {
        try {
            const href = a.getAttribute('href');
            if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
            const url = new URL(href, window.location.href);
            if (url.origin === baseOrigin) {
                // Strip hash/query for dedup
                links.add(url.origin + url.pathname);
            }
        } catch (_) {}
    });
    return Array.from(links);
}
"""


# ---------------------------------------------------------------------------
# Playwright crawler (runs sync API in a thread)
# ---------------------------------------------------------------------------

def _new_context(browser: Browser) -> BrowserContext:
    """Create a fresh browser context with standard viewport / UA."""
    return browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="AI-Agent-Test Crawler/1.0",
    )


def _perform_login_sync(
    context: BrowserContext,
    login_url: str,
    username: str,
    password: str,
    timeout_ms: int,
) -> None:
    """
    Perform a standard form-based login using the given browser context.

    Auto-detects username (email/text input) and password fields on the
    login page, fills them, and submits the form.  After submission the
    cookies / session persist in *context* for all subsequent pages.
    """
    page = context.new_page()
    try:
        page.goto(login_url, wait_until="networkidle", timeout=timeout_ms)
    except PWTimeoutError:
        page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)

    # Wait for SPA rendering
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PWTimeoutError:
        pass
    page.wait_for_timeout(1000)

    # --- Auto-detect form fields ---
    # Password field
    pw_locator = page.locator('input[type="password"]:visible').first
    pw_locator.wait_for(state="visible", timeout=10000)

    # Username field: visible text/email/tel input that is NOT the password
    username_locator = page.locator(
        'input:visible:not([type="password"]):not([type="hidden"])'
        ':not([type="checkbox"]):not([type="radio"])'
        ':not([type="submit"]):not([type="button"])'
    ).first

    # Fill credentials
    username_locator.fill(username)
    pw_locator.fill(password)

    # Submit: try the nearest submit button first, else press Enter
    submit_btn = page.locator(
        'button[type="submit"]:visible, input[type="submit"]:visible'
    ).first
    if submit_btn.count():
        submit_btn.click()
    else:
        pw_locator.press("Enter")

    # Wait for navigation away from the login page
    try:
        page.wait_for_url(
            lambda url: url != login_url and "/login" not in url.lower(),
            timeout=15000,
        )
    except PWTimeoutError:
        logger.warning("Login redirect detection timed out — continuing anyway")

    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PWTimeoutError:
        pass

    logger.info("Login complete — current URL: %s", page.url)
    page.close()


def _extract_page_sync(
    context: BrowserContext,
    url: str,
    timeout_ms: int,
    capture_screenshot: bool = False,
    extract_links_origin: str | None = None,
) -> tuple["PageSnapshot", str | None, list[str]]:
    """Navigate to *url* inside the (possibly authenticated) context and extract DOM info.

    Returns a tuple of (PageSnapshot, screenshot_base64_or_None, discovered_links).
    discovered_links is populated only when extract_links_origin is provided.
    """
    page = context.new_page()

    # Navigate – try networkidle first, fall back to domcontentloaded
    try:
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
    except PWTimeoutError:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except PWTimeoutError:
            page.close()
            return PageSnapshot(page_url=url, page_title=None, elements=[], forms=[]), None, []

    page_title = page.title()

    # Extra settle time for late network activity
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PWTimeoutError:
        pass

    # Wait for SPA frameworks to render
    try:
        page.wait_for_function(
            """() => {
                const root = document.getElementById('root')
                    || document.getElementById('app')
                    || document.getElementById('__next');
                return !root || root.children.length > 0;
            }""",
            timeout=5000,
        )
    except PWTimeoutError:
        pass

    page.wait_for_timeout(2000)

    # Extract interactive elements & forms via JS evaluation
    raw_elements = page.evaluate(EXTRACT_ELEMENTS_JS)
    raw_forms = page.evaluate(EXTRACT_FORMS_JS)

    raw_html = page.content()
    if len(raw_html) > 50000:
        raw_html = raw_html[:50000] + "\n<!-- truncated -->"

    elements = [PageElement(**el) for el in raw_elements]

    # Capture screenshot if requested
    screenshot_b64: str | None = None
    if capture_screenshot:
        try:
            screenshot_bytes = page.screenshot(full_page=False)
            screenshot_b64 = "data:image/png;base64," + base64.b64encode(screenshot_bytes).decode()
        except Exception as ss_err:
            logger.warning("Screenshot capture failed for %s: %s", url, ss_err)

    # Discover same-origin links while the page is still open (avoids a second navigation)
    discovered_links: list[str] = []
    if extract_links_origin:
        try:
            discovered_links = page.evaluate(EXTRACT_LINKS_JS, extract_links_origin)
        except Exception as lnk_err:
            logger.warning("Link discovery failed for %s: %s", url, lnk_err)

    page.close()
    snapshot = PageSnapshot(
        page_url=url,
        page_title=page_title,
        elements=elements,
        forms=raw_forms,
        raw_html=raw_html,
    )
    return snapshot, screenshot_b64, discovered_links


def _crawl_pages_sync(
    urls: list[str],
    timeout_ms: int,
    login_url: str | None = None,
    login_username: str | None = None,
    login_password: str | None = None,
) -> list[PageSnapshot]:
    """
    Crawl one or more pages using a single Playwright browser.

    If login credentials are provided the crawler first authenticates via
    form-based login so subsequent page visits use the authenticated session.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = _new_context(browser)

            # Authenticate if credentials provided
            if login_url and login_username and login_password:
                logger.info("Performing login at %s as %s", login_url, login_username)
                try:
                    _perform_login_sync(
                        context, login_url, login_username, login_password, timeout_ms
                    )
                except Exception as e:
                    logger.error("Login failed: %s — continuing unauthenticated", e)

            # Crawl each page with the (possibly authenticated) context
            snapshots: list[PageSnapshot] = []
            for url in urls:
                try:
                    snap, _, _ = _extract_page_sync(context, url, timeout_ms)
                    snapshots.append(snap)
                    logger.info(
                        "Crawled %s: %d elements, %d forms",
                        url, len(snap.elements), len(snap.forms),
                    )
                except Exception as e:
                    logger.error("Failed to crawl %s: %s", url, e, exc_info=True)
                    snapshots.append(
                        PageSnapshot(page_url=url, page_title=None, elements=[], forms=[])
                    )
            return snapshots
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def crawl_page(
    url: str,
    *,
    login_url: str | None = None,
    login_username: str | None = None,
    login_password: str | None = None,
) -> PageSnapshot:
    """
    Crawl a single page using Playwright.
    Optionally authenticates first if login credentials are provided.
    """
    logger.info("Crawling page: %s", url)
    timeout_ms = settings.crawler_timeout_ms

    try:
        snapshots = await asyncio.to_thread(
            _crawl_pages_sync,
            [url],
            timeout_ms,
            login_url,
            login_username,
            login_password,
        )
        return snapshots[0]
    except Exception as e:
        logger.error("Crawler failed for %s: %s", url, e, exc_info=True)
        return PageSnapshot(page_url=url, page_title=None, elements=[], forms=[])


async def crawl_pages(
    base_url: str,
    paths: list[str],
    *,
    login_url: str | None = None,
    login_username: str | None = None,
    login_password: str | None = None,
) -> list[PageSnapshot]:
    """
    Crawl multiple pages given a base URL and list of relative paths.
    Uses a single browser + context so authentication persists across pages.
    """
    urls = []
    for path in paths:
        if path.startswith("http"):
            urls.append(path)
        else:
            urls.append(urljoin(base_url.rstrip("/") + "/", path.lstrip("/")))

    timeout_ms = settings.crawler_timeout_ms
    try:
        return await asyncio.to_thread(
            _crawl_pages_sync,
            urls,
            timeout_ms,
            login_url,
            login_username,
            login_password,
        )
    except Exception as e:
        logger.error("Crawler batch failed: %s", e, exc_info=True)
        return [
            PageSnapshot(page_url=u, page_title=None, elements=[], forms=[])
            for u in urls
        ]


# ---------------------------------------------------------------------------
# Async helpers for site-wide crawl (async_playwright)
# ---------------------------------------------------------------------------

async def _perform_login_async(
    context: AsyncBrowserContext,
    login_url: str,
    username: str,
    password: str,
    timeout_ms: int,
) -> None:
    """Async login helper — used inside _run_async_crawler."""
    page = await context.new_page()
    try:
        await page.goto(login_url, wait_until="networkidle", timeout=timeout_ms)
    except AsyncPWTimeoutError:
        await page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)

    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except AsyncPWTimeoutError:
        pass
    await page.wait_for_timeout(1000)

    pw_locator = page.locator('input[type="password"]:visible').first
    await pw_locator.wait_for(state="visible", timeout=10000)

    username_locator = page.locator(
        'input:visible:not([type="password"]):not([type="hidden"])'
        ':not([type="checkbox"]):not([type="radio"])'
        ':not([type="submit"]):not([type="button"])'
    ).first

    await username_locator.fill(username)
    await pw_locator.fill(password)

    submit_btn = page.locator('button[type="submit"]:visible, input[type="submit"]:visible').first
    if await submit_btn.count():
        await submit_btn.click()
    else:
        await pw_locator.press("Enter")

    try:
        await page.wait_for_url(
            lambda url: url != login_url and "/login" not in url.lower(),
            timeout=15000,
        )
    except AsyncPWTimeoutError:
        logger.warning("Login redirect detection timed out — continuing anyway")

    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except AsyncPWTimeoutError:
        pass

    logger.info("Login complete — current URL: %s", page.url)
    await page.close()


async def _extract_page_async(
    context: AsyncBrowserContext,
    url: str,
    timeout_ms: int,
    capture_screenshot: bool = False,
    extract_links_origin: str | None = None,
) -> tuple[PageSnapshot, str | None, list[str]]:
    """Async page extraction — used inside _run_async_crawler."""
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
    except AsyncPWTimeoutError:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except AsyncPWTimeoutError:
            await page.close()
            return PageSnapshot(page_url=url, page_title=None, elements=[], forms=[]), None, []

    page_title = await page.title()

    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except AsyncPWTimeoutError:
        pass

    try:
        await page.wait_for_function(
            """() => {
                const root = document.getElementById('root')
                    || document.getElementById('app')
                    || document.getElementById('__next');
                return !root || root.children.length > 0;
            }""",
            timeout=5000,
        )
    except AsyncPWTimeoutError:
        pass

    await page.wait_for_timeout(2000)

    raw_elements = await page.evaluate(EXTRACT_ELEMENTS_JS)
    raw_forms = await page.evaluate(EXTRACT_FORMS_JS)

    raw_html = await page.content()
    if len(raw_html) > 50000:
        raw_html = raw_html[:50000] + "\n<!-- truncated -->"

    elements = [PageElement(**el) for el in raw_elements]

    screenshot_b64: str | None = None
    if capture_screenshot:
        try:
            screenshot_bytes = await page.screenshot(full_page=False)
            screenshot_b64 = "data:image/png;base64," + base64.b64encode(screenshot_bytes).decode()
        except Exception as ss_err:
            logger.warning("Screenshot capture failed for %s: %s", url, ss_err)

    discovered_links: list[str] = []
    if extract_links_origin:
        try:
            discovered_links = await page.evaluate(EXTRACT_LINKS_JS, extract_links_origin)
        except Exception as lnk_err:
            logger.warning("Link discovery failed for %s: %s", url, lnk_err)

    await page.close()
    snapshot = PageSnapshot(
        page_url=url,
        page_title=page_title,
        elements=elements,
        forms=raw_forms,
        raw_html=raw_html,
    )
    return snapshot, screenshot_b64, discovered_links


def _run_async_crawler(
    base_url: str,
    timeout_ms: int,
    max_pages: int,
    login_url: str | None,
    login_username: str | None,
    login_password: str | None,
    progress_callback_sync,  # sync callable(event_dict) — thread-safe
) -> list[PageSnapshot]:
    """
    Run the async BFS crawler inside asyncio.run().

    asyncio.run() on Windows always creates a ProactorEventLoop (regardless of
    uvicorn's loop policy), which supports subprocess creation required by Playwright.
    This function is meant to be called via asyncio.to_thread() from the main loop.
    """
    parsed_base = urlparse(base_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    async def _crawl():
        visited: set[str] = set()
        queue: list[str] = [base_url]
        snapshots: list[PageSnapshot] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="AI-Agent-Test Crawler/1.0",
                )

                if login_url and login_username and login_password:
                    # ── Snapshot login page BEFORE authenticating (form is still visible) ──
                    logger.info("Site crawl: snapshotting login page at %s", login_url)
                    try:
                        login_snap, login_screenshot, _ = await _extract_page_async(
                            context, login_url, timeout_ms,
                            capture_screenshot=True,
                        )
                        snapshots.append(login_snap)
                        # Mark login URL as visited so BFS won't revisit it
                        visited.add(login_url.rstrip("/"))
                        if progress_callback_sync:
                            progress_callback_sync({
                                "event": "crawl_page",
                                "url": login_url,
                                "page_title": login_snap.page_title,
                                "element_count": len(login_snap.elements),
                                "form_count": len(login_snap.forms),
                                "screenshot_base64": login_screenshot,
                                "pages_done": len(snapshots),
                                "pages_total": min(max_pages, len(snapshots) + len(queue)),
                            })
                    except Exception as e:
                        logger.error("Failed to snapshot login page %s: %s", login_url, e)

                    # ── Now perform the actual login ──
                    logger.info("Site crawl: login at %s as %s", login_url, login_username)
                    try:
                        await _perform_login_async(
                            context, login_url, login_username, login_password, timeout_ms
                        )
                    except Exception as e:
                        logger.error("Site crawl login failed: %s — continuing unauthenticated", e)

                while queue and len(snapshots) < max_pages:
                    url = queue.pop(0)
                    norm = url.rstrip("/")
                    if norm in visited:
                        continue
                    visited.add(norm)

                    logger.info("Site crawl [%d/%d]: %s", len(snapshots) + 1, max_pages, url)

                    try:
                        snap, screenshot_b64, discovered = await _extract_page_async(
                            context, url, timeout_ms,
                            capture_screenshot=True,
                            extract_links_origin=base_origin,
                        )
                        snapshots.append(snap)

                        for link in discovered:
                            norm_link = link.rstrip("/")
                            if norm_link not in visited and link not in queue:
                                queue.append(link)

                        if progress_callback_sync:
                            progress_callback_sync({
                                "event": "crawl_page",
                                "url": url,
                                "page_title": snap.page_title,
                                "element_count": len(snap.elements),
                                "form_count": len(snap.forms),
                                "screenshot_base64": screenshot_b64,
                                "pages_done": len(snapshots),
                                "pages_total": min(max_pages, len(snapshots) + len(queue)),
                            })

                    except Exception as e:
                        logger.error("Site crawl page failed for %s: %s", url, e, exc_info=True)
                        snapshots.append(PageSnapshot(page_url=url, page_title=None, elements=[], forms=[]))
                        if progress_callback_sync:
                            progress_callback_sync({
                                "event": "crawl_page",
                                "url": url,
                                "page_title": None,
                                "element_count": 0,
                                "form_count": 0,
                                "screenshot_base64": None,
                                "pages_done": len(snapshots),
                                "pages_total": min(max_pages, len(snapshots) + len(queue)),
                            })

            finally:
                await browser.close()

        return snapshots

    # On Windows, uvicorn sets WindowsSelectorEventLoopPolicy globally, causing
    # asyncio.run() to also create SelectorEventLoop. Bypass by creating
    # ProactorEventLoop directly (the only loop that supports subprocess creation).
    import sys
    if sys.platform == "win32":
        loop: asyncio.AbstractEventLoop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_crawl())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()
        asyncio.set_event_loop(None)


# ---------------------------------------------------------------------------
# Site-wide BFS crawl — public async API
# ---------------------------------------------------------------------------

async def crawl_site(
    base_url: str,
    *,
    login_url: str | None = None,
    login_username: str | None = None,
    login_password: str | None = None,
    max_pages: int = 20,
    progress_callback=None,  # async callable(event_dict) → None
) -> list[PageSnapshot]:
    """
    BFS crawl from base_url. Runs Playwright in a worker thread via asyncio.to_thread so
    that asyncio.run() inside the thread creates a ProactorEventLoop (required on Windows
    for subprocess creation). Progress events are forwarded to the caller's event loop
    in real-time via call_soon_threadsafe + asyncio.Queue.
    """
    timeout_ms = settings.crawler_timeout_ms
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue[dict] = asyncio.Queue()

    def _sync_callback(event: dict) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    try:
        crawl_task = asyncio.ensure_future(
            asyncio.to_thread(
                _run_async_crawler,
                base_url,
                timeout_ms,
                max_pages,
                login_url,
                login_username,
                login_password,
                _sync_callback,
            )
        )

        # Drain and forward events while the crawl runs
        while not crawl_task.done() or not event_queue.empty():
            try:
                event = event_queue.get_nowait()
            except asyncio.QueueEmpty:
                if crawl_task.done():
                    break
                await asyncio.sleep(0.05)
                continue
            if progress_callback:
                await progress_callback(event)

        snapshots = crawl_task.result()

        # ── MCP accessibility enrichment ──
        from app.services.mcp_browser import enrich_snapshots_with_mcp
        snapshots = await enrich_snapshots_with_mcp(
            snapshots,
            login_url=login_url,
            login_username=login_username,
            login_password=login_password,
        )

        total_elements = sum(len(s.elements) for s in snapshots)
        if progress_callback:
            await progress_callback({
                "event": "crawl_complete",
                "total_pages": len(snapshots),
                "total_elements": total_elements,
            })

        return snapshots

    except Exception as e:
        logger.error("crawl_site failed: %s", e, exc_info=True)
        error_msg = str(e) or repr(e)
        if progress_callback:
            await progress_callback({"event": "crawl_error", "error": error_msg})
        return []

