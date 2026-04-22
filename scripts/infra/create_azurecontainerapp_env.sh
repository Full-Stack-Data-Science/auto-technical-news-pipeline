
RESOURCE_GROUP="technical-news"
LOCATION="southeastasia"
NAME_ENV="cae-scrapingJobs-v2"

az containerapp env create \
  --name $NAME_ENV \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

az containerapp env list \
  -g $RESOURCE_GROUP \
  -o table