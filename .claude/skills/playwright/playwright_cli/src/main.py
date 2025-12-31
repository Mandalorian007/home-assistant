"""
Playwright CLI - Browser automation from the command line.

A standalone CLI for Playwright browser control, independent of any sandbox or environment.
"""

import sys
import json
import time
import asyncio
import signal
import socket
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Any, Tuple
from functools import wraps

import click
from rich.console import Console

# Playwright is loaded dynamically to avoid import errors if not installed
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None  # type: ignore
    Page = None  # type: ignore

console = Console()

# --- Constants ---

DEFAULT_PORT = 9222
DEFAULT_VIEWPORT_WIDTH = 1920
DEFAULT_VIEWPORT_HEIGHT = 1080

# iPhone 14/15 standard viewport
MOBILE_VIEWPORT_WIDTH = 390
MOBILE_VIEWPORT_HEIGHT = 844
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


# --- Exceptions ---

class BrowserNotInitializedError(Exception):
    """Raised when browser environment is not properly set up."""
    pass


class BrowserConnectionError(Exception):
    """Raised when browser connection fails."""
    pass


# --- Helpers ---

def run_async(f):
    """Decorator to run async functions in a click command."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return asyncio.run(f(*args, **kwargs))
        except RuntimeError as e:
            if "This event loop is already running" in str(e):
                return f(*args, **kwargs)
            raise
    return wrapper


def check_playwright_installed() -> bool:
    """Check if Playwright Python package is installed."""
    return PLAYWRIGHT_AVAILABLE


def check_chromium_installed() -> Tuple[bool, str]:
    """Check if Playwright Chromium is installed. Returns (is_installed, path_or_cache_dir)."""
    import glob

    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        cache_dir = home / "Library/Caches/ms-playwright"
        chromium_pattern = "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
    elif system == "Windows":
        cache_dir = home / "AppData/Local/ms-playwright"
        chromium_pattern = "chromium-*/chrome-win/chrome.exe"
    else:
        cache_dir = home / ".cache/ms-playwright"
        chromium_pattern = "chromium-*/chrome-linux/chrome"

    chromium_paths = sorted(glob.glob(str(cache_dir / chromium_pattern)), reverse=True)

    if chromium_paths:
        return True, chromium_paths[0]
    return False, str(cache_dir)


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("localhost", port)) == 0
    sock.close()
    return result


def kill_browser_on_port(port: int) -> bool:
    """Kill the browser process on the specified port. Returns True if killed."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    import os
                    os.kill(int(pid), signal.SIGTERM)
                except (ValueError, ProcessLookupError):
                    pass
            return True
    except Exception:
        pass
    return False


def ensure_initialized() -> str:
    """Check browser environment is initialized. Returns chromium path or exits."""
    if not check_playwright_installed():
        console.print("[red]✗ Browser environment not initialized[/red]")
        console.print("\n[yellow]ERROR: Playwright is not installed[/yellow]")
        console.print("\nRun this command to initialize:")
        console.print("  [cyan]uv run pw init[/cyan]")
        sys.exit(1)

    is_installed, path_or_dir = check_chromium_installed()
    if not is_installed:
        console.print("[red]✗ Browser environment not initialized[/red]")
        console.print("\n[yellow]ERROR: Playwright Chromium not found[/yellow]")
        console.print(f"  Searched in: {path_or_dir}")
        console.print("\nRun this command to initialize:")
        console.print("  [cyan]uv run pw init[/cyan]")
        sys.exit(1)

    return path_or_dir


# --- Browser Connection ---

async def connect(port: int = DEFAULT_PORT) -> Tuple[Any, Browser]:
    """Connect to running browser. Returns (playwright, browser) tuple."""
    browser_url = f"http://127.0.0.1:{port}"
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(browser_url)
        return pw, browser
    except Exception as e:
        await pw.stop()
        raise BrowserConnectionError(f"Could not connect to port {port}: {e}")


async def get_active_page(browser: Browser) -> Page:
    """Get the most recently active page from browser."""
    contexts = browser.contexts
    if not contexts:
        raise RuntimeError("No browser contexts found")
    pages = contexts[0].pages
    if not pages:
        raise RuntimeError("No pages found")
    return pages[-1]


# --- Browser Lifecycle ---

