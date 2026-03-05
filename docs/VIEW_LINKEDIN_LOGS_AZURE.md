# Viewing LinkedIn Scraper Logs in Azure Portal

## Quick Answer

**Yes!** All the logs you see locally (like "LinkedIn AI Graph Built Successfully", "Starting LinkedIn login process...", etc.) will appear in Azure Portal.

## How to View Them

### Step 1: Navigate to Logs

1. Go to Azure Portal
2. Find your Container App Job: `linkedin-scraping-job`
3. Go to **Monitoring** → **Logs**

### Step 2: Use This KQL Query

Paste this query into the query editor:

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| project TimeGenerated, Log_s, Level
| order by TimeGenerated desc
```

Click **Run** to see the logs.

### Step 3: What You'll See

You should see logs like:
- `"LinkedIn AI Graph Built Successfully"`
- `"Total users: 51"`
- `"Initializing LinkedInPostScraper..."`
- `"Checking for Selenium Grid server at localhost:4444..."`
- `"✓ Selenium Grid is ready"`
- `"Starting LinkedIn login process..."`
- `"Scraping posts for user chiphuyen"`
- And all other application logs

## Filter by Log Level

### See Only Errors and Warnings

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| where Level in ("ERROR", "WARNING", "CRITICAL")
| project TimeGenerated, Log_s, Level
| order by TimeGenerated desc
```

### See Only Info Logs

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| where Level == "INFO"
| project TimeGenerated, Log_s
| order by TimeGenerated desc
```

## Search for Specific Text

### Find Login-Related Logs

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| where Log_s contains "login" or Log_s contains "Login"
| project TimeGenerated, Log_s
| order by TimeGenerated desc
```

### Find Upload-Related Logs

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| where Log_s contains "upload" or Log_s contains "Upload" or Log_s contains "complete"
| project TimeGenerated, Log_s
| order by TimeGenerated desc
```

## View Logs from Specific Execution

If you want to see logs from a specific job execution:

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| where ExecutionName_s == "linkedin-scraping-job-ufx1oqy"  // Replace with your execution name
| project TimeGenerated, Log_s, Level
| order by TimeGenerated desc
```

## View Recent Logs (Last Hour)

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| where TimeGenerated > ago(1h)
| project TimeGenerated, Log_s, Level
| order by TimeGenerated desc
```

## Log Format in Azure

The logs will appear in the `Log_s` column with the same format as local:
```
2025-12-31 12:15:11,732 - src.scraping.linkedin.linkedin_scraper - INFO - Starting scraping process...
```

## Troubleshooting

### If You Don't See Logs

1. **Check Time Range**: Make sure the time range includes when the job ran
   - Default is "Last 24 hours"
   - Adjust if needed

2. **Check Container Name**: Make sure you're filtering by `ContainerName_s == "scraper"` (not "selenium")

3. **Wait a Few Minutes**: Logs can take 2-5 minutes to appear in Log Analytics

4. **Check Job Status**: Make sure the job actually ran
   - Go to **Execution history** to verify

### If Logs Are Missing

1. **Check if logging is configured**: The code uses `logging.StreamHandler` which writes to stdout/stderr
2. **Check if job completed**: If the job failed early, logs might be limited
3. **Check Log Analytics workspace**: Make sure it's properly configured for your Container App environment

## Quick Reference

**Location**: Azure Portal → `linkedin-scraping-job` → **Monitoring** → **Logs**

**Basic Query**:
```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| project TimeGenerated, Log_s
| order by TimeGenerated desc
```

**What You'll See**: All the same logs you see locally, including:
- Graph building messages
- Selenium initialization
- Login process
- Scraping progress
- Upload status
- Errors and warnings















