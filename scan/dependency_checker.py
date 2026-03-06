#!/usr/bin/env python3
"""
Dependency Checker for VPT Scanner
===================================
Checks all required dependencies at startup and provides clear instructions
for any missing components.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class DependencyStatus(NamedTuple):
    """Status of a dependency check."""
    name: str
    satisfied: bool
    version: str | None
    error: str | None
    fix_instruction: str


def check_python_version() -> DependencyStatus:
    """Check Python version is >= 3.10."""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        return DependencyStatus(
            name="Python 3.10+",
            satisfied=True,
            version=version,
            error=None,
            fix_instruction=""
        )
    return DependencyStatus(
        name="Python 3.10+",
        satisfied=False,
        version=version,
        error=f"Python {version} is too old",
        fix_instruction="Install Python 3.10 or higher: sudo apt install python3.10"
    )


def check_flask() -> DependencyStatus:
    """Check Flask is installed."""
    try:
        import flask
        try:
            from importlib.metadata import version as get_version
            flask_version = get_version("flask")
        except Exception:
            flask_version = getattr(flask, '__version__', 'installed')
        return DependencyStatus(
            name="Flask",
            satisfied=True,
            version=flask_version,
            error=None,
            fix_instruction=""
        )
    except ImportError as e:
        return DependencyStatus(
            name="Flask",
            satisfied=False,
            version=None,
            error=str(e),
            fix_instruction="pip install flask"
        )


def check_playwright() -> DependencyStatus:
    """Check Playwright is installed."""
    try:
        from playwright.sync_api import sync_playwright
        return DependencyStatus(
            name="Playwright",
            satisfied=True,
            version="installed",
            error=None,
            fix_instruction=""
        )
    except ImportError as e:
        return DependencyStatus(
            name="Playwright",
            satisfied=False,
            version=None,
            error=str(e),
            fix_instruction="pip install playwright"
        )


def check_playwright_browser() -> DependencyStatus:
    """Check Playwright Chromium browser is installed."""
    # Check if chromium exists in playwright cache
    home = Path.home()
    playwright_cache = home / ".cache" / "ms-playwright"
    
    if not playwright_cache.exists():
        return DependencyStatus(
            name="Playwright Chromium",
            satisfied=False,
            version=None,
            error="Playwright browser cache not found",
            fix_instruction="playwright install chromium"
        )
    
    # Look for chromium installation
    chromium_dirs = list(playwright_cache.glob("chromium*"))
    if chromium_dirs:
        return DependencyStatus(
            name="Playwright Chromium",
            satisfied=True,
            version=chromium_dirs[0].name,
            error=None,
            fix_instruction=""
        )
    
    return DependencyStatus(
        name="Playwright Chromium",
        satisfied=False,
        version=None,
        error="Chromium browser not installed",
        fix_instruction="playwright install chromium"
    )


def check_chromium_deps() -> DependencyStatus:
    """Check system library for Chromium (libnspr4)."""
    # Try to find libnspr4.so
    lib_paths = [
        "/usr/lib/x86_64-linux-gnu/libnspr4.so",
        "/usr/lib/libnspr4.so",
        "/lib/x86_64-linux-gnu/libnspr4.so",
    ]
    
    for path in lib_paths:
        if os.path.exists(path):
            return DependencyStatus(
                name="Chromium System Libraries",
                satisfied=True,
                version="installed",
                error=None,
                fix_instruction=""
            )
    
    # Also check with ldconfig
    try:
        result = subprocess.run(
            ["ldconfig", "-p"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "libnspr4.so" in result.stdout:
            return DependencyStatus(
                name="Chromium System Libraries",
                satisfied=True,
                version="installed",
                error=None,
                fix_instruction=""
            )
    except Exception:
        pass
    
    return DependencyStatus(
        name="Chromium System Libraries",
        satisfied=False,
        version=None,
        error="libnspr4.so not found (required for Playwright)",
        fix_instruction="sudo apt-get install libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2t64"
    )


def check_google_genai() -> DependencyStatus:
    """Check Google GenAI is installed."""
    try:
        from google import genai
        return DependencyStatus(
            name="Google GenAI",
            satisfied=True,
            version="installed",
            error=None,
            fix_instruction=""
        )
    except ImportError as e:
        return DependencyStatus(
            name="Google GenAI",
            satisfied=False,
            version=None,
            error=str(e),
            fix_instruction="pip install google-genai"
        )


def check_dotenv() -> DependencyStatus:
    """Check python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
        return DependencyStatus(
            name="python-dotenv",
            satisfied=True,
            version="installed",
            error=None,
            fix_instruction=""
        )
    except ImportError as e:
        return DependencyStatus(
            name="python-dotenv",
            satisfied=False,
            version=None,
            error=str(e),
            fix_instruction="pip install python-dotenv"
        )


def check_requests() -> DependencyStatus:
    """Check requests is installed."""
    try:
        import requests
        return DependencyStatus(
            name="requests",
            satisfied=True,
            version=requests.__version__,
            error=None,
            fix_instruction=""
        )
    except ImportError as e:
        return DependencyStatus(
            name="requests",
            satisfied=False,
            version=None,
            error=str(e),
            fix_instruction="pip install requests"
        )


def check_google_api_key() -> DependencyStatus:
    """Check if GOOGLE_API_KEY is configured."""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    
    if api_key:
        # Mask most of the key for display
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "****"
        return DependencyStatus(
            name="GOOGLE_API_KEY",
            satisfied=True,
            version=masked,
            error=None,
            fix_instruction=""
        )
    
    return DependencyStatus(
        name="GOOGLE_API_KEY",
        satisfied=False,
        version=None,
        error="Not configured (AI features will be disabled)",
        fix_instruction="Add GOOGLE_API_KEY=your-key to .env file. Get a key from: https://makersuite.google.com/app/apikey"
    )


def check_all_dependencies(include_optional: bool = True) -> tuple[list[DependencyStatus], bool]:
    """
    Check all dependencies.
    
    Returns:
        Tuple of (list of status objects, all_required_satisfied)
    """
    # Required dependencies (app won't start without these)
    required_checks = [
        check_python_version,
        check_flask,
        check_dotenv,
    ]
    
    # Optional but recommended (app will start but features may be limited)
    optional_checks = [
        check_playwright,
        check_playwright_browser,
        check_chromium_deps,
        check_google_genai,
        check_requests,
        check_google_api_key,
    ]
    
    results = []
    all_required_ok = True
    
    for check_func in required_checks:
        status = check_func()
        status = status._replace(name=f"[REQUIRED] {status.name}")
        results.append(status)
        if not status.satisfied:
            all_required_ok = False
    
    if include_optional:
        for check_func in optional_checks:
            status = check_func()
            status = status._replace(name=f"[OPTIONAL] {status.name}")
            results.append(status)
    
    return results, all_required_ok


def print_dependency_report(results: list[DependencyStatus], all_ok: bool) -> None:
    """Print a formatted dependency report to stdout."""
    print("\n" + "=" * 70)
    print("VPT Scanner - Dependency Check")
    print("=" * 70 + "\n")
    
    for status in results:
        if status.satisfied:
            icon = "✓"
            color = "\033[92m"  # Green
        else:
            if "[REQUIRED]" in status.name:
                icon = "✗"
                color = "\033[91m"  # Red
            else:
                icon = "⚠"
                color = "\033[93m"  # Yellow
        
        reset = "\033[0m"
        
        version_str = f" (v{status.version})" if status.version else ""
        print(f"{color}{icon} {status.name}{version_str}{reset}")
        
        if not status.satisfied:
            if status.error:
                print(f"    Error: {status.error}")
            if status.fix_instruction:
                print(f"    Fix: {status.fix_instruction}")
            print()
    
    print("-" * 70)
    
    if all_ok:
        print("\033[92m✓ All required dependencies satisfied!\033[0m")
    else:
        print("\033[91m✗ Some required dependencies are missing. Please fix them before starting.\033[0m")
        print("\nQuick fix: Run the install script:")
        print("  ./install.sh")
    
    print()


def verify_dependencies(exit_on_failure: bool = True, verbose: bool = True) -> bool:
    """
    Verify all dependencies are satisfied.
    
    Args:
        exit_on_failure: If True, exit the program if required deps are missing
        verbose: If True, print the dependency report
    
    Returns:
        True if all required dependencies are satisfied
    """
    results, all_ok = check_all_dependencies()
    
    if verbose:
        print_dependency_report(results, all_ok)
    
    if not all_ok and exit_on_failure:
        sys.exit(1)
    
    return all_ok


def get_missing_dependencies() -> list[str]:
    """Get list of fix instructions for missing dependencies."""
    results, _ = check_all_dependencies()
    return [status.fix_instruction for status in results if not status.satisfied and status.fix_instruction]


if __name__ == "__main__":
    # When run directly, just check and report
    verify_dependencies(exit_on_failure=False)
