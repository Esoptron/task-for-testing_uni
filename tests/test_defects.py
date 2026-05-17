from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--allow-file-access-from-files")

    drv = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    yield drv
    drv.quit()


def open_app(drv):
    url = Path("dist/index.html").resolve().as_uri()
    drv.get(url)


def wait(drv, seconds=10):
    return WebDriverWait(drv, seconds)


def find_card_input(drv):
    return wait(drv).until(
        EC.visibility_of_element_located(
            (By.XPATH, "//input[@placeholder='0000 0000 0000 0000']")
        )
    )


def find_amount_input(drv):
    return wait(drv).until(
        EC.visibility_of_element_located(
            (By.XPATH, "//input[@placeholder='1000']")
        )
    )


def find_transfer_button(drv):
    return wait(drv).until(
        EC.visibility_of_element_located(
            (By.XPATH, "//button[contains(normalize-space(), 'Перевести')]")
        )
    )


def test_bug_001_card_number_must_be_16_digits(driver):
    open_app(driver)

    card_input = find_card_input(driver)
    card_input.clear()
    card_input.send_keys("12345678901234567")

    normalized = card_input.get_attribute("value").replace(" ", "")

    assert len(normalized) == 16, (
        "Card number must be limited to 16 digits"
    )


def test_bug_002_negative_transfer_must_be_blocked(driver):
    open_app(driver)

    card_input = find_card_input(driver)
    card_input.clear()
    card_input.send_keys("1234567890123456")

    amount_input = find_amount_input(driver)
    amount_input.clear()
    amount_input.send_keys("-1000")

    transfer_button = find_transfer_button(driver)

    assert not transfer_button.is_enabled(), (
        "Transfer button must be disabled for negative amount"
    )