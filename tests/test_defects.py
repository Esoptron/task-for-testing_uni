from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import time

import pytest
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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


def open_app(driver, app_url):
    driver.get(app_url)
    time.sleep(2)


def get_account_cards(driver):
    return driver.find_elements(By.CSS_SELECTOR, ".g-card_clickable")


def get_inputs(driver):
    return driver.find_elements(By.CSS_SELECTOR, "input")


def click_first_available_account(driver):
    cards = get_account_cards(driver)

    assert len(cards) > 0, (
        "Account cards must be visible on the main page"
    )

    for card in cards:
        ActionChains(driver).move_to_element(card).click().perform()
        time.sleep(1)

        if len(get_inputs(driver)) >= 2:
            return

    assert len(get_inputs(driver)) >= 2, (
        "Transfer form must open after clicking an account card"
    )


def set_input_value(element, value):
    element.click()
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(Keys.BACKSPACE)
    element.send_keys(value)


def test_bug_001_card_number_must_be_16_digits(driver, app_url):
    open_app(driver, app_url)

    click_first_available_account(driver)

    inputs = get_inputs(driver)

    assert len(inputs) >= 2, (
        "Transfer form must contain card number and amount inputs"
    )

    card_input = inputs[0]
    set_input_value(card_input, "12345678901234567")

    normalized = card_input.get_attribute("value").replace(" ", "")

    assert len(normalized) == 16, (
        "Card number must be limited to 16 digits"
    )


def test_bug_002_negative_transfer_must_be_blocked(driver, app_url):
    open_app(driver, app_url)

    click_first_available_account(driver)

    inputs = get_inputs(driver)

    assert len(inputs) >= 2, (
        "Transfer form must contain card number and amount inputs"
    )

    card_input = inputs[0]
    amount_input = inputs[1]

    set_input_value(card_input, "1234567890123456")
    set_input_value(amount_input, "-1000")

    buttons = driver.find_elements(By.CSS_SELECTOR, "button")

    enabled_transfer_buttons = [
        button for button in buttons
        if "перевести" in button.text.lower()
        and button.is_displayed()
        and button.is_enabled()
    ]

    assert len(enabled_transfer_buttons) == 0, (
        "Transfer button must not be enabled for negative amount"
    )