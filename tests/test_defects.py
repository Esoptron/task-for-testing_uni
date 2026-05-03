from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--allow-file-access-from-files")

    drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    yield drv
    drv.quit()


def open_app(drv):
    url = Path("dist/index.html").resolve().as_uri()
    drv.get(url)


def select_rub_account(drv):
    drv.find_element(By.XPATH, "//h2[text()='Рубли']").click()


def test_bug_001_card_number_must_be_16_digits(driver):
    open_app(driver)
    select_rub_account(driver)

    card_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder='0000 0000 0000 0000']")
    card_input.send_keys("12345678901234567")

    normalized = card_input.get_attribute("value").replace(" ", "")
    assert len(normalized) == 16, "Card number must be limited to 16 digits"


def test_bug_002_negative_transfer_must_be_blocked(driver):
    open_app(driver)
    select_rub_account(driver)

    card_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder='0000 0000 0000 0000']")
    card_input.send_keys("1234567890123456")

    amount_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder='1000']")
    amount_input.clear()
    amount_input.send_keys("-1000")

    buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Перевести')]")
    assert len(buttons) == 0, "Transfer button must not be visible for negative amount"
