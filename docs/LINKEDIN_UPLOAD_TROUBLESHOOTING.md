# LinkedIn Data Upload to Azure Storage - Troubleshooting

## Why You Don't See Data Yet

The upload to Azure Storage only happens **AFTER all scraping is complete**. If you see logs like:
```
CSV dump successfully for user tshaw
```

This means the scraper is still running. The upload happens at the very end.

## Expected Behavior

1. **During Scraping**: Data is saved locally to `/src/data/raw/linkedin/linkedin_scraping_data_{timestamp}.csv`
2. **After All Users Scraped**: The upload process begins
3. **Upload Location**: `bronze` container → `linkedin/raw/linkedin_scraping_data_{timestamp}.csv`

## How to Check if Upload Happened

### Step 1: Check Azure Logs

In Azure Portal → `linkedin-scraping-job` → **Monitoring** → **Logs**, run this query:

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "linkedin-scraping-job"
| where ContainerName_s == "scraper"
| where Log_s contains "Upload" or Log_s contains "upload" or Log_s contains "complete"
| project TimeGenerated, Log_s
| order by TimeGenerated desc
```

Look for these log messages:
- ✅ `"Scraping complete. Uploading data to Azure Data Lake Storage..."`
- ✅ `"Found CSV file: {path} ({size} bytes)"`
- ✅ `"Uploading {filename} to Azure Data Lake Storage..."`
- ✅ `"✓ CSV uploaded successfully to ADLS Gen2 at linkedin/raw/{filename}"`
- ❌ `"STORAGE_ACCOUNT_KEY not set"` or `"FILE_SYSTEM_NAME not set"`
- ❌ `"Failed to upload to Azure Data Lake Storage"`

### Step 2: Check Job Execution Status

In Azure Portal → `linkedin-scraping-job` → **Execution history**:
- Check if the latest execution shows **"Succeeded"** or **"Failed"**
- If it's still running, wait for it to complete
- If it failed, check the logs for errors

### Step 3: Check Azure Storage

In Azure Portal → `technewsdlake001` → **Storage browser** → `bronze` container:

**Expected Structure:**
```
bronze/
├── twitter/          (existing)
└── linkedin/
    └── raw/
        └── linkedin_scraping_data_{timestamp}.csv
```

**If you don't see `linkedin` folder:**
- The upload hasn't happened yet (job still running)
- OR the upload failed (check logs)

## Common Issues

### Issue 1: Upload Never Happens

**Symptoms:**
- Job completes but no `linkedin` folder appears
- No "Uploading" or "uploaded successfully" messages in logs

**Possible Causes:**
1. **Missing Environment Variables**: Check if `STORAGE_ACCOUNT_KEY` and `FILE_SYSTEM_NAME` are set
2. **File Not Found**: The CSV file was deleted or not created
3. **Silent Failure**: Exception was caught but not logged properly

**Solution:**
Check logs for:
```
STORAGE_ACCOUNT_KEY not set - cannot upload to Azure Data Lake Storage
FILE_SYSTEM_NAME not set - cannot upload to Azure Data Lake Storage
CSV file not found: {path}
```

### Issue 2: Upload Fails with Permission Error

**Symptoms:**
- Logs show: `"Failed to upload to Azure Data Lake Storage: ..."`
- Error mentions "permission" or "authentication"

**Solution:**
1. Verify the Managed Identity has "Storage Blob Data Contributor" role
2. Check that `STORAGE_ACCOUNT_KEY` is correct in the Bicep template
3. Verify the storage account name matches: `technewsdlake001`

### Issue 3: Wrong Path in Storage

**Symptoms:**
- Upload succeeds but file is in wrong location
- File appears in root of container instead of `linkedin/raw/`

**Solution:**
The upload path is: `{data_source}/raw/{file_csv}` which should be `linkedin/raw/{filename}.csv`

## Verification Commands

### Check if Job Completed

```bash
az containerapp job execution list \
  --name linkedin-scraping-job \
  --resource-group technical-news \
  --query "[0].{name:name, status:properties.status, startTime:properties.startTime}" \
  -o table
```

### Check Latest Logs for Upload

```bash
az monitor log-analytics query \
  --workspace {workspace-id} \
  --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == 'linkedin-scraping-job' | where Log_s contains 'upload' | order by TimeGenerated desc | take 10" \
  -o table
```

## Next Steps

1. **Wait for Job to Complete**: If the scraper is still running, wait for it to finish
2. **Check Execution History**: Verify the job status is "Succeeded"
3. **Check Logs**: Look for upload-related messages
4. **Check Storage**: Navigate to `bronze` container and look for `linkedin/raw/` folder

## Expected Timeline

- **Scraping**: ~30-60 minutes (depends on number of influencers)
- **Upload**: ~10-30 seconds (depends on file size)
- **Total**: ~30-60 minutes from start to data appearing in Azure Storage