def start_browser_process(
    chromium_path: str,
    port: int,
    headed: bool = False,
    profile_dir: Optional[Path] = None,
    width: int = DEFAULT_VIEWPORT_WIDTH,
    height: int = DEFAULT_VIEWPORT_HEIGHT,
    mobile: bool = False,
) -> subprocess.Popen:
    """Start Chromium process with remote debugging."""
    if profile_dir is None:
        profile_dir = Path.home() / ".cache/playwright-browser-temp"
        profile_dir.mkdir(parents=True, exist_ok=True)

    if mobile:
        width = MOBILE_VIEWPORT_WIDTH
        height = MOBILE_VIEWPORT_HEIGHT

    cmd = [
        chromium_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    if mobile:
        cmd.extend([
            f"--user-agent={MOBILE_USER_AGENT}",
            "--enable-touch-events",
            "--force-device-scale-factor=3",
        ])

    if not headed:
        cmd.extend([
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
        ])

    if sys.platform == "win32":
        process = subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS)
    else:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    return process


async def wait_for_browser(port: int, max_attempts: int = 30) -> bool:
    """Wait for browser to be ready. Returns True if connected."""
    time.sleep(1)
    for attempt in range(max_attempts):
        try:
            async with async_playwright() as pw:
                browser_url = f"http://127.0.0.1:{port}"
                browser = await pw.chromium.connect_over_cdp(browser_url)
                await browser.close()
                return True
        except Exception:
            if attempt == max_attempts - 1:
                return False
            time.sleep(0.5)
    return False


# --- Page Operations ---

async def navigate(browser: Browser, url: str, new_tab: bool = False) -> str:
    """Navigate to URL. Returns the final URL."""
    if new_tab:
        context = browser.contexts[0]
        page = await context.new_page()
    else:
        page = await get_active_page(browser)
    await page.goto(url, wait_until="domcontentloaded")
    return page.url


async def take_screenshot(browser: Browser, path: Optional[str] = None, full_page: bool = False) -> str:
    """Take screenshot. Returns the filepath."""
    page = await get_active_page(browser)
    if path:
        filepath = Path(path)
    else:
        filename = f"screenshot-{int(time.time())}.png"
        filepath = Path(tempfile.gettempdir()) / filename
    await page.screenshot(path=str(filepath), full_page=full_page)
    return str(filepath)


async def evaluate_js(browser: Browser, code: str) -> Any:
    """Execute JavaScript in the active page."""
    page = await get_active_page(browser)
    return await page.evaluate(f"(async () => {{ return ({code}); }})()")


async def click_element(browser: Browser, selector: str) -> None:
    """Click an element matching the selector."""
    page = await get_active_page(browser)
    await page.click(selector)


async def type_text(browser: Browser, selector: str, text: str) -> None:
    """Type text into an input field."""
    page = await get_active_page(browser)
    await page.fill(selector, text)


async def press_key(browser: Browser, key: str) -> None:
    """Press a keyboard key."""
    page = await get_active_page(browser)
    await page.keyboard.press(key)


async def scroll_page(browser: Browser, direction: str, amount: int = 500) -> None:
    """Scroll the page in specified direction."""
    page = await get_active_page(browser)
    if direction == "top":
        await page.evaluate("window.scrollTo(0, 0)")
    elif direction == "bottom":
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    elif direction == "up":
        await page.mouse.wheel(0, -amount)
    elif direction == "down":
        await page.mouse.wheel(0, amount)


async def get_cookies(browser: Browser) -> list:
    """Get all cookies from the browser context."""
    context = browser.contexts[0]
    return await context.cookies()


async def get_accessibility_tree(browser: Browser) -> dict:
    """Get the accessibility tree snapshot."""
    page = await get_active_page(browser)
    return await page.accessibility.snapshot()


async def get_dom(browser: Browser, full: bool = False) -> Any:
    """Get DOM structure. Returns full HTML if full=True, else simplified structure."""
    page = await get_active_page(browser)

    if full:
        return await page.content()

    js = """
    () => {
        function isVisible(el) {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            return style.display !== 'none' &&
                   style.visibility !== 'hidden' &&
                   style.opacity !== '0';
        }

        function clean(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent.trim();
                return text ? text : null;
            }
            if (node.nodeType !== Node.ELEMENT_NODE) return null;

            const el = node;
            if (!isVisible(el)) return null;

            const tag = el.tagName.toLowerCase();
            if (['script', 'style', 'noscript', 'meta', 'link', 'svg', 'path'].includes(tag)) return null;

            const attrs = {};
            ['id', 'name', 'class', 'role', 'type', 'placeholder', 'aria-label', 'href', 'value'].forEach(attr => {
                if (el.hasAttribute(attr)) attrs[attr] = el.getAttribute(attr);
            });

            const children = [];
            el.childNodes.forEach(child => {
                const cleaned = clean(child);
                if (cleaned) {
                    if (typeof cleaned === 'string' && children.length > 0 && typeof children[children.length-1] === 'string') {
                        children[children.length-1] += ' ' + cleaned;
                    } else {
                        children.push(cleaned);
                    }
                }
            });

            if (Object.keys(attrs).length === 0 && children.length === 0) {
                if (!['p', 'div', 'span', 'h1','h2','h3','h4','h5','h6', 'li', 'td'].includes(tag)) return null;
            }

            return { tag, attrs, children };
        }

        return clean(document.body);
    }
    """
    return await page.evaluate(js)


PICKER_JS = """
(message) => {
    return new Promise((resolve) => {
        const selections = [];
        const selectedElements = new Set();

        const overlay = document.createElement("div");
        overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:2147483647;pointer-events:none";

        const highlight = document.createElement("div");
        highlight.style.cssText = "position:absolute;border:2px solid #3b82f6;background:rgba(59,130,246,0.1);transition:all 0.1s";
        overlay.appendChild(highlight);

        const banner = document.createElement("div");
        banner.style.cssText = "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#1f2937;color:white;padding:12px 24px;border-radius:8px;font:14px sans-serif;box-shadow:0 4px 12px rgba(0,0,0,0.3);pointer-events:auto;z-index:2147483647";
        banner.textContent = `${message} (${selections.length} selected, Cmd/Ctrl+click for multi, Enter to finish, ESC to cancel)`;

        document.body.append(banner, overlay);

        const cleanup = () => {
            document.removeEventListener("mousemove", onMove, true);
            document.removeEventListener("click", onClick, true);
            document.removeEventListener("keydown", onKey, true);
            overlay.remove();
            banner.remove();
            selectedElements.forEach(el => el.style.outline = "");
        };

        const buildElementInfo = (el) => {
            const parents = [];
            let current = el.parentElement;
            while (current && current !== document.body) {
                parents.push(current.tagName.toLowerCase() +
                        (current.id ? `#${current.id}` : "") +
                        (current.className ? `.${current.className.trim().replace(/\\s+/g, ".")}` : ""));
                current = current.parentElement;
            }
            return {
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                class: el.className || null,
                text: el.textContent?.trim().slice(0, 200) || null,
                html: el.outerHTML.slice(0, 500),
                parents: parents.join(" > ")
            };
        };

        const onMove = (e) => {
            const el = document.elementFromPoint(e.clientX, e.clientY);
            if (!el || overlay.contains(el) || banner.contains(el)) return;
            const r = el.getBoundingClientRect();
            highlight.style.cssText = `position:absolute;border:2px solid #3b82f6;background:rgba(59,130,246,0.1);top:${r.top}px;left:${r.left}px;width:${r.width}px;height:${r.height}px`;
        };

        const onClick = (e) => {
            if (banner.contains(e.target)) return;
            e.preventDefault();
            e.stopPropagation();
            const el = document.elementFromPoint(e.clientX, e.clientY);
            if (!el || overlay.contains(el) || banner.contains(el)) return;

            if (e.metaKey || e.ctrlKey) {
                if (!selectedElements.has(el)) {
                    selectedElements.add(el);
                    el.style.outline = "3px solid #10b981";
                    selections.push(buildElementInfo(el));
                    banner.textContent = `${message} (${selections.length} selected, Enter to finish)`;
                }
            } else {
                cleanup();
                resolve(selections.length > 0 ? selections : buildElementInfo(el));
            }
        };

        const onKey = (e) => {
            if (e.key === "Escape") {
                cleanup();
                resolve(null);
            } else if (e.key === "Enter" && selections.length > 0) {
                cleanup();
                resolve(selections);
            }
        };

        document.addEventListener("mousemove", onMove, true);
        document.addEventListener("click", onClick, true);
        document.addEventListener("keydown", onKey, true);
    });
}
"""


async def pick_element(browser: Browser, message: str) -> Any:
    """Run interactive element picker."""
    page = await get_active_page(browser)
    return await page.evaluate(PICKER_JS, message)


