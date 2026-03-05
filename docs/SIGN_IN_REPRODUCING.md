# Reproducing sign-in automation test in local

This guide explains how to reproduce the X (Twitter) sign-in automation test both locally and using Docker.

# Getting started

To get start, we need to do the following

## Prepare enviroment 

Install all dependencies dedicated to the project in local

```bash
python -m venv .venv
source .venv/bin/activate
```

```bash
cd src
pip install -r requirements.txt
```

## Reproduce in local machine

Both ways running in non-headless mode

### Set up env variables running in local

Export the required environment variables:
```bash
cd src 

export EMAIL="..."
export PASSWORD="..."
export USER_NAME="..."
export PYTHONPATH="${PYTHONPATH}:."
```

### Sign In to X via Google OAuth (Selenium)
```python
python3 scraping/twitter/sign_in_by_selenium.py
```
Note: Change run_in_local=True, in order to utilize webdriver/Chrome browser in local

### Sign In to X using nodriver (connect to X directly using username/password)

Open Source: https://github.com/ultrafunkamsterdam/nodriver

This approach uses nodriver to sign in directly to X, without Google OAuth.

```python
python3 scraping/twitter/sign_in_by_nodriver.py
```

## Running with docker container


- Sign-in to X using Selenium (selenium-chrome + twitter-scraping-selenium containers) 
- Sign-in to X using nosriver (twitter-scraping-nodriver container)
- Note: Change run_in_local=False from sign_in_by_selenium, in order to connect webdriver/Chrome browser in selenium Chrome container.

Create .env, and adding env as credentials 
```
EMAIL="..."
PASSWORD="..."
USER_NAME="..."
SELENIUM_HOST="selenium-chrome" # remote Selenium service that has a browser via port 4444
```

Running both above scraping approaches and a remote Selenium Chrome container (support for selenium solution)
```
docker compose up -d
```

For reference, base docker images:
```
Dockerfile.nodriver: nodriver solution
Dockerfile.selenium: selenium solution
```
### Outcome

Log-in using nodriver in docker is failed (checking flow by tracking UI captures in artifact folder)