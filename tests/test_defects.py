from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

    yield f"http://127.0.0.1:{server.server_port}/index.html"

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
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(normalize-space(), 'F-Bank')]")
        )
    )


def select_rub_account(drv):
    rub_sum = wait(drv).until(
        EC.presence_of_element_located((By.ID, "rub-sum"))
    )

    drv.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});",
        rub_sum
    )
    drv.execute_script(
        "arguments[0].click();",
        rub_sum
    )


def get_inputs(drv):
    return wait(drv).until(
        lambda driver: driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
        if len(driver.find_elements(By.CSS_SELECTOR, "input[type='text']")) >= 2
        else False
    )


def find_card_input(drv):
    return get_inputs(drv)[0]


def find_amount_input(drv):
    return get_inputs(drv)[1]


def find_transfer_button(drv):
    return wait(drv).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//button[contains(normalize-space(), 'Перевести')]"
            )
        )
    )


def set_input_value(element, value):
    element.click()
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(Keys.BACKSPACE)
    element.send_keys(value)


def test_bug_001_card_number_must_be_16_digits(driver, app_url):
    open_app(driver, app_url)
    select_rub_account(driver)

    card_input = find_card_input(driver)
    set_input_value(card_input, "12345678901234567")

    normalized = card_input.get_attribute("value").replace(" ", "")

    assert len(normalized) == 16, (
        "Card number must be limited to 16 digits"
    )


def test_bug_002_negative_transfer_must_be_blocked(driver, app_url):
    open_app(driver, app_url)
    select_rub_account(driver)

    card_input = find_card_input(driver)
    set_input_value(card_input, "1234567890123456")

    amount_input = find_amount_input(driver)
    set_input_value(amount_input, "-1000")

    transfer_button = find_transfer_button(driver)

    assert not transfer_button.is_enabled(), (
        "Transfer button must be disabled for negative amount"
    )