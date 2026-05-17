from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="session")
def app_url():
    dist_dir = Path(__file__).resolve().parents[1] / "dist"

    handler = partial(
        QuietHTTPRequestHandler,
        directory=str(dist_dir)
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{server.server_port}/"

    server.shutdown()
    server.server_close()


@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    drv = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    yield drv
    drv.quit()


def wait(drv, seconds=10):
    return WebDriverWait(drv, seconds)


def open_app(drv, app_url):
    drv.get(app_url)

    wait(drv).until(
        lambda driver: driver.execute_script(
            "return document.readyState"
        ) == "complete"
    )

    wait(drv).until(
        lambda driver: driver.execute_script(
            """
            const root = document.getElementById('root');
            return root && root.children.length > 0;
            """
        )
    )


def get_inputs(drv):
    return drv.find_elements(By.CSS_SELECTOR, "input")


def wait_for_transfer_form(drv, seconds=5):
    return WebDriverWait(drv, seconds).until(
        lambda driver: get_inputs(driver)
        if len(get_inputs(driver)) >= 2
        else False
    )


def dispatch_real_click(drv, element):
    drv.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
        element
    )

    try:
        ActionChains(drv).move_to_element(element).pause(0.1).click().perform()
    except Exception:
        pass

    drv.execute_script(
        """
        const element = arguments[0];

        for (const eventName of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
            element.dispatchEvent(
                new MouseEvent(eventName, {
                    bubbles: true,
                    cancelable: true,
                    view: window
                })
            );
        }
        """,
        element
    )


def find_clickable_ancestor(drv, element):
    return drv.execute_script(
        """
        let element = arguments[0];

        while (element && element !== document.body) {
            const role = element.getAttribute('role');
            const tag = element.tagName.toLowerCase();
            const cursor = window.getComputedStyle(element).cursor;

            if (
                role === 'button' ||
                tag === 'button' ||
                tag === 'a' ||
                cursor === 'pointer'
            ) {
                return element;
            }

            element = element.parentElement;
        }

        return arguments[0];
        """,
        element
    )


def find_account_related_elements(drv):
    result = []

    selectors = [
        "h1",
        "h2",
        "h3",
        "p",
        "span",
        "[id*='rub']",
        "[id*='usd']",
        "[id*='euro']",
        "[role='button']",
        "button",
        "a"
    ]

    for selector in selectors:
        for element in drv.find_elements(By.CSS_SELECTOR, selector):
            try:
                text = element.text.strip().lower()
                element_id = (element.get_attribute("id") or "").lower()
                class_name = (element.get_attribute("class") or "").lower()

                haystack = f"{text} {element_id} {class_name}"

                if (
                    "руб" in haystack or
                    "rub" in haystack or
                    "доллар" in haystack or
                    "usd" in haystack or
                    "евро" in haystack or
                    "euro" in haystack
                ):
                    result.append(element)
            except Exception:
                continue

    unique = []
    seen = set()

    for element in result:
        try:
            element_id = element.id
            if element_id not in seen:
                seen.add(element_id)
                unique.append(element)
        except Exception:
            continue

    return unique


def try_open_form_by_clicking(drv):
    if len(get_inputs(drv)) >= 2:
        return True

    account_elements = find_account_related_elements(drv)

    for account_element in account_elements:
        try:
            clickable = find_clickable_ancestor(drv, account_element)
            dispatch_real_click(drv, clickable)
            wait_for_transfer_form(drv, seconds=3)
            return True
        except Exception:
            continue

    clickables = drv.find_elements(
        By.CSS_SELECTOR,
        "[role='button'], button, a, .g-card, .g-card_clickable"
    )

    for clickable in clickables:
        try:
            dispatch_real_click(drv, clickable)
            wait_for_transfer_form(drv, seconds=3)
            return True
        except Exception:
            continue

    return False


def try_open_form_by_routes(drv):
    candidate_paths = [
        "/",
        "/rub",
        "/rub/",
        "/ruble",
        "/ruble/",
        "/rubles",
        "/rubles/",
        "/rublik",
        "/rublik/",
        "/account/rub",
        "/account/rub/",
        "/accounts/rub",
        "/accounts/rub/",
        "/transfer",
        "/transfer/",
        "/transfer/rub",
        "/transfer/rub/",
        "/transfer?currency=rub",
        "/transfer?account=rub",
        "/?currency=rub",
        "/?account=rub",
        "/#/",
        "/#/rub",
        "/#/transfer",
        "/#/transfer/rub",
    ]

    for path in candidate_paths:
        try:
            drv.execute_script(
                """
                window.history.pushState({}, '', arguments[0]);
                window.dispatchEvent(new PopStateEvent('popstate'));
                """,
                path
            )

            wait_for_transfer_form(drv, seconds=2)
            return True
        except Exception:
            continue

    return False


def debug_page_state(drv):
    buttons = []

    for element in drv.find_elements(By.CSS_SELECTOR, "[role='button'], button, a"):
        try:
            buttons.append({
                "tag": element.tag_name,
                "text": element.text,
                "id": element.get_attribute("id"),
                "class": element.get_attribute("class"),
                "href": element.get_attribute("href"),
            })
        except Exception:
            continue

    return (
        f"URL: {drv.current_url}\n"
        f"TITLE: {drv.title}\n"
        f"INPUTS_COUNT: {len(get_inputs(drv))}\n"
        f"CLICKABLES: {buttons}\n"
        f"BODY:\n{drv.find_element(By.TAG_NAME, 'body').text}\n"
        f"HTML:\n{drv.page_source}"
    )


def select_account_with_transfer_form(drv):
    if len(get_inputs(drv)) >= 2:
        return

    if try_open_form_by_clicking(drv):
        return

    if try_open_form_by_routes(drv):
        return

    raise AssertionError(
        "Transfer form was not opened.\n\n" + debug_page_state(drv)
    )


def find_card_input(drv):
    inputs = wait_for_transfer_form(drv)
    return inputs[0]


def find_amount_input(drv):
    inputs = wait_for_transfer_form(drv)
    return inputs[1]


def set_input_value(element, value):
    element.click()
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(Keys.BACKSPACE)
    element.send_keys(value)


def find_transfer_buttons(drv):
    buttons = drv.find_elements(By.CSS_SELECTOR, "button")

    return [
        button
        for button in buttons
        if "перевести" in button.text.strip().lower()
    ]


def test_bug_001_card_number_must_be_16_digits(driver, app_url):
    open_app(driver, app_url)
    select_account_with_transfer_form(driver)

    card_input = find_card_input(driver)
    set_input_value(card_input, "12345678901234567")

    normalized = card_input.get_attribute("value").replace(" ", "")

    assert len(normalized) == 16, (
        "Card number must be limited to 16 digits"
    )


def test_bug_002_negative_transfer_must_be_blocked(driver, app_url):
    open_app(driver, app_url)
    select_account_with_transfer_form(driver)

    card_input = find_card_input(driver)
    set_input_value(card_input, "1234567890123456")

    amount_input = find_amount_input(driver)
    set_input_value(amount_input, "-1000")

    transfer_buttons = find_transfer_buttons(driver)

    has_enabled_transfer_button = any(
        button.is_displayed() and button.is_enabled()
        for button in transfer_buttons
    )

    assert not has_enabled_transfer_button, (
        "Transfer button must be disabled for negative amount"
    )