#!/bin/bash
set -e

# Deploy a dedicated LinkedIn Connections/Followers scraping job.
# This mirrors the LinkedIn post scraper structure but overrides the command
# to run the connections scraper entrypoint.

# Resolve script and project roots
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

RESOURCE_GROUP="technical-news"
JOB_NAME="linkedin-connections-job"
LOCATION="southeastasia"
ACR_LOGIN_SERVER="technicalwebscrapingacr.azurecr.io"
SCRAPER_IMAGE="linkedin-scraper"
# Use the working tag that is known-good for LinkedIn
SCRAPER_IMAGE_TAG="working-20260102"
IDENTITY_NAME="uami-linkedin-scraping"
# Default schedule: daily at 03:00 UTC (adjust as needed)
CRON_SCHEDULE="0 3 * * *"

echo "=================================================="
echo "Deploying LinkedIn Connections Job"
echo "=================================================="
echo ""

# Determine Container Apps Environment:
# 1) If the connections job exists, reuse its environment
# 2) Else reuse the existing linkedin-scraping-job environment
# 3) Else fall back to twitter-scraping-job environment
EXISTING_ENV=$(az containerapp job show --name "$JOB_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.environmentId" -o tsv 2>/dev/null || echo "")

if [ -z "$EXISTING_ENV" ]; then
  EXISTING_ENV=$(az containerapp job show --name linkedin-scraping-job --resource-group "$RESOURCE_GROUP" --query "properties.environmentId" -o tsv 2>/dev/null || echo "")
fi

if [ -z "$EXISTING_ENV" ]; then
  EXISTING_ENV=$(az containerapp job show --name twitter-scraping-job --resource-group "$RESOURCE_GROUP" --query "properties.environmentId" -o tsv 2>/dev/null || echo "")
fi

if [ -z "$EXISTING_ENV" ]; then
  echo "Could not determine Container Apps Environment. Ensure a LinkedIn or Twitter job already exists."
  exit 1
fi

echo "Using environment: $EXISTING_ENV"
echo ""

cd infra/bicep

# Deploy the connections job using the generic linkedin-container-job.bicep module
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file modules/linkedin-container-job.bicep \
  --parameters \
    location="$LOCATION" \
    jobName="$JOB_NAME" \
    envId="$EXISTING_ENV" \
    acrLoginServer="$ACR_LOGIN_SERVER" \
    scraperImage="$SCRAPER_IMAGE" \
    scraperImageTag="$SCRAPER_IMAGE_TAG" \
    identityName="$IDENTITY_NAME" \
    cronSchedule="$CRON_SCHEDULE" \
    scraperCommand='["python3","-m","service.linkedin_connections_scraper_execution"]' \
  --query "properties.provisioningState" -o tsv

echo ""
echo "✓ LinkedIn connections job deployment finished."

cd "$PROJECT_ROOT"

echo ""
echo "Verifying job..."
sleep 5
if az containerapp job show --name "$JOB_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  echo "✓ LinkedIn connections job created/updated successfully!"
  az containerapp job show \
    --name "$JOB_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "{name:name, provisioningState:properties.provisioningState, environmentId:properties.environmentId, schedule:properties.configuration.scheduleTriggerConfig.cronExpression}" -o json | python3 -m json.tool
else
  echo "LinkedIn connections job not found after deployment"
  exit 1
fi

echo ""
echo "=================================================="
echo "LinkedIn Connections Job Deployed Successfully!"
echo "=================================================="
