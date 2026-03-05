## Orchestration setup overview

This document describes a **prototype** Apache Airflow setup used for
experimenting with orchestration of the **LinkedIn** scraping/publishing flow
on a local machine.

It does **not** replace the production cron jobs running on the VM, and it is
not used for the Twitter flow. Cron remains the source of truth in production;
Airflow here is only for local development, debugging, and “what‑if” scheduling
of the LinkedIn pipeline.

Airflow runs locally and points its DAGs folder at `src/orchestration/dags`, while
all generated Airflow state (database, logs, config) is kept inside
`src/orchestration/dags/.airflow` and ignored by Git.

The key scripts are:

- `src/requirements.txt` – installs Airflow and its dependencies.
- `setup_airflow.sh` – one‑time initialization of the Airflow database and admin user.
- `start_airflow.sh` – helper to start the webserver and scheduler with the right env vars.

## Prerequisites

- **Python**: 3.10 or 3.11 (Airflow 2.9.0 does **not** support 3.12).
- **Virtualenv** (installed automatically from `src/requirements.txt`).
- System packages for Selenium/Chrome/Chromedriver as required by the scrapers.

From the project root (`/home/martin/technical-news` on the primary dev machine):

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r src/requirements.txt
```

This installs:

- `apache-airflow==2.9.0`
- `flask-session==0.5.0`
- `virtualenv`
- plus all scraping and testing dependencies.

## Airflow layout and environment variables

The orchestration layout is:

- **DAGs folder**: `src/orchestration/dags`
- **Airflow home** (state, DB, logs, config): `src/orchestration/dags/.airflow`

Environment variables used:

- `AIRFLOW_HOME` – points to `src/orchestration/dags/.airflow`
- `AIRFLOW__CORE__DAGS_FOLDER` – points to `src/orchestration/dags`
- `AIRFLOW__CORE__LOAD_EXAMPLES` – set to `False` to avoid pulling in example DAGs
  and their optional dependencies (e.g. `kubernetes`).

Both `setup_airflow.sh` and `start_airflow.sh` export these variables for you.

## One‑time Airflow initialization

Run this once after creating your virtualenv and installing requirements:

```bash
cd /home/martin/technical-news
source .venv/bin/activate
./setup_airflow.sh
```

What `setup_airflow.sh` does:

- Creates `src/orchestration/dags/` if it does not exist.
- Sets `AIRFLOW_HOME=src/orchestration/dags/.airflow`.
- Runs `airflow db init` to initialize the metadata database.
- Updates `airflow.cfg` so:
  - `dags_folder = src/orchestration/dags`
  - `load_examples = False`
- Creates an admin user (idempotent):
  - username: `admin`
  - password: `admin`

If you run the project from a different absolute path than
`/home/martin/technical-news`, update `ORCHESTRATION_DAGS_DIR` at the top of
`setup_airflow.sh` and `start_airflow.sh` accordingly.

## Starting the Airflow webserver and scheduler

After initialization, use the helper script to start Airflow:

```bash
cd /home/martin/technical-news
source .venv/bin/activate

# Terminal 1 – web UI
./start_airflow.sh webserver

# Terminal 2 – scheduler
./start_airflow.sh scheduler
```

Then open the Airflow UI at:

- `http://localhost:8080`
- login: `admin` / `admin`

You should see DAGs defined in `src/orchestration/dags` (once you add them).

## Adding orchestration DAGs (LinkedIn prototype only)

Airflow discovers DAGs by scanning Python files in `src/orchestration/dags`.

For the current prototype we only orchestrate the **LinkedIn** flow.

To add or modify the LinkedIn workflow:

- Create or edit a `.py` file in `src/orchestration/dags`, for example
  `src/orchestration/dags/linkedin_scraper_dag.py`.
- Define one or more `DAG` objects inside, using operators like `BashOperator`
  to call the existing LinkedIn shell entrypoints such as:
  - `src/run_linkedin_scraper_job.sh`

A typical LinkedIn Airflow DAG will:

- Scrape LinkedIn posts.
- Optionally save media / transform data.
- Optionally publish LinkedIn posts.

These DAGs are meant for local experimentation. The production VM still relies
on cron and shell scripts to run the real jobs.

## CI notes

In CI, the project uses:

- `PYTHONPATH=/home/runner/work/technical-news/technical-news/src`

This ensures that `scraping.*` and other packages under `src/` are importable
in tests and in any Airflow tasks that rely on the same code.

If you add new orchestration code that imports from `src/`, keep this layout
and `PYTHONPATH` convention so CI and local runs behave consistently.

