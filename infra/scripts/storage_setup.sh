#!/bin/bash
set -e

RESOURCE_GROUP="technical-news"
INFRA_FOLDER="./infra"
BICEP="${INFRA_FOLDER}/bicep/modules/storage.bicep"


az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file $BICEP \ 