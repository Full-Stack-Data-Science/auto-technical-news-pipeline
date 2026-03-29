import os
from dotenv import load_dotenv

class Config:    
    PROJECT_ROOT = os.getenv("PROJECT_ROOT", ".")
    
    # filesystems
    DATA_DIR = f"{PROJECT_ROOT}/data"
    TWITTER_DATA_DIR = f"{DATA_DIR}/raw/twitter"
    LINKEDIN_DATA_DIR = f"{DATA_DIR}/raw/linkedin"
    COOKIE_PATH= f"{DATA_DIR}/cookies"

    # scraper websites
    TWITTER_PAGE = "https://x.com"
    TWITTER_LOGIN = f"{TWITTER_PAGE}/login"
    LINKEDIN_PAGE = "https://www.linkedin.com"
    LINKEDIN_LOGIN = f"{LINKEDIN_PAGE}/login"
    PROXY_WEBPAGE  = "https://free-proxy-list.net/"

    # credential
    TWITTER_EMAIL=os.getenv("TWITTER_EMAIL", "quochungtr99@gmail.com")
    TWITTER_PASSWORD=os.getenv("TWITTER_PASSWORD", "...")
    USER_NAME =os.getenv("USER_NAME")
    LINKEDIN_EMAIL=os.getenv("LINKEDIN_EMAIL", "dangminhhust193231@gmail.com")
    LINKEDIN_PASSWORD=os.getenv("LINKEDIN_PASSWORD", "...")
    TWITTER_COOKIE_FILE=f"{COOKIE_PATH}/twitter_cookies.json"
    LINKEDIN_COOKIE_FILE =f"{COOKIE_PATH}/linkedin_cookies.json"
    SELENIUM_HOST=os.getenv("SELENIUM_HOST", "localhost")

    STORAGE_ACCOUNT_NAME=os.getenv("STORAGE_ACCOUNT_NAME", "technewsdlake001")
    STORAGE_ACCOUNT_KEY =os.getenv("STORAGE_ACCOUNT_KEY")
    FILE_SYSTEM_NAME=os.getenv("FILE_SYSTEM_NAME", "bronze")

    FSDS_URL            =os.getenv("FSDS_URL", "https://api.fullstackdatascience.com")
    FSDS_USERNAME=os.getenv("FSDS_USERNAME")
    FSDS_PASSWORD=os.getenv("FSDS_PASSWORD")

    OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
    OPENAI_ENDPOINT ="https://fdry-code-review-dev.cognitiveservices.azure.com/openai/v1/"
    TECHNICAL_CHANNEL_ID=os.getenv('TECHNICAL_CHANNEL_ID', 'e0eea093-9d1c-4364-bb7b-e8d17d89e71b')

    SERVICE_BUS_CONNECTION_STRING=os.getenv("SERVICE_BUS_CONNECTION_STRING")
    TWITTER_NEW_POST_TOPIC=os.getenv("TWITTER_NEW_POST_TOPIC", "new-post-events")
    TWITTER_NEW_POST_SUBSCRIPTION=os.getenv("TWITTER_NEW_POST_SUBSCRIPTION", "logger")