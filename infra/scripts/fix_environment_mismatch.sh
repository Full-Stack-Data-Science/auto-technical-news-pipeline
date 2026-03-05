#!/bin/bash
set -e

RESOURCE_GROUP="technical-news"
LINKEDIN_JOB_NAME="linkedin-scraping-job"
TARGET_ENV="cae-scrapingJobs-v2"

echo "=================================================="
echo "Fixing Environment Mismatch"
echo "=================================================="
echo ""
echo "Issue: LinkedIn job exists in different environment than Twitter job"
echo "Solution: Move LinkedIn job to same environment as Twitter (cae-scrapingJobs-v2)"
echo ""

# Check current LinkedIn job environment
CURRENT_ENV=$(az containerapp job show --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP --query "properties.environmentId" -o tsv 2>/dev/null || echo "")

if [ -z "$CURRENT_ENV" ]; then
    echo "LinkedIn job does not exist. You can deploy it fresh."
    exit 0
fi

echo "Current LinkedIn job environment: $CURRENT_ENV"

TARGET_ENV_ID="/subscriptions/33e07b82-c85e-42ae-a35f-9e7dc6461ba5/resourceGroups/technical-news/providers/Microsoft.App/managedEnvironments/$TARGET_ENV"

if [[ "$CURRENT_ENV" == *"$TARGET_ENV"* ]]; then
    echo "✓ LinkedIn job is already in the correct environment ($TARGET_ENV)"
    exit 0
fi

echo ""
echo "⚠️  LinkedIn job is in a different environment."
echo "To move it, we need to:"
echo "  1. Delete the existing LinkedIn job"
echo "  2. Recreate it in the target environment"
echo ""
read -p "Do you want to proceed? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Delete existing LinkedIn job
echo ""
echo "Step 1: Deleting existing LinkedIn job..."
az containerapp job delete \
    --name $LINKEDIN_JOB_NAME \
    --resource-group $RESOURCE_GROUP \
    --yes \
    --output none

echo "✓ LinkedIn job deleted"
echo ""

# Wait a bit for deletion to complete
echo "Waiting for deletion to complete..."
sleep 10

# Deploy LinkedIn job to correct environment
echo ""
echo "Step 2: Deploying LinkedIn job to $TARGET_ENV..."
cd infra/bicep

az deployment group create \
    --resource-group $RESOURCE_GROUP \
    --template-file modules/linkedin-container-job.bicep \
    --parameters \
        location=southeastasia \
        jobName=$LINKEDIN_JOB_NAME \
        envId="$TARGET_ENV_ID" \
        acrLoginServer=technicalwebscrapingacr.azurecr.io \
        scraperImage=linkedin-scraper \
        scraperImageTag=latest \
        identityName=uami-linkedin-scraping \
        cronSchedule="0 2 * * *" \
    --query "properties.provisioningState" -o tsv

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ LinkedIn job deployed to $TARGET_ENV"
else
    echo "❌ Deployment failed"
    exit 1
fi

cd ../..

# Verify
echo ""
echo "Verifying deployment..."
sleep 5
NEW_ENV=$(az containerapp job show --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP --query "properties.environmentId" -o tsv)

if [[ "$NEW_ENV" == *"$TARGET_ENV"* ]]; then
    echo "✓ LinkedIn job is now in $TARGET_ENV"
    echo ""
    echo "Both jobs are now in the same environment:"
    echo "  - Twitter job: $TARGET_ENV"
    echo "  - LinkedIn job: $TARGET_ENV"
else
    echo "❌ Verification failed"
    exit 1
fi

echo ""
echo "=================================================="
echo "Environment Mismatch Fixed!"
echo "=================================================="















