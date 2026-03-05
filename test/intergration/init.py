from selenium import webdriver
from dotenv import load_dotenv

def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    return driver

def set_test_env_var():
    load_dotenv()