from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
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
        lambda driver: driver.find_element(By.ID, "root")
    )


def select_account_with_transfer_form(drv):
    cards = wait(drv).until(
        lambda driver: driver.find_elements(By.CSS_SELECTOR, "[role='button']")
    )

    for card in cards:
        drv.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            card
        )
        drv.execute_script("arguments[0].click();", card)

        try:
            WebDriverWait(drv, 2).until(
                lambda driver: len(
                    driver.find_elements(By.CSS_SELECTOR, "input")
                ) >= 2
            )
            return
        except TimeoutException:
            continue

    raise AssertionError("Transfer form was not opened after clicking account cards")


def get_inputs(drv):
    return wait(drv).until(
        lambda driver: driver.find_elements(By.CSS_SELECTOR, "input")
        if len(driver.find_elements(By.CSS_SELECTOR, "input")) >= 2
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

    transfer_buttons = driver.find_elements(
        By.XPATH,
        "//button[contains(normalize-space(), 'Перевести')]"
    )

    has_enabled_transfer_button = any(
        button.is_displayed() and button.is_enabled()
        for button in transfer_buttons
    )

    assert not has_enabled_transfer_button, (
        "Transfer button must be disabled for negative amount"
    )