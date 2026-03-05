# Updating LinkedIn Scraper Code - Quick Guide

## When You Change Code Locally

After making changes to the LinkedIn scraper code, you need to rebuild and push the Docker image to Azure Container Registry (ACR) so the Azure job uses your updated code.

## Quick Steps

### 1. Rebuild and Push Docker Image

```bash
cd /home/martin/technical-news
./infra/scripts/build_linkedin_image.sh
```

This script will:
- Build a new Docker image with your updated code
- Push it to Azure Container Registry (ACR)
- Tag it as `linkedin-scraper:latest`

**Time:** ~5-10 minutes

### 2. Verify Image Was Pushed

```bash
az acr repository show-tags \
  --name technicalwebscrapingacr \
  --repository linkedin-scraper \
  --output table
```

You should see `latest` with a recent timestamp.

### 3. The Job Will Use New Image Automatically

The Azure Container App Job is configured to use `linkedin-scraper:latest`, so:
- **Next scheduled run**: Will automatically use the new image
- **Manual run**: Will use the new image immediately

No need to redeploy the job - just rebuild the image!

## Optional: Force Immediate Test

If you want to test the new code immediately without waiting for the scheduled run:

```bash
# Start a manual execution
az containerapp job start \
  --name linkedin-scraping-job \
  --resource-group technical-news

# Monitor the execution
az containerapp job execution list \
  --name linkedin-scraping-job \
  --resource-group technical-news \
  -o table
```

## What Gets Updated

The Docker image includes:
- All Python source code (`src/` directory)
- Dependencies (`requirements.txt`)
- Configuration files

## What Doesn't Need Rebuild

You **don't need to rebuild** if you only change:
- Bicep templates (infrastructure)
- Environment variables in Azure Portal (requires job update, not rebuild)
- Azure resource configurations

## Troubleshooting

### Image Build Fails

```bash
# Check if .env.acr exists
ls -la .env.acr

# If missing, run ACR setup first
./infra/scripts/acr_setup.sh
```

### Job Still Uses Old Code

1. **Check image tag**: The job should use `linkedin-scraper:latest`
2. **Verify push succeeded**: Check ACR repository tags
3. **Check job configuration**: 
   ```bash
   az containerapp job show \
     --name linkedin-scraping-job \
     --resource-group technical-news \
     --query "properties.template.containers[?name=='scraper'].image" \
     -o table
   ```

### Need to Update Environment Variables

If you change environment variables (like `STORAGE_ACCOUNT_KEY`), you need to:
1. Update the Bicep template (`infra/bicep/modules/container-linkedin-jobs-env.bicep`)
2. Redeploy the job:
   ```bash
   cd infra/bicep
   az deployment group create \
     --resource-group technical-news \
     --template-file main.bicep \
     --parameters @parameters.json
   ```

## Summary

**For code changes:**
```bash
./infra/scripts/build_linkedin_image.sh
```

**For infrastructure/config changes:**
```bash
# Update Bicep files, then:
cd infra/bicep
az deployment group create \
  --resource-group technical-news \
  --template-file main.bicep \
  --parameters @parameters.json
```

That's it! The job will automatically use the new image on the next run.















