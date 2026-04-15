"""
Playwright MCP Client Wrapper.

Provides an async context manager to start the @playwright/mcp server
via stdio transport and exposes browser automation methods:
navigate, snapshot, screenshot, click, type.

Used by the crawler for accessibility-based element discovery.
Falls back gracefully if MCP server is unavailable.
"""

import asyncio
import json
import logging
import re
import shutil
from contextlib import asynccontextmanager

from app.config import get_settings
from app.schemas.agent import PageSnapshot

logger = logging.getLogger(__name__)

settings = get_settings()


class MCPBrowserClient:
    """
    Client for the Playwright MCP server using stdio JSON-RPC transport.

    The MCP server is started as a subprocess and communicates via
    stdin/stdout using the JSON-RPC 2.0 protocol.
    """

    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process
        self._request_id = 0

    async def _send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and read the response."""
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        payload = json.dumps(request)
        # MCP uses content-length header framing over stdio
        message = f"Content-Length: {len(payload)}\r\n\r\n{payload}"

        self._process.stdin.write(message.encode())
        await self._process.stdin.drain()

        # Read response with content-length framing
        response_data = await self._read_response()
        return response_data

    async def _read_response(self) -> dict:
        """Read a JSON-RPC response with content-length framing."""
        # Read headers until we find Content-Length
        content_length = 0
        while True:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30.0
            )
            line_str = line.decode().strip()
            if line_str == "":
                break  # End of headers
            if line_str.lower().startswith("content-length:"):
                content_length = int(line_str.split(":")[1].strip())

        if content_length == 0:
            raise RuntimeError("No Content-Length in MCP response")

        # Read the JSON body
        body = await asyncio.wait_for(
            self._process.stdout.readexactly(content_length), timeout=30.0
        )
        return json.loads(body.decode())

    async def initialize(self) -> dict:
        """Send the MCP initialize handshake."""
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ai-agent-test", "version": "1.0.0"},
        })
        # Send initialized notification
        notification = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        message = f"Content-Length: {len(notification)}\r\n\r\n{notification}"
        self._process.stdin.write(message.encode())
        await self._process.stdin.drain()
        return result

    async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """Call an MCP tool by name."""
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
        return await self._send_request("tools/call", params)

    async def navigate(self, url: str) -> dict:
        """Navigate the browser to a URL."""
        return await self.call_tool("browser_navigate", {"url": url})

    async def snapshot(self) -> dict:
        """Get an accessibility snapshot of the current page."""
        return await self.call_tool("browser_snapshot")

    async def screenshot(self) -> dict:
        """Take a screenshot of the current page."""
        return await self.call_tool("browser_screenshot")

    async def click(self, element: str, ref: str) -> dict:
        """Click an element by its ref."""
        return await self.call_tool("browser_click", {
            "element": element,
            "ref": ref,
        })

    async def type_text(self, element: str, ref: str, text: str) -> dict:
        """Type text into an element by its ref."""
        return await self.call_tool("browser_type", {
            "element": element,
            "ref": ref,
            "text": text,
        })

    async def close(self):
        """Terminate the MCP server process."""
        if self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()


def _get_mcp_command() -> list[str]:
    """Parse the MCP command string into a list of arguments."""
    parts = settings.playwright_mcp_command.split()
    # Resolve npx to npx.cmd on Windows
    if parts[0] == "npx":
        npx_path = shutil.which("npx.cmd") or shutil.which("npx")
        if npx_path:
            parts[0] = npx_path
    return parts


def is_mcp_available() -> bool:
    """Check if the MCP command is available on PATH."""
    parts = settings.playwright_mcp_command.split()
    cmd = parts[0]
    if cmd == "npx":
        return bool(shutil.which("npx.cmd") or shutil.which("npx"))
    return bool(shutil.which(cmd))


@asynccontextmanager
async def create_mcp_client():
    """
    Async context manager that starts the Playwright MCP server
    and yields an MCPBrowserClient.

    Usage:
        async with create_mcp_client() as client:
            await client.navigate("https://example.com")
            snapshot = await client.snapshot()
    """
    cmd = _get_mcp_command()
    logger.info("Starting Playwright MCP server: %s", " ".join(cmd))

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    client = MCPBrowserClient(process)
    try:
        await client.initialize()
        logger.info("Playwright MCP server initialized")
        yield client
    finally:
        await client.close()
        logger.info("Playwright MCP server stopped")


# ---------------------------------------------------------------------------
# Accessibility enrichment
# ---------------------------------------------------------------------------

def _extract_accessibility_text(response: dict) -> str | None:
    """Extract the human-readable accessibility tree text from an MCP snapshot response.

    The MCP ``tools/call`` response wraps tool output in::

        {"result": {"content": [{"type": "text", "text": "..."}]}}

    Returns the text string or ``None`` if the structure is unexpected.
    """
    try:
        result = response.get("result", response)
        content = result.get("content", [])
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                if text:
                    return text
    except Exception:
        pass
    return None


async def _mcp_login(
    client: MCPBrowserClient,
    login_url: str,
    username: str,
    password: str,
) -> None:
    """Perform login inside the MCP browser using accessibility refs.

    Navigates to ``login_url``, takes a snapshot, locates the username and
    password fields by their accessibility roles, fills them, and clicks the
    submit button.  Silently returns on any failure so the caller can proceed
    with unauthenticated snapshots.
    """
    await client.navigate(login_url)
    # Short wait for page to settle
    await asyncio.sleep(2)

    snap_resp = await client.snapshot()
    snap_text = _extract_accessibility_text(snap_resp)
    if not snap_text:
        logger.warning("MCP login: could not get accessibility snapshot of login page")
        return

    # Parse refs from the accessibility snapshot text.
    # Typical lines:  ``- ref=e5 textbox "Email" [focused]``
    # We look for a textbox (username) and a password/textbox (password).
    username_ref: str | None = None
    username_label: str | None = None
    password_ref: str | None = None
    password_label: str | None = None
    submit_ref: str | None = None
    submit_label: str | None = None

    for line in snap_text.splitlines():
        lower = line.lower()
        ref_match = re.search(r'ref=(e\d+)', line)
        if not ref_match:
            continue
        ref = ref_match.group(1)
        label_match = re.search(r'"([^"]+)"', line)
        label = label_match.group(1) if label_match else ""

        # Password field detection (type="password" renders as textbox with "password" in name)
        if not password_ref and ("password" in lower) and ("textbox" in lower or "input" in lower):
            password_ref = ref
            password_label = label

        # Username field: textbox that is NOT the password field
        elif not username_ref and ("textbox" in lower or "input" in lower):
            if "password" not in lower:
                username_ref = ref
                username_label = label

        # Submit button
        if not submit_ref and ("button" in lower) and any(
            kw in lower for kw in ("log in", "login", "sign in", "signin", "submit")
        ):
            submit_ref = ref
            submit_label = label

    if not username_ref or not password_ref:
        logger.warning(
            "MCP login: could not detect username/password fields "
            "(username_ref=%s, password_ref=%s)", username_ref, password_ref,
        )
        return

    # Fill credentials and submit
    await client.type_text(username_label or "username", username_ref, username)
    await client.type_text(password_label or "password", password_ref, password)

    if submit_ref:
        await client.click(submit_label or "submit", submit_ref)
    else:
        # Press Enter as fallback
        await client.call_tool("browser_press_key", {"key": "Enter"})

    # Wait for navigation after login
    await asyncio.sleep(3)
    logger.info("MCP login: completed login attempt")


async def enrich_snapshots_with_mcp(
    snapshots: list[PageSnapshot],
    *,
    login_url: str | None = None,
    login_username: str | None = None,
    login_password: str | None = None,
) -> list[PageSnapshot]:
    """Enrich page snapshots with MCP accessibility tree data.

    For each snapshot, navigates to the page URL in the MCP browser, takes an
    accessibility snapshot, and stores the human-readable text in the
    ``accessibility_tree`` field.

    Falls back gracefully: if MCP is unavailable or any error occurs, the
    original snapshots are returned unchanged.

    Args:
        snapshots:      List of PageSnapshot objects (from crawler).
        login_url:      Optional login page URL for authenticated crawls.
        login_username: Optional username for login.
        login_password: Optional password for login.

    Returns:
        The same list with ``accessibility_tree`` populated where possible.
    """
    if not settings.mcp_enrichment_enabled:
        logger.debug("MCP enrichment disabled via settings")
        return snapshots

    if not is_mcp_available():
        logger.info("MCP enrichment skipped — Playwright MCP command not available on PATH")
        return snapshots

    if not snapshots:
        return snapshots

    logger.info("MCP enrichment: enriching %d snapshots with accessibility trees", len(snapshots))

    try:
        async with create_mcp_client() as client:
            # Authenticate if credentials provided
            if login_url and login_username and login_password:
                try:
                    await _mcp_login(client, login_url, login_username, login_password)
                except Exception as login_err:
                    logger.warning("MCP login failed: %s — proceeding unauthenticated", login_err)

            enriched_count = 0
            for snap in snapshots:
                try:
                    await client.navigate(snap.page_url)
                    await asyncio.sleep(2)  # Allow page to settle

                    resp = await client.snapshot()
                    tree_text = _extract_accessibility_text(resp)
                    if tree_text:
                        # Truncate very large trees to keep LLM context manageable
                        if len(tree_text) > 15000:
                            tree_text = tree_text[:15000] + "\n... (truncated)"
                        snap.accessibility_tree = tree_text
                        enriched_count += 1
                        logger.debug("MCP enrichment: got accessibility tree for %s", snap.page_url)
                    else:
                        logger.debug("MCP enrichment: empty snapshot for %s", snap.page_url)
                except Exception as page_err:
                    logger.warning("MCP enrichment failed for %s: %s", snap.page_url, page_err)

            logger.info("MCP enrichment: enriched %d/%d snapshots", enriched_count, len(snapshots))

    except Exception as e:
        logger.warning("MCP enrichment failed globally: %s — returning original snapshots", e)

    return snapshots
