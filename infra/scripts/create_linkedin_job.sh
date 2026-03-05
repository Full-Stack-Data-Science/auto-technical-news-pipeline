#!/bin/bash
set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

RESOURCE_GROUP="technical-news"
LINKEDIN_JOB_NAME="linkedin-scraping-job"
LINKEDIN_IDENTITY_NAME="uami-linkedin-scraping"
ACR_NAME="technicalwebscrapingacr"
STORAGE_ACCOUNT="technewsdlake001"

echo "=================================================="
echo "Creating LinkedIn Scraping Job"
echo "=================================================="
echo ""

# Step 1: Verify prerequisites
echo "STEP 1: Checking prerequisites..."

# Check if managed identity exists
if ! az identity show --name $LINKEDIN_IDENTITY_NAME --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "⚠️  Managed identity '$LINKEDIN_IDENTITY_NAME' does not exist"
    echo "Creating managed identity..."
    az identity create \
        --name $LINKEDIN_IDENTITY_NAME \
        --resource-group $RESOURCE_GROUP \
        --location southeastasia
    echo "✓ Managed identity created"
else
    echo "✓ Managed identity exists"
fi

# Get identity principal ID
IDENTITY_PRINCIPAL_ID=$(az identity show \
    --name $LINKEDIN_IDENTITY_NAME \
    --resource-group $RESOURCE_GROUP \
    --query principalId -o tsv)
echo "  Principal ID: $IDENTITY_PRINCIPAL_ID"
echo ""

# Step 2: Grant ACR permissions
echo "STEP 2: Granting ACR pull permission..."
ACR_ID=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query id -o tsv)
az role assignment create \
    --assignee $IDENTITY_PRINCIPAL_ID \
    --role AcrPull \
    --scope $ACR_ID \
    --output none 2>/dev/null && echo "✓ ACR pull permission granted" || echo "⚠️  Permission may already exist"
echo ""

# Step 3: Grant Storage permissions
echo "STEP 3: Granting Storage permissions..."
STORAGE_ID=$(az storage account show --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query id -o tsv 2>/dev/null || echo "")
if [ -z "$STORAGE_ID" ]; then
    echo "⚠️  Storage account not found. Skipping storage permissions."
else
    az role assignment create \
        --assignee $IDENTITY_PRINCIPAL_ID \
        --role "Storage Blob Data Contributor" \
        --scope $STORAGE_ID \
        --output none 2>/dev/null && echo "✓ Storage permissions granted" || echo "⚠️  Permission may already exist"
fi
echo ""

# Step 4: Check if LinkedIn image exists in ACR
echo "STEP 4: Checking LinkedIn Docker image..."
if az acr repository show --name $ACR_NAME --repository linkedin-scraper &>/dev/null; then
    echo "✓ LinkedIn image exists in ACR"
    az acr repository show-tags --name $ACR_NAME --repository linkedin-scraper --output table
else
    echo "❌ LinkedIn image not found in ACR"
    echo "Please build and push the image first:"
    echo "  ./infra/scripts/build_linkedin_image.sh"
    exit 1
fi
echo ""

# Step 5: Deploy LinkedIn job
echo "STEP 5: Deploying LinkedIn scraping job..."
cd infra/bicep
az deployment group create \
    --resource-group $RESOURCE_GROUP \
    --template-file main.bicep \
    --parameters @parameters.json \
    --query "properties.provisioningState" -o tsv

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Deployment completed"
else
    echo "❌ Deployment failed"
    exit 1
fi
cd "$PROJECT_ROOT"
echo ""

# Step 6: Verify job exists
echo "STEP 6: Verifying LinkedIn job..."
sleep 5
if az containerapp job show --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "✓ LinkedIn job created successfully!"
    echo ""
    echo "Job details:"
    az containerapp job show \
        --name $LINKEDIN_JOB_NAME \
        --resource-group $RESOURCE_GROUP \
        --query "{name:name, provisioningState:properties.provisioningState, schedule:properties.configuration.scheduleTriggerConfig.cronExpression}" -o json | python3 -m json.tool
else
    echo "❌ LinkedIn job not found after deployment"
    exit 1
fi
echo ""

# Step 7: Summary
echo "=================================================="
echo "LinkedIn Scraping Job Created Successfully!"
echo "=================================================="
echo ""
echo "Job Name: $LINKEDIN_JOB_NAME"
echo "Schedule: Daily at 2:00 AM (0 2 * * *)"
echo ""
echo "Next steps:"
echo "1. Test run the job:"
echo "   az containerapp job start --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "2. Monitor execution:"
echo "   az containerapp job execution list --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP -o table"
echo ""
echo "3. View logs:"
echo "   az containerapp job logs show --name $LINKEDIN_JOB_NAME --resource-group $RESOURCE_GROUP --container scraper --follow"
echo ""













