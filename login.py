from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def parse_cookie_source(raw: str | None) -> dict[str, str]:
    if raw is None or not raw.strip():
        return {}

    text = raw.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text

    return cookie_map_from_data(parsed)


def cookie_map_from_data(data: Any) -> dict[str, str]:
    if isinstance(data, dict):
        if "name" in data and "value" in data:
            return {str(data["name"]): str(data["value"])}
        return {str(key): str(value) for key, value in data.items()}

    if isinstance(data, list):
        cookies: dict[str, str] = {}
        for item in data:
            if isinstance(item, dict) and "name" in item and "value" in item:
                cookies[str(item["name"])] = str(item["value"])
        return cookies

    if isinstance(data, str):
        cookies: dict[str, str] = {}
        for part in data.split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name:
                cookies[name] = value
        return cookies

    return {}


def extract_auth_from_cookie_map(cookie_map: dict[str, str]) -> tuple[str, str | None, str | None]:
    bduss = cookie_map.get("BDUSS") or cookie_map.get("BDUSS_BFESS") or ""
    stoken = cookie_map.get("STOKEN") or cookie_map.get("stoken")
    baiduid = cookie_map.get("BAIDUID") or cookie_map.get("BAIDUID_BFESS")
    return bduss, stoken, baiduid


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


def _load_cookie_source() -> str | None:
    inline_cookies = os.getenv("TIEBA_COOKIES", "").strip()
    if inline_cookies:
        return inline_cookies

    cookie_file = os.getenv("TIEBA_COOKIE_FILE", "").strip() or "tieba_cookies.json"
    cookie_path = Path(cookie_file)
    if cookie_path.is_file():
        return cookie_path.read_text(encoding="utf-8")
    return None


@dataclass(slots=True)
class Settings:
    bduss: str
    stoken: str
    baiduid: str | None = None
    cookies: dict[str, str] | None = None
    use_official_msign: bool = True
    slow_mode: bool = False
    sign_delay_ms: int = 2000
    fail_on_partial_failure: bool = False
    request_timeout: int = 30
    dry_run: bool = False
    device_seed: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        cookie_map = parse_cookie_source(_load_cookie_source())
        cookie_bduss, cookie_stoken, cookie_baiduid = extract_auth_from_cookie_map(cookie_map)

        bduss = os.getenv("TIEBA_BDUSS", "").strip() or cookie_bduss
        stoken = os.getenv("TIEBA_STOKEN", "").strip() or (cookie_stoken or "")
        if not bduss:
            raise ValueError(
                "Missing login material. Provide TIEBA_COOKIES, TIEBA_BDUSS, "
                "or place tieba_cookies.json in the project root."
            )
        if not stoken:
            raise ValueError(
                "Missing STOKEN. Full mobile API sign-in requires both BDUSS and STOKEN. "
                "Prefer using TIEBA_COOKIES exported from the local QR-login helper."
            )

        return cls(
            bduss=bduss,
            stoken=stoken,
            baiduid=os.getenv("TIEBA_BAIDUID", "").strip() or cookie_baiduid,
            cookies=cookie_map or None,
            use_official_msign=_get_bool("TIEBA_USE_OFFICIAL_MSIGN", True),
            slow_mode=_get_bool("TIEBA_SLOW_MODE", False),
            sign_delay_ms=_get_int("TIEBA_SIGN_DELAY_MS", 2000),
            fail_on_partial_failure=_get_bool("TIEBA_FAIL_ON_PARTIAL_FAILURE", False),
            request_timeout=_get_int("TIEBA_REQUEST_TIMEOUT", 30),
            dry_run=_get_bool("TIEBA_DRY_RUN", False),
            device_seed=os.getenv("TIEBA_DEVICE_SEED"),
        )


def _find_browser_path() -> str | None:
    configured_path = os.getenv("TIEBA_BROWSER_PATH", "").strip()
    if configured_path and Path(configured_path).is_file():
        return configured_path

    for browser_name in ("chrome", "chromium", "chromium-browser", "msedge"):
        browser_path = shutil.which(browser_name)
        if browser_path:
            return browser_path

    candidate_paths = []
    for base_dir in (
        os.getenv("PROGRAMFILES"),
        os.getenv("PROGRAMFILES(X86)"),
        os.getenv("LOCALAPPDATA"),
    ):
        if not base_dir:
            continue
        candidate_paths.extend(
            [
                Path(base_dir) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(base_dir) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ]
        )

    for candidate_path in candidate_paths:
        if candidate_path.is_file():
            return str(candidate_path)
    return None


def export_cookies() -> int:
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError:
        print("DrissionPage is not installed. Run: python -m pip install -r requirements-login.txt")
        return 1

    options = ChromiumOptions()
    browser_path = _find_browser_path()
    if browser_path:
        options.set_browser_path(browser_path)
    else:
        print(
            "Browser executable not found automatically. "
            "Set TIEBA_BROWSER_PATH to your Chrome/Edge executable, "
            "for example: C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
        )
        return 1
    options.set_argument("--disable-extensions")
    options.set_argument("--disable-component-extensions-with-background-pages")
    options.set_argument("--disable-default-apps")
    options.set_argument("--disable-sync")
    options.set_argument("--no-first-run")
    options.set_argument("--no-default-browser-check")
    user_data_dir = Path(tempfile.gettempdir()) / f"tieba-sign-qr-{int(time.time())}"
    options.set_user_data_path(str(user_data_dir))
    options.auto_port()

    page = None
    url = "https://tieba.baidu.com/"
    output = Path("tieba_cookies.json")
    timeout_seconds = 300
    poll_interval = 2

    try:
        try:
            page = ChromiumPage(options)
        except FileNotFoundError:
            print(
                "Failed to start the browser. "
                "Check TIEBA_BROWSER_PATH and make sure the browser executable exists."
            )
            return 1
        page.get(url)
        print("Browser opened. Please complete Tieba QR-code login in the visible window.")
        print(f"Waiting up to {timeout_seconds} seconds for login cookies...")

        cookies_list = []
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            cookies_list = page.cookies(all_info=True)
            cookie_map = cookie_map_from_data(cookies_list)
            bduss, stoken, _ = extract_auth_from_cookie_map(cookie_map)
            if bduss:
                time.sleep(3)
                cookies_list = page.cookies(all_info=True)
                cookie_map = cookie_map_from_data(cookies_list)
                bduss, stoken, _ = extract_auth_from_cookie_map(cookie_map)
                output.write_text(json.dumps(cookies_list, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Saved {len(cookies_list)} cookies to {output.resolve()}")
                print(f"BDUSS found: {'yes' if bduss else 'no'}")
                print(f"STOKEN found: {'yes' if stoken else 'no'}")
                if not stoken:
                    print("Warning: STOKEN was not found in exported cookies. Full mobile API sign-in may not work.")
                return 0
            time.sleep(poll_interval)

        print("Timed out waiting for login cookies. No file was saved.")
        return 1
    finally:
        if page is not None:
            page.quit()
        shutil.rmtree(user_data_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(export_cookies())
