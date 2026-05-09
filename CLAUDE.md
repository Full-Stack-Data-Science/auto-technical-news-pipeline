# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated pipeline that scrapes social media posts (Twitter/X and LinkedIn) from tech influencers, classifies them for technical relevance using zero-shot ML, summarizes trending content with GPT, and publishes curated insights to the [FSDS community platform](https://fullstackdatascience.com).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
export PYTHONPATH="${PYTHONPATH}:./src"
```

Required environment variables (create `.env`):
```
TWITTER_EMAIL, TWITTER_PASSWORD
LINKEDIN_EMAIL, LINKEDIN_PASSWORD
STORAGE_ACCOUNT_KEY          # Azure ADLS Gen2
OPENAI_API_KEY
FSDS_USERNAME, FSDS_PASSWORD
SERVICE_BUS_CONNECTION_STRING
```

See `src/common/config.py` for all config values and defaults.

## Commands

```bash
# Run tests
export PROJECT_ROOT="./test"
pytest test/unit/test_celeb_graph.py
pytest test/unit/test_utils.py

# Integration tests (require Chrome + internet)
pytest test/intergration/test_twitter_post_extractor.py
pytest test/intergration/test_linkedin_post_extractor.py

# Run scraping jobs
python3 src/service/twitter_scraper_execution.py --data data/influencer/twitter_influencer.json --no-upload
python3 src/service/linkedin_scraper_execution.py --data data/influencer/linkedin_influencer.json --posts 3 --no-upload

# Run publishing jobs
python3 src/service/twitter_trending_posts_publish.py
python3 src/service/linkedin_trending_posts_publish.py
```

## Architecture

The system has four loosely-coupled layers:

**1. Scraper (`src/post_scraper/`)** — Selenium-based, uses persistent Chrome user profiles (stored in `./google-chrome/`) so sessions survive between runs without re-authentication. Scrapers are graph-aware: the influencer network (`src/celeb_graph/`) is loaded as a NetworkX graph, and the scraper walks nodes to discover whose timeline to visit. Output is Parquet files written to `data/raw/{twitter,linkedin}/` and optionally uploaded to Azure ADLS Gen2.

**2. Classification (`src/post_writer/post_classification/`)** — Two-stage pipeline. Stage 1 applies cheap rule-based filters (length, keyword lists) to reject obvious non-technical posts early. Stage 2 runs zero-shot inference using `facebook/bart-large-mnli` for the rest. Results are `ClassificationResult` with labels (Generative AI, NLP, ML, CV, etc.) and an `exit_stage` tracking which stage rejected/accepted the post. The classifier caches results with LRU cache on the model.

**3. Summarization (`src/post_writer/llm/`)** — `ChatGPTClient` wraps OpenAI/Azure OpenAI. Prompts are in `src/post_writer/llm/prompt_templates/post_summary.py`. The `use_cases.py` module contains `summerize_X_posts()` and `summerize_linkedin_posts()` which pick top-K posts by engagement, generate summaries, and return them with hashtags derived from classification labels.

**4. Publisher (`src/fsds/`)** — `MemePoster` authenticates to FSDS and posts rich HTML. A local `published_posts.json` cache (see `src/common/utils.py`) prevents re-publishing.

**Data flow**: Parquet files → Azure ADLS bronze layer → Azure Synapse SQL views (dedup/normalize) → silver layer → Power BI dashboards. Azure Service Bus (`src/common/messaging/`) can trigger consumers when new posts arrive.

## Chrome Profile Setup (one-time)

The scrapers require a pre-authenticated Chrome profile. Chrome must be closed before running scrapers:

```bash
# Create profiles and sign in manually
google-chrome --user-data-dir=./google-chrome --profile-directory=Profile_Twitter
# Navigate to x.com, sign in, close Chrome

google-chrome --user-data-dir=./google-chrome --profile-directory=Profile_LinkedIn
# Navigate to linkedin.com, sign in, close Chrome

pkill -9 chrome  # Ensure Chrome is fully closed before running scrapers
```

## Influencer Configuration

Scrapers expect JSON files before running:

**`data/influencer/twitter_influencer.json`** — dict mapping username to `{follow: [], mention: []}` relationship lists (used to build the `celeb_graph`).

**`data/influencer/linkedin_influencer.json`** — list of LinkedIn profile slugs.

## Infrastructure

Terraform definitions in `infra/terraform/` provision Azure Container Registry, Container Jobs, ADLS Gen2, Service Bus, and Synapse. Shell scripts in `infra/scripts/pipeline/` are the cron job entrypoints.
