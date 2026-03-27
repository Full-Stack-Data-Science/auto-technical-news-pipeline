#!/bin/bash
set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

RESOURCE_GROUP="technical-news"
LINKEDIN_JOB_NAME="linkedin-scraping-job"

echo "=================================================="
echo "Deploying LinkedIn Job Only (Skipping Twitter)"
echo "=================================================="
echo ""

# Check if LinkedIn job already exists
if az containerapp job show --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "⚠️  LinkedIn job already exists. Updating it..."
    UPDATE_MODE=true
else
    echo "Creating new LinkedIn job..."
    UPDATE_MODE=false
fi

# Deploy only LinkedIn job using the module directly
cd infra/bicep

# Get the environment ID (prefer the existing LinkedIn job's environment)
EXISTING_ENV=$(az containerapp job show --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP --query "properties.environmentId" -o tsv 2>/dev/null || echo "")

if [ -z "$EXISTING_ENV" ]; then
    # Fallback to Twitter job's environment if LinkedIn job doesn't exist yet
    EXISTING_ENV=$(az containerapp job show --name twitter-scraping-job --resource-group $RESOURCE_GROUP --query "properties.environmentId" -o tsv 2>/dev/null || echo "")
    if [ -z "$EXISTING_ENV" ]; then
        echo "Could not determine environment. Please check Twitter job exists."
        exit 1
    fi
fi

echo "Using environment: $EXISTING_ENV"
echo ""

# Deploy LinkedIn job module directly
az deployment group create \
    --resource-group $RESOURCE_GROUP \
    --template-file modules/linkedin-container-job.bicep \
    --parameters \
        location=southeastasia \
        jobName=$LINKEDIN_JOB_NAME \
        envId="$EXISTING_ENV" \
        acrLoginServer=technicalwebscrapingacr.azurecr.io \
        scraperImage=linkedin-scraper \
        scraperImageTag=latest \
        identityName=uami-linkedin-scraping \
        cronSchedule="0 2 * * *" \
    --query "properties.provisioningState" -o tsv

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ LinkedIn job deployment completed"
else
    echo "Deployment failed"
    exit 1
fi

cd "$PROJECT_ROOT"

# Verify job
echo ""
echo "Verifying LinkedIn job..."
sleep 5
if az containerapp job show --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "✓ LinkedIn job created/updated successfully!"
    echo ""
    az containerapp job show \
        --name $LINKEDIN_JOB_NAME \
        --resource-group $RESOURCE_GROUP \
        --query "{name:name, provisioningState:properties.provisioningState, environmentId:properties.environmentId, schedule:properties.configuration.scheduleTriggerConfig.cronExpression}" -o json | python3 -m json.tool
else
    echo "LinkedIn job not found after deployment"
    exit 1
fi

echo ""
echo "=================================================="
echo "LinkedIn Job Deployed Successfully!"
echo "=================================================="