#!/bin/bash
set -e

RESOURCE_GROUP="technical-news"
INFRA_FOLDER="./infra"
BICEP="${INFRA_FOLDER}/bicep/main.bicep"
PARAMS="${INFRA_FOLDER}/bicep/parameters.json" 
OUTPUT="container-jobs-env-outputs.json"

# DEPLOY JOB
# -------------------------
echo "Deploying Container App Job..."

az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file $BICEP \
  --parameters $PARAMS
  --name main-$(date +%s) \

echo "Job deployment completed"