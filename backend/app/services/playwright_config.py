"""
Playwright Configuration Manager.

Generates playwright.config.ts dynamically based on TestSuite settings.
"""

import logging
import os

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

PLAYWRIGHT_CONFIG_TEMPLATE = """\
import {{ defineConfig, devices }} from '@playwright/test';

export default defineConfig({{
  testDir: '{test_dir}',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: [
    ['html', {{ open: 'never' }}],
    ['json', {{ outputFile: 'test-results/results.json' }}],
  ],
  use: {{
    baseURL: '{base_url}',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10000,
    navigationTimeout: 30000,
  }},
  projects: [
    {{
      name: 'chromium',
      use: {{ ...devices['Desktop Chrome'] }},
    }},
    {{
      name: 'firefox',
      use: {{ ...devices['Desktop Firefox'] }},
    }},
    {{
      name: 'webkit',
      use: {{ ...devices['Desktop Safari'] }},
    }},
  ],
  outputDir: 'test-results/',
}});
"""


def generate_playwright_config(
    suite_id: str,
    base_url: str,
    browsers: list[str] | None = None,
    screenshot: str = "only-on-failure",
    video: str = "retain-on-failure",
    retries: int = 1,
) -> str:
    """
    Generate a playwright.config.ts file content for a test suite.

    Args:
        suite_id: The test suite ID (used for test directory path).
        base_url: The base URL of the application under test.
        browsers: List of browser projects to include. Defaults to all three.
        screenshot: Screenshot capture mode.
        video: Video capture mode.
        retries: Number of test retries.

    Returns the config file content as a string.
    """
    if browsers is None:
        browsers = ["chromium", "firefox", "webkit"]

    # Build projects section based on selected browsers
    browser_configs = {
        "chromium": ("chromium", "Desktop Chrome"),
        "firefox": ("firefox", "Desktop Firefox"),
        "webkit": ("webkit", "Desktop Safari"),
    }

    project_entries = []
    for browser in browsers:
        if browser in browser_configs:
            name, device = browser_configs[browser]
            project_entries.append(
                f"    {{\n"
                f"      name: '{name}',\n"
                f"      use: {{ ...devices['{device}'] }},\n"
                f"    }}"
            )

    projects_str = ",\n".join(project_entries)
    test_dir = f"./{suite_id}"

    config_content = (
        "import { defineConfig, devices } from '@playwright/test';\n"
        "\n"
        "export default defineConfig({\n"
        f"  testDir: '{test_dir}',\n"
        "  fullyParallel: false,\n"
        "  forbidOnly: !!process.env.CI,\n"
        f"  retries: process.env.CI ? 2 : {retries},\n"
        "  workers: 1,\n"
        "  reporter: [\n"
        "    ['html', { open: 'never' }],\n"
        "    ['json', { outputFile: 'test-results/results.json' }],\n"
        "  ],\n"
        "  use: {\n"
        f"    baseURL: '{base_url}',\n"
        "    trace: 'on-first-retry',\n"
        f"    screenshot: '{screenshot}',\n"
        f"    video: '{video}',\n"
        "    actionTimeout: 10000,\n"
        "    navigationTimeout: 30000,\n"
        "  },\n"
        "  projects: [\n"
        f"{projects_str}\n"
        "  ],\n"
        "  outputDir: 'test-results/',\n"
        "});\n"
    )

    return config_content


def save_playwright_config(
    suite_id: str,
    base_url: str,
    browsers: list[str] | None = None,
    **kwargs,
) -> str:
    """
    Generate and save a playwright.config.ts to the generated-tests directory.

    Returns the absolute file path of the saved config.
    """
    config_content = generate_playwright_config(
        suite_id=suite_id,
        base_url=base_url,
        browsers=browsers,
        **kwargs,
    )

    config_path = os.path.join(settings.generated_tests_dir, "playwright.config.ts")
    os.makedirs(settings.generated_tests_dir, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config_content)

    logger.info("Playwright config written to: %s", config_path)
    return config_path