# --- CLI ---

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    Playwright CLI - Browser automation from the command line.

    Uses Playwright's Chromium - does not affect your Chrome browser.

    \b
    USAGE
    -----
    cd .claude/skills/playwright/playwright_cli/
    uv run pw <command> [args]

    \b
    EXAMPLES
    --------
    # Basic workflow
    uv run pw init                        # One-time setup
    uv run pw start
    uv run pw nav https://example.com
    uv run pw screenshot --path ./page.png
    uv run pw close

    # Form testing
    uv run pw type "#email" "test@example.com"
    uv run pw click "#submit"

    # Data extraction
    uv run pw eval "document.title"
    uv run pw a11y

    # Mobile / parallel
    uv run pw start --mobile
    uv run pw start --port 9223

    Run 'uv run pw <command> --help' for detailed usage.
    """
    pass


@cli.command()
@run_async
async def init():
    """Initialize browser environment - install Playwright and Chromium."""
    console.print("[bold]Initializing browser environment...[/bold]\n")

    if check_playwright_installed():
        console.print("[green]✓[/green] Playwright Python package installed")
    else:
        console.print("[yellow]Installing Playwright...[/yellow]")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]✗ Failed to install Playwright[/red]")
            console.print(f"  {result.stderr}")
            sys.exit(1)
        console.print("[green]✓[/green] Playwright installed")

    is_installed, chromium_path = check_chromium_installed()
    if is_installed:
        console.print(f"[green]✓[/green] Chromium installed")
        console.print(f"  [dim]{chromium_path}[/dim]")
    else:
        console.print("[yellow]Installing Chromium (this may take a minute)...[/yellow]")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]✗ Failed to install Chromium[/red]")
            console.print(f"  {result.stderr}")
            sys.exit(1)

        is_installed, chromium_path = check_chromium_installed()
        if not is_installed:
            console.print(f"[red]✗ Chromium installation failed[/red]")
            sys.exit(1)
        console.print(f"[green]✓[/green] Chromium installed")
        console.print(f"  [dim]{chromium_path}[/dim]")

    # Verify
    console.print("\n[dim]Verifying installation...[/dim]")
    try:
        result = subprocess.run(
            [chromium_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            console.print(f"[green]✓[/green] Chromium verified: {version}")
        else:
            console.print("[yellow]![/yellow] Could not verify Chromium version (may still work)")
    except Exception:
        console.print("[yellow]![/yellow] Could not verify Chromium version (may still work)")

    console.print("\n[green][bold]Browser environment ready![/bold][/green]")
    console.print("\nNext steps:")
    console.print("  [cyan]pw start[/cyan]              # Start browser")
    console.print("  [cyan]pw start --port 9223[/cyan]  # Custom port")


@cli.command()
@click.option("--profile", is_flag=True, help="Use your default Chrome profile")
@click.option("--user-data-dir", type=click.Path(), help="Custom profile directory")
@click.option("--headed", is_flag=True, help="Show browser window (default: headless)")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port (default: 9222)")
@click.option("--width", type=int, default=DEFAULT_VIEWPORT_WIDTH, help="Viewport width (default: 1920)")
@click.option("--height", type=int, default=DEFAULT_VIEWPORT_HEIGHT, help="Viewport height (default: 1080)")
@click.option("--mobile", is_flag=True, help="Mobile mode: iPhone viewport, touch events, mobile UA")
@run_async
async def start(profile: bool, user_data_dir: Optional[str], headed: bool, port: int, width: int, height: int, mobile: bool):
    """Start Playwright Chromium with remote debugging enabled."""
    chromium_path = ensure_initialized()

    if is_port_in_use(port):
        console.print(f"[red]✗ Port {port} is already in use[/red]")
        console.print(f"\n[yellow]Options:[/yellow]")
        console.print(f"  1. Use different port: [cyan]pw start --port {port + 1}[/cyan]")
        console.print(f"  2. Close existing: [cyan]pw close --port {port}[/cyan]")
        sys.exit(1)

    # Determine profile directory
    if user_data_dir:
        profile_dir = Path(user_data_dir)
    elif profile:
        import shutil
        if sys.platform == "darwin":
            default_profile = Path.home() / "Library/Application Support/Google/Chrome"
        elif sys.platform == "win32":
            default_profile = Path.home() / "AppData/Local/Google/Chrome/User Data"
        else:
            default_profile = Path.home() / ".config/google-chrome"

        profile_dir = Path.home() / ".cache/playwright-browser-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        if not (profile_dir / "Default").exists():
            console.print("Copying Chrome profile (first time only)...")
            shutil.copytree(default_profile, profile_dir, dirs_exist_ok=True)
    else:
        profile_dir = Path.home() / f".cache/playwright-browser-{port}"
        profile_dir.mkdir(parents=True, exist_ok=True)

    mode = "headed" if headed else "headless"
    device_mode = "mobile (iPhone)" if mobile else "desktop"
    viewport = f"{MOBILE_VIEWPORT_WIDTH}x{MOBILE_VIEWPORT_HEIGHT}" if mobile else f"{width}x{height}"

    console.print(f"Starting Playwright Chromium ({mode}, {device_mode}) on port {port}...")
    console.print(f"  [dim]Using: {chromium_path}[/dim]")
    console.print(f"  [dim]Viewport: {viewport}[/dim]")
    if mobile:
        console.print(f"  [dim]Touch events: enabled[/dim]")
        console.print(f"  [dim]User agent: iPhone/Safari[/dim]")

    start_browser_process(chromium_path, port, headed, profile_dir, width, height, mobile)

    if await wait_for_browser(port):
        profile_msg = " with your profile" if profile or user_data_dir else ""
        console.print(f"[green]✓ Browser started on port {port} ({mode}){profile_msg}[/green]")
        console.print(f"[dim]Your Chrome browser is unaffected[/dim]")
    else:
        console.print(f"\n[red]✗ Failed to start browser on port {port}[/red]")
        console.print(f"\n[yellow]Troubleshooting:[/yellow]")
        console.print(f"  1. Verify init: [cyan]pw init[/cyan]")
        console.print(f"  2. Try different port: [cyan]pw start --port {port + 1}[/cyan]")
        sys.exit(1)


@cli.command()
@click.argument("url")
@click.option("--new", is_flag=True, help="Open in new tab")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def nav(url: str, new: bool, port: int):
    """Navigate to a URL."""
    try:
        pw, browser_conn = await connect(port)
        try:
            await navigate(browser_conn, url, new_tab=new)
            action = "Opened" if new else "Navigated to"
            console.print(f"[green]✓ {action}: {url}[/green]")
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        console.print(f"\n  Run: [cyan]pw start --port {port}[/cyan]")
        sys.exit(1)


@cli.command(name="eval")
@click.argument("code")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def eval_cmd(code: str, port: int):
    """Execute JavaScript in the active page."""
    try:
        pw, browser_conn = await connect(port)
        try:
            result = await evaluate_js(browser_conn, code)
            if isinstance(result, list):
                for i, item in enumerate(result):
                    if i > 0:
                        click.echo()
                    if isinstance(item, dict):
                        for key, value in item.items():
                            click.echo(f"{key}: {value}")
                    else:
                        click.echo(item)
            elif isinstance(result, dict):
                for key, value in result.items():
                    click.echo(f"{key}: {value}")
            else:
                click.echo(result)
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        console.print(f"\n  Run: [cyan]pw start --port {port}[/cyan]")
        sys.exit(1)


@cli.command()
@click.option("--path", type=click.Path(), help="Save to specific path")
@click.option("--full", is_flag=True, help="Full page screenshot")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def screenshot(path: Optional[str], full: bool, port: int):
    """Take a screenshot of the active page."""
    try:
        pw, browser_conn = await connect(port)
        try:
            filepath = await take_screenshot(browser_conn, path, full)
            console.print(f"[green]✓ Screenshot saved:[/green] {filepath}")
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        console.print(f"\n  Run: [cyan]pw start --port {port}[/cyan]")
        sys.exit(1)


@cli.command(name="click")
@click.argument("selector")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def click_cmd(selector: str, port: int):
    """Click an element matching the selector."""
    try:
        pw, browser_conn = await connect(port)
        try:
            await click_element(browser_conn, selector)
            console.print(f"[green]✓ Clicked:[/green] {selector}")
        except Exception as e:
            console.print(f"[red]✗ Failed to click '{selector}'[/red]")
            console.print(f"  Error: {e}")
            sys.exit(1)
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.command(name="type")
@click.argument("selector")
@click.argument("text")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def type_cmd(selector: str, text: str, port: int):
    """Type text into an input field."""
    try:
        pw, browser_conn = await connect(port)
        try:
            await type_text(browser_conn, selector, text)
            console.print(f"[green]✓ Typed into '{selector}':[/green] {text}")
        except Exception as e:
            console.print(f"[red]✗ Failed to type into '{selector}'[/red]")
            console.print(f"  Error: {e}")
            sys.exit(1)
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.command(name="press")
@click.argument("key")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def press_cmd(key: str, port: int):
    """Press a keyboard key (Tab, Enter, Escape, etc.)."""
    try:
        pw, browser_conn = await connect(port)
        try:
            await press_key(browser_conn, key)
            console.print(f"[green]✓ Pressed:[/green] {key}")
        except Exception as e:
            console.print(f"[red]✗ Failed to press '{key}'[/red]")
            console.print(f"  Error: {e}")
            sys.exit(1)
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("direction", type=click.Choice(["up", "down", "top", "bottom"]))
@click.option("--amount", type=int, default=500, help="Amount to scroll (pixels)")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def scroll(direction: str, amount: int, port: int):
    """Scroll the page (up/down/top/bottom)."""
    try:
        pw, browser_conn = await connect(port)
        try:
            await scroll_page(browser_conn, direction, amount)
            console.print(f"[green]✓ Scrolled {direction}[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to scroll[/red]")
            console.print(f"  Error: {e}")
            sys.exit(1)
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def cookies(port: int):
    """Get cookies from the active page as JSON."""
    try:
        pw, browser_conn = await connect(port)
        try:
            data = await get_cookies(browser_conn)
            click.echo(json.dumps(data, indent=2))
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def a11y(port: int):
    """Get the accessibility tree snapshot."""
    try:
        pw, browser_conn = await connect(port)
        try:
            snapshot = await get_accessibility_tree(browser_conn)
            click.echo(json.dumps(snapshot, indent=2))
        except Exception as e:
            console.print(f"[red]✗ Failed to get accessibility snapshot[/red]")
            console.print(f"  Error: {e}")
            sys.exit(1)
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--full", is_flag=True, help="Return full HTML instead of simplified")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def dom(full: bool, port: int):
    """Get the DOM structure (simplified or full HTML)."""
    try:
        pw, browser_conn = await connect(port)
        try:
            structure = await get_dom(browser_conn, full)
            if isinstance(structure, str):
                click.echo(structure)
            else:
                click.echo(json.dumps(structure, indent=2))
        except Exception as e:
            console.print(f"[red]✗ Failed to get DOM[/red]")
            console.print(f"  Error: {e}")
            sys.exit(1)
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("message")
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def pick(message: str, port: int):
    """Interactive element picker - click elements to inspect them."""
    try:
        pw, browser_conn = await connect(port)
        try:
            result = await pick_element(browser_conn, message)
            if result is None:
                console.print("[yellow]Cancelled[/yellow]")
                return
            if isinstance(result, list):
                for i, item in enumerate(result):
                    if i > 0:
                        click.echo()
                    for key, value in item.items():
                        click.echo(f"{key}: {value}")
            else:
                for key, value in result.items():
                    click.echo(f"{key}: {value}")
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def status(port: int):
    """Check if browser is running and accessible."""
    try:
        pw, browser_conn = await connect(port)
        try:
            contexts = browser_conn.contexts
            if contexts:
                pages = contexts[0].pages
                console.print(f"[green]✓ Browser is running on port {port}[/green]")
                console.print(f"  Open tabs: {len(pages)}")
                if pages:
                    current_page = pages[-1]
                    console.print(f"  Current URL: {current_page.url}")
        finally:
            await browser_conn.close()
            await pw.stop()
    except BrowserConnectionError:
        console.print(f"[red]✗ Browser not running on port {port}[/red]")
        console.print(f"  Run: [cyan]pw start --port {port}[/cyan]")


@cli.command()
@click.option("--port", type=int, default=DEFAULT_PORT, help="CDP port")
@run_async
async def close(port: int):
    """Close the browser and terminate the process."""
    try:
        pw, browser_conn = await connect(port)
        await browser_conn.close()
        await pw.stop()
    except BrowserConnectionError:
        pass

    if kill_browser_on_port(port):
        console.print(f"[green]✓ Browser on port {port} closed[/green]")
    else:
        console.print(f"[green]✓ No browser running on port {port}[/green]")


if __name__ == "__main__":
    cli()
