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
            "return document.getElementById('root')"
            " && document.getElementById('root').children.length > 0"
        )
    )


def get_visible_inputs(drv):
    inputs = drv.find_elements(By.CSS_SELECTOR, "input")
    return [
        input_element
        for input_element in inputs
        if input_element.is_displayed()
    ]


def wait_for_transfer_form(drv, seconds=5):
    return WebDriverWait(drv, seconds).until(
        lambda driver: get_visible_inputs(driver)
        if len(get_visible_inputs(driver)) >= 2
        else False
    )


def get_clickable_ancestor(drv, element):
    return drv.execute_script(
        """
        let element = arguments[0];

        while (element && element !== document.body) {
            const role = element.getAttribute("role");
            const tagName = element.tagName.toLowerCase();
            const cursor = window.getComputedStyle(element).cursor;

            if (
                role === "button" ||
                tagName === "button" ||
                tagName === "a" ||
                cursor === "pointer" ||
                element.onclick
            ) {
                return element;
            }

            element = element.parentElement;
        }

        return arguments[0];
        """,
        element
    )


def click_element(drv, element):
    drv.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});",
        element
    )

    try:
        ActionChains(drv).move_to_element(element).click().perform()
    except Exception:
        drv.execute_script("arguments[0].click();", element)


def find_account_elements(drv):
    elements = []

    for selector in ["h2", "h3", "p", "span", "div"]:
        for element in drv.find_elements(By.CSS_SELECTOR, selector):
            text = element.text.strip().lower()

            if not text:
                continue

            if "руб" in text or "rub" in text:
                elements.append(element)

    return elements


def select_account_with_transfer_form(drv):
    account_elements = wait(drv).until(
        lambda driver: find_account_elements(driver)
    )

    for account_element in account_elements:
        try:
            clickable_element = get_clickable_ancestor(drv, account_element)
            click_element(drv, clickable_element)
            wait_for_transfer_form(drv, seconds=4)
            return
        except Exception:
            continue

    fallback_clickable_elements = drv.find_elements(
        By.CSS_SELECTOR,
        "[role='button'], button, a"
    )

    for clickable_element in fallback_clickable_elements:
        try:
            click_element(drv, clickable_element)
            wait_for_transfer_form(drv, seconds=4)
            return
        except Exception:
            continue

    raise AssertionError(
        "Transfer form was not opened after clicking account elements"
    )


def get_inputs(drv):
    return wait(drv).until(
        lambda driver: get_visible_inputs(driver)
        if len(get_visible_inputs(driver)) >= 2
        else False
    )


def find_card_input(drv):
    return get_inputs(drv)[0]


def find_amount_input(drv):
    return get_inputs(drv)[1]


def set_input_value(element, value):
    element.click()
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(Keys.BACKSPACE)
    element.send_keys(value)


def find_transfer_buttons(drv):
    return [
        button
        for button in drv.find_elements(By.CSS_SELECTOR, "button")
        if "Перевести" in button.text
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