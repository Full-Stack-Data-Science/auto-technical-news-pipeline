from selenium import webdriver
from dotenv import load_dotenv

from contextlib import contextmanager
from selenium import webdriver

@contextmanager
def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    try:
        yield driver
    finally:
        driver.quit()

def set_test_env_var():
    load_dotenv()