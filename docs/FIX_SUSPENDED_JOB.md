# Fix: "Job linkedin-scraping-job is suspended" Error

## The Problem

You're getting this error:
```
Attempt to start job failed. Job linkedin-scraping-job is suspended
```

## Why This Happens

Azure Container Apps Jobs get automatically suspended after multiple consecutive failures (usually 5+). This is a safety mechanism.

## Solution: Resume via Azure Portal

The Azure CLI doesn't have a direct "resume" command, but you can fix it via the portal:

### Step 1: Go to Azure Portal
1. Navigate to: https://portal.azure.com
2. Search for: `linkedin-scraping-job`
3. Open the job

### Step 2: Check Job Status
1. Go to **Overview**
2. Look for job status
3. If it shows "Suspended", there should be a **"Resume"** or **"Activate"** button

### Step 3: Resume the Job
1. Click **"Resume"** or **"Activate"** button
2. Confirm the action
3. Wait for the job to be active

### Step 4: Try Starting Again
```bash
az containerapp job start \
  --name linkedin-scraping-job \
  --resource-group technical-news
```

## Alternative: Redeploy the Job

If there's no resume button, redeploy the job to reset its state:

```bash
cd /home/martin/technical-news/infra/bicep
az deployment group create \
  --resource-group technical-news \
  --template-file main.bicep \
  --parameters @parameters.json
```

**Note:** This will reset the job configuration, so make sure your Bicep template is up to date.

## Why It Was Suspended

Looking at your execution history:
- `linkedin-scraping-job-6yki13t` - **Failed** (likely due to CAPTCHA/login issues)
- `linkedin-scraping-job-ufx1oqy` - **Stopped** (manually stopped)
- `linkedin-scraping-job-xenoxhv` - **Stopped** (just stopped)

Multiple failures likely triggered the automatic suspension.

## Prevention

After fixing the code (CAPTCHA handling, directory creation), the job should work better:

1. **Rebuild the Docker image** with the fixes:
   ```bash
   ./infra/scripts/build_linkedin_image.sh
   ```

2. **Resume the job** (via portal or redeploy)

3. **Start a new execution**:
   ```bash
   az containerapp job start \
     --name linkedin-scraping-job \
     --resource-group technical-news
   ```

## Quick Check

To see if the job is suspended:
```bash
az containerapp job show \
  --name linkedin-scraping-job \
  --resource-group technical-news \
  --query "properties.provisioningState" \
  -o tsv
```

If it shows "Succeeded" but you still can't start it, the job is likely suspended and needs to be resumed via the portal.















