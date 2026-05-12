# Table of Contents

- [Getting Started](#getting-started)
  - [Project Structure](#project-structure)
  - [Prepare Environment](#prepare-environment)
  - [Install Google Chrome](#install-google-chrome)
  - [Create a Persistent Chrome User Profile](#create-a-persistent-chrome-user-profile)
  - [Running the Pipeline Locally](#running-the-pipeline-locally)
    - [1. Configure the Influencer Network](#1-configure-the-influencer-network)
    - [2. Set Environment Variables](#2-set-environment-variables)
    - [3. Run the Scraper](#3-run-the-scraper)
    - [4. Run the Publisher](#4-run-the-publisher)
- [Running Tests](#running-tests)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)
- [Architecture Diagram](#architecture-diagram)
  - [Scraping Service (Producer Layer)](#scraping-service-producer-layer)
  - [Data Lake (Storage Layer)](#data-lake-storage-layer)
  - [Message Queue (Event / Trigger Layer)](#message-queue-event--trigger-layer)
  - [Filtering / Consumer Service](#filtering--consumer-service)
  - [Presentation](#presentation)
  - [Visualization](#visualization)
- [Cloud Deployment](#cloud-deployment)
  - [Prerequisites](#prerequisites)
  - [One-Time Azure Setup](#one-time-azure-setup)
  - [Configure Variables](#configure-variables)
  - [Build and Push Images](#build-and-push-images)
  - [Deploy with Terraform](#deploy-with-terraform)
  - [Trigger a Job Manually](#trigger-a-job-manually)
- [TODO](#todo)

# Getting Started

This project automates an end-to-end technical news pipeline using Selenium WebDriver. It collects posts from social media influencers, classifies them for technical relevance, summarizes trending content, and publishes curated insights to any downstream channel — Discord, community platforms, or any webhook-compatible destination.

The pipeline is designed to be extensible — currently supporting X (Twitter), with LinkedIn support in active development following the same architecture.

## Project Structure

```
.
├── analytics/                     # SQL views for Azure Synapse (bronze → silver layer)
│   └── sql_queries/
├── data/                          # Local data (git-ignored in production)
│   ├── influencer/                # Influencer config JSON files
│   └── raw/                       # Scraped Parquet output (twitter/, linkedin/)
├── infra/
│   └── terraform/                 # All IaC — ACR, storage, Container App Jobs
│       ├── main.tf
│       ├── variables.tf
│       ├── locals.tf
│       ├── outputs.tf
│       ├── backend.tf
│       ├── terraform.tfvars.example
│       └── modules/
│           ├── acr/               # Azure Container Registry module
│           ├── storage/           # ADLS Gen2 module
│           └── scraper_job/       # Reusable scheduled Container App Job module
├── notebooks/                     # Research & experimentation
├── scripts/
│   ├── infra/                     # Infrastructure scripts
│   │   ├── build_push.sh          # Build + push Docker image to ACR
│   │   ├── tf_deploy.sh           # Terraform plan / apply / destroy wrapper
│   │   └── trigger_job.sh         # Manually trigger a Container App Job
│   └── pipeline/                  # Pipeline entrypoint scripts (run inside containers)
│       ├── run_twitter_scraper_job.sh
│       └── run_twitter_post_publish.sh
├── src/                           # Application source (PYTHONPATH=./src)
│   ├── celeb_graph/               # Influencer network graph (NetworkX)
│   │   ├── graph/                 # Graph builder
│   │   ├── io/                    # JSON loader
│   │   └── models/                # Relationship model
│   ├── common/                    # Shared config, utils, logging
│   │   ├── messaging/             # Azure Service Bus publisher / consumer
│   │   └── storage/               # ADLS Gen2 client + local Parquet reader
│   ├── post_scraper/              # Selenium-based scrapers
│   │   ├── core/                  # DriverManager, base classes, post cache, data models
│   │   ├── proxypool/             # Proxy pool scraper
│   │   ├── twitter/               # Twitter session, parser, extractor, scraper
│   │   └── linkedin/              # LinkedIn parser, extractor, scraper (in development)
│   ├── post_writer/               # Classification, summarization, and publishing
│   │   ├── post_classification/   # Two-stage classifier (rules + bart-large-mnli zero-shot)
│   │   ├── llm/                   # LLM clients (Claude, GPT) + prompt templates
│   │   └── publisher/             # Publisher layer (base, Discord, ranking, dedup cache)
│   ├── service/                   # Execution entry points (called by pipeline scripts)
│   └── requirements.txt
├── test/
│   ├── unit/                      # Unit tests (no Chrome, no network, ML mocked)
│   └── intergration/              # Integration tests (require Chrome + internet)
└── TODO.md
```

## Prepare Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/requirements.txt
export PYTHONPATH="${PYTHONPATH}:./src"
```

## Install Google Chrome

This project requires Google Chrome (not Chromium) — it supports Google Account sign-in fully and its profile structure is stable with Selenium.

```bash
google-chrome --version
```

## Create a Persistent Chrome User Profile

A persistent Chrome profile preserves authentication state, cookies, and session tokens across runs so you only log in once.

### Create and initialize the profile

```bash
google-chrome --user-data-dir=./google-chrome --profile-directory=Profile_Twitter
```

Repeat with `--profile-directory=Profile_LinkedIn` for LinkedIn (when that pipeline is ready).

### Manually sign in (one-time only)

When Chrome opens with the new profile:
1. Navigate to https://x.com and sign in via Google.
2. Complete any CAPTCHA or verification steps.
3. Confirm you stay logged in after a page refresh.

![Google auth](images/gg_authen.png)

Once done, close Chrome fully before running the scraper:

```bash
pkill -9 chrome
```

## Running the Pipeline Locally

The pipeline has two entry points that run in sequence.

### 1. Configure the Influencer Network

Create `data/influencer/twitter_influencer.json` defining the accounts to scrape and their relationships:

```json
{
  "karpathy": {
    "follow": ["AndrewYNg", "ylecun"]
  },
  "ylecun": {
    "follow": ["karpathy", "lexfridman"],
    "mention": ["GoogleDeepMind"]
  },
  "AndrewYNg": {}
}
```

Each key is a Twitter username. `follow` and `mention` lists are used to build the influence graph — leave them empty (`{}`) if you have no relationship data for a user.

### 2. Set Environment Variables

Create a `.env` file or export the variables directly:

```bash
export TWITTER_EMAIL="your-twitter@example.com"
export TWITTER_PASSWORD="your-password"

# Optional — only needed for the publisher step
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export ANTHROPIC_API_KEY="sk-ant-..."   # or OPENAI_API_KEY
```

### 3. Run the Scraper

Scrapes the most recent posts from each configured influencer, classifies them (technical vs. non-technical), and writes the results to a local Parquet file.

```bash
python3 src/service/twitter_scraper_execution.py \
    --data data/influencer/twitter_influencer.json \
    --posts 3 \
    --no-upload
```

| Flag | Description |
|---|---|
| `--data` | Path to the influencer config file |
| `--posts` | Number of recent posts to scrape per user |
| `--no-upload` | Keep output local; omit to upload to Azure ADLS |

Output is written to `data/raw/twitter/twitter_scraping_data_<timestamp>.parquet`.

### 4. Run the Publisher

Reads the scraped Parquet files, picks the top trending technical posts by engagement, generates a summary using the configured LLM (Claude or GPT, falls back to plain text if neither is configured), and posts to Discord.

```bash
python3 src/service/twitter_trending_posts_publish.py
```

The publisher reads from `data/raw/twitter/` by default. No flags required for a local run — credentials are picked up from environment variables.

# Running Tests

## Unit Tests

Unit tests have **no external dependencies** — no Chrome, no internet, no cloud credentials. The zero-shot classifier is mocked wherever it appears.

```bash
export PYTHONPATH="${PYTHONPATH}:./src"
export PROJECT_ROOT="./test"

# Full suite
pytest test/unit/ -v

# Single file
pytest test/unit/test_post_classification.py -v

# Single class or case
pytest test/unit/test_post_classification.py::TestPostClassifierZeroShotMulti -v
pytest test/unit/test_post_classification.py::TestPostClassifierZeroShotMulti::test_two_labels_when_scores_within_margin -v

# Filter by name substring
pytest test/unit/ -k "ops" -v
```

## Integration Tests

Integration tests drive a real Chrome browser. They require an authenticated Chrome profile and Chrome fully closed before running.

```bash
pkill -9 chrome
pytest test/intergration/test_twitter_post_extractor.py -v
```

# Architecture Diagram

This project is an end-to-end data pipeline that continuously collects, classifies, summarizes, and publishes trending technical content. It follows a producer–consumer pattern centered around a data lake.

![Overall architecture](images/arch.png)

## Scraping Service (Producer Layer)

The scraper connects to configured influencer timelines via Selenium WebDriver using a persistent Chrome profile. It detects new posts, classifies them, and writes compressed Parquet files to the Data Lake on a scheduled cron cadence.

Chrome profile persistence means authentication tokens and session state survive across runs — no re-login needed. The scraper operates headlessly after the one-time manual sign-in.

## Data Lake (Storage Layer)

Scraped Parquet files land in the **Bronze layer** of Azure ADLS Gen2, organized by platform:

```
bronze/twitter/
bronze/linkedin/   ← in development
```

The **Silver layer** contains deduped, normalized views built by Azure Synapse Serverless SQL over the Bronze Parquet files. Power BI connects to the Silver layer for dashboards and trend exploration.

![Data Lake](images/data_lake.png)

## Message Queue (Event / Trigger Layer)

When the scraper detects a new post, it publishes an event to Azure Service Bus. The publisher job subscribes to this topic and processes events asynchronously — decoupling ingestion speed from publishing speed and ensuring no events are lost during transient failures.

## Filtering / Consumer Service

Reads scraped data from the Data Lake, then:
- Classifies posts as technical or non-technical using zero-shot inference (`facebook/bart-large-mnli`)
- Ranks the top-K technical posts by engagement (likes, reposts, comments)
- Generates a natural-language summary via LLM (Claude or GPT)

## Presentation

Trending technical post summaries are published to a Discord channel via webhook.

![Post summarization](images/post_summerization.png)

## Visualization

The Silver layer feeds Power BI dashboards for interactive trend exploration across influencers, topics, and engagement metrics.

![Dashboard](images/analytics.png)

# Cloud Deployment

The pipeline runs as scheduled Azure Container App Jobs. Terraform manages all infrastructure; three helper scripts cover the deploy workflow.

```
infra/terraform/
├── main.tf                    # Root: wires ACR, storage, scraper job, publisher job
├── variables.tf               # All input variables
├── locals.tf                  # Auto-applied tags (Project, ManagedBy, Environment)
├── outputs.tf                 # Key output values
├── backend.tf                 # Remote state config (commented — enable for teams)
├── terraform.tfvars.example
└── modules/
    ├── acr/                   # Azure Container Registry
    ├── storage/               # ADLS Gen2 storage account + bronze container
    └── scraper_job/           # Reusable scheduled Container App Job

scripts/infra/
├── build_push.sh              # Build Docker image and push to ACR
├── tf_deploy.sh               # terraform init → plan / apply / destroy
└── trigger_job.sh             # Manually trigger a Container App Job
```

## Prerequisites

| Tool | Minimum version |
|---|---|
| [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) | 2.50 |
| [Terraform](https://developer.hashicorp.com/terraform/downloads) | 1.5 |
| [Docker](https://docs.docker.com/get-docker/) | 24 |

```bash
az login
az account set --subscription <your-subscription-id>
```

## One-Time Azure Setup

These resources are looked up by Terraform as data sources — create them once before the first `terraform apply`:

```bash
az group create --name rg-tech-news-pipeline --location southeastasia

az monitor log-analytics workspace create \
  --resource-group rg-tech-news-pipeline \
  --workspace-name law-tech-news
```

## Configure Variables

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars — never commit it
```

For CI/CD, export sensitive values as `TF_VAR_*` environment variables instead:

```bash
export TF_VAR_twitter_credentials='{"email":"x@example.com","password":"secret"}'
export TF_VAR_discord_webhook_url="https://discord.com/api/webhooks/..."
export TF_VAR_anthropic_api_key="sk-ant-..."
```

## Build and Push Images

```bash
export ACR_NAME=technewsacr001   # or read automatically from terraform output

./scripts/infra/build_push.sh twitter-scraper    # uses Dockerfile.twitter
./scripts/infra/build_push.sh post-publisher     # uses Dockerfile.publisher

# Push a specific tag
./scripts/infra/build_push.sh twitter-scraper v1.2.3
```

## Deploy with Terraform

```bash
./scripts/infra/tf_deploy.sh plan     # preview changes
./scripts/infra/tf_deploy.sh apply    # create / update resources
./scripts/infra/tf_deploy.sh destroy  # tear down (requires typing 'yes')
```

After a successful apply:

```
acr_login_server         = "technewsacr001.azurecr.io"
storage_account_name     = "technewsdlake001"
twitter_scraper_job_name = "twitter-scraper-job"
publisher_job_name       = "post-publisher-job"
```

The scraper job runs on its cron schedule automatically. The publisher job is event-triggered and fires whenever a new post event arrives on the Service Bus topic.

## Trigger a Job Manually

```bash
./scripts/infra/trigger_job.sh twitter-scraper-job rg-tech-news-pipeline

# Follow execution status
az containerapp job execution list \
  --name twitter-scraper-job \
  --resource-group rg-tech-news-pipeline \
  -o table
```

# TODO
See the full task list in [TODO.md](TODO.md).
