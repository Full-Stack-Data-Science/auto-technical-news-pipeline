#!/bin/bash
set -e

RESOURCE_GROUP="technical-news"
INFRA_FOLDER="./infra"
BICEP="${INFRA_FOLDER}/bicep/modules/acr.bicep"
OUTPUT="arc-outputs.json"

# ACR-specific parameters (not from main parameters.json)
ACR_NAME="technicalwebscrapingacr"
LOCATION="southeastasia"
ACR_SKU="Basic"

echo "=================================================="
echo "Deploying Azure Container Registry"
echo "=================================================="
echo ""
echo "Resource Group: $RESOURCE_GROUP"
echo "Bicep File: $BICEP"
echo ""

# Check if resource group exists
echo "Checking resource group..."
if ! az group show --name $RESOURCE_GROUP &>/dev/null; then
    echo "❌ Error: Resource group '$RESOURCE_GROUP' does not exist"
    echo "Create it with: az group create --name $RESOURCE_GROUP --location southeastasia"
    exit 1
fi
echo "✓ Resource group exists"


# Deploy
echo ""
echo "Deploying ACR..."
echo "This will take 2-3 minutes..."

az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file $BICEP \
  --parameters acrName=$ACR_NAME location=$LOCATION acrSku=$ACR_SKU \
  --query "properties.outputs" -o json > $OUTPUT


if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================="
    echo "✓ ACR Deployment Successful!"
    echo "=================================================="
    echo ""
    
    # Extract and display outputs
    ACR_NAME=$(cat $OUTPUT | jq -r '.acrName.value')
    ACR_LOGIN_SERVER=$(cat $OUTPUT | jq -r '.loginServer.value')
    
    echo "ACR Details:"
    echo "  Name: $ACR_NAME"
    echo "  Login Server: $ACR_LOGIN_SERVER"
    echo ""
    
    # Save to environment file
    cat > .env.acr << EOF
ACR_NAME=$ACR_NAME
ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER
EOF
    
    echo "✓ Credentials saved to .env.acr"
    echo ""
    echo "=================================================="
    echo "Next Steps:"
    echo "=================================================="
    echo "1. Build and push Docker image:"
    echo "   Use the build script: ./infra/scripts/build_image.sh"
    echo "   Or manually:"
    echo "   cd src && az acr build --registry $ACR_NAME --image twitter-scraper:latest --file Dockerfile ."
    echo ""
else
    echo "❌ Deployment failed"
    exit 1
fi