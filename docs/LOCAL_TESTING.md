# Local Testing Guide for LinkedIn Scraper

## Why Nothing Shows Up?

The LinkedIn scraper requires **Selenium Grid** to be running. When you run the script locally, it waits for Selenium Grid at `localhost:4444`, but it's not running, so the script hangs.

## Solution: Start Selenium Grid Locally

### Option 1: Using Docker Compose (Recommended)

From the project root:
```bash
cd src
docker-compose up -d selenium-chrome
```

Or from the root directory:
```bash
docker-compose -f src/docker-compose.yaml up -d selenium-chrome
```

Verify Selenium is running:
```bash
curl http://localhost:4444/wd/hub/status
```

You should see a JSON response with `"ready": true`.

### Option 2: Using Docker Directly

```bash
docker run -d -p 4444:4444 --shm-size=2g selenium/standalone-chrome:latest
```

### Option 3: Run Everything with Docker Compose

```bash
cd src
docker-compose up
```

This will start both Selenium and the scraper service.

## Test the Scraper

Once Selenium is running, test the scraper:

```bash
cd /home/martin/technical-news
python3 -m src.service.linkedin_scraper_execution
```

Or:
```bash
cd /home/martin/technical-news
python3 src/service/linkedin_scraper_execution.py
```

## Expected Output

You should see:
1. Graph built with influencers
2. "Selenium Grid is ready" message
3. LinkedIn login process
4. Post scraping for each influencer

## Troubleshooting

### Selenium Not Starting

Check if port 4444 is already in use:
```bash
lsof -i :4444
```

If something is using it, stop it or use a different port.

### Connection Refused

Make sure Docker is running:
```bash
docker ps
```

### Timeout Errors

Increase the timeout in the code or check Selenium logs:
```bash
docker logs selenium-chrome
```

## Stop Selenium

When done testing:
```bash
docker-compose -f src/docker-compose.yaml down
```

Or:
```bash
docker stop $(docker ps -q --filter ancestor=selenium/standalone-chrome)
```