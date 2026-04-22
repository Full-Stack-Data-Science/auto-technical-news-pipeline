from __future__ import annotations

import logging
from typing import Optional, List, Callable, TypeVar, Union

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

T = TypeVar("T")
SearchContext = Union[WebDriver, WebElement]


# =========================
# Core wait utilities
# =========================

def wait_for(driver: WebDriver, timeout: int = DEFAULT_TIMEOUT) -> WebDriverWait:
    return WebDriverWait(driver, timeout)


def wait_for_page_load(driver: WebDriver, timeout: int = DEFAULT_TIMEOUT):
    wait_for(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def safe_get(driver: WebDriver, url: str, timeout: int = DEFAULT_TIMEOUT):
    driver.get(url)
    wait_for_page_load(driver, timeout)


# =========================
# Generic finders (driver + element)
# =========================

def find(
    ctx: SearchContext,
    by: str,
    selector: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> WebElement:
    """
    Find a single element from driver or element context.
    """
    if isinstance(ctx, WebDriver):
        return wait_for(ctx, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    return ctx.find_element(by, selector)


def find_all(
    ctx: SearchContext,
    by: str,
    selector: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[WebElement]:
    """
    Find all elements from driver or element context.
    """
    if isinstance(ctx, WebDriver):
        wait_for(ctx, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    return ctx.find_elements(by, selector)


def try_find(
    ctx: SearchContext,
    by: str,
    selector: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[WebElement]:
    try:
        return find(ctx, by, selector, timeout)
    except Exception as e:
        logger.debug(f"Element not found: {selector} ({e})")
        return None


# =========================
# Safe getters
# =========================

def get_text(
    ctx: SearchContext,
    by: str,
    selector: str,
    timeout: int = DEFAULT_TIMEOUT,
    fallback: str = "",
) -> str:
    el = try_find(ctx, by, selector, timeout)
    return el.text.strip() if el else fallback


def get_attr(
    ctx: SearchContext,
    by: str,
    selector: str,
    attr: str,
    timeout: int = DEFAULT_TIMEOUT,
    fallback: str = "",
) -> str:
    el = try_find(ctx, by, selector, timeout)
    return (el.get_attribute(attr) or fallback) if el else fallback


def attr(
    el: WebElement,
    name: str,
    fallback: str = "",
) -> str:
    try:
        return el.get_attribute(name) or fallback
    except Exception:
        return fallback


# =========================
# High-level helpers
# =========================

def wait_for_all(
    driver: WebDriver,
    by: str,
    selector: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[WebElement]:
    """
    Wait until at least one element exists, then return all.
    More stable than presence_of_all_elements_located.
    """
    wait_for(driver, timeout).until(
        EC.presence_of_element_located((by, selector))
    )
    return driver.find_elements(by, selector)


def first(elements: List[WebElement]) -> Optional[WebElement]:
    return elements[0] if elements else None


def map_elements(
    elements: List[WebElement],
    fn: Callable[[WebElement], T],
) -> List[T]:
    return [fn(el) for el in elements]


# =========================
# Retry utility (important for dynamic DOM like X)
# =========================

def retry_stale(fn: Callable[[], T], retries: int = 2) -> T:
    """
    Retry function if stale element exception occurs.
    """
    for i in range(retries):
        try:
            return fn()
        except StaleElementReferenceException:
            if i == retries - 1:
                raise