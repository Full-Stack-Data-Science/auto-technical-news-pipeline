# technical-news


# Docker compose to build docker image in local:

```
docker compose up -d
```

```
docker compose down
```

# ACR setup


```
infra/scripts/./acr_setup.sh
```

# Push docker image to acr registry

```
infra/scripts/./build_image.sh
```

# Create uami
```
az identity create \
  --name uami-twitter-scraping \
  --resource-group technical-news \
  --location southeastasia
```

to access to storage, docker registry, grant ArcPull

# create Containers app env

```
infra/scripts/./create_azurecontainerapp_env.sh
```
```
  az containerapp job delete \
    --name "twitter-scraping-job" \
    --resource-group "technical-news" \
    --yes \
    --only-show-errors || true
```
# create datalake file system
```
infra/scripts/./storage_setup.sh
```