# Azure Cloud vs Local - Common Issues and Fixes

## Problem: Works Locally, Fails on Azure

### Issue 1: CAPTCHA/Login Timeout in Headless Mode

**Symptom:**
- Works perfectly locally
- Fails on Azure with: `"Manual login timeout - please complete CAPTCHA and try again"`

**Root Cause:**
- Azure runs in headless mode (no browser window)
- Code tries to wait for manual CAPTCHA completion (impossible in headless)
- LinkedIn detects automated access and shows CAPTCHA

**Fix Applied:**
- Detect if running in headless/Docker environment
- Fail fast with clear error message instead of waiting 5 minutes
- Provide actionable error messages

**Solution:**
The code now detects headless mode and fails immediately with helpful error messages instead of timing out.

### Issue 2: Missing Data Directories

**Symptom:**
- FileNotFoundError when trying to write CSV files
- Directory doesn't exist errors

**Root Cause:**
- Dockerfile only created `/src/data/cookies`
- Missing `/src/data/raw/linkedin` directory

**Fix Applied:**
Updated Dockerfile to create all necessary directories:
```dockerfile
RUN mkdir -p /src/data/cookies && \
    mkdir -p /src/data/raw/linkedin && \
    mkdir -p /src/data/raw/twitter
```

### Issue 3: Missing JSON Files

**Symptom:**
- Warnings about missing `all_scraped_followers.json` and `all_scraped_connections.json`

**Root Cause:**
- These files aren't copied into Docker image
- They're only needed for relationship graph building

**Status:**
- ✅ Already handled gracefully - code creates minimal graph if files don't exist
- This is expected behavior for first run

## Key Differences: Local vs Azure

| Aspect | Local | Azure (Cloud) |
|--------|-------|---------------|
| **Browser Mode** | Visible (can interact) | Headless (no UI) |
| **CAPTCHA** | Can complete manually | Cannot complete |
| **Cookies** | Saved to local disk | Saved in container (ephemeral) |
| **Selenium** | localhost:4444 | selenium:4444 (container name) |
| **File Paths** | Relative to project root | `/src/...` (absolute) |
| **Environment** | Your machine | Docker container |

## Best Practices for Azure Deployment

### 1. Use Cookies from Previous Runs

Cookies are saved in the container. If login succeeds once, cookies can be reused:
- Cookies are saved to `/src/data/cookies/linkedin_cookies.json`
- They persist within the same container execution
- But are lost when container stops (ephemeral storage)

### 2. Handle CAPTCHA Gracefully

The code now:
- Detects headless mode
- Fails fast with clear error
- Suggests solutions (wait, retry, check credentials)

### 3. Ensure All Directories Exist

The Dockerfile now creates:
- `/src/data/cookies` - for session cookies
- `/src/data/raw/linkedin` - for CSV output
- `/src/data/raw/twitter` - for Twitter data (if needed)

### 4. Use Environment Variables

Make sure these are set in Azure:
- `STORAGE_ACCOUNT_NAME`
- `STORAGE_ACCOUNT_KEY`
- `FILE_SYSTEM_NAME`
- `LINKEDIN_EMAIL`
- `LINKEDIN_PASSWORD`
- `SELENIUM_HOST=selenium` (container name, not localhost)

## Troubleshooting

### Login Fails with CAPTCHA

**If you see:**
```
CAPTCHA challenge in headless environment - cannot complete automatically
```

**Solutions:**
1. **Wait and retry**: LinkedIn may be rate-limiting
2. **Check credentials**: Make sure `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD` are correct
3. **Use cookies**: If you have valid cookies, they should be loaded automatically
4. **Check LinkedIn account**: Account might be flagged - try logging in manually first

### File Not Found Errors

**If you see:**
```
FileNotFoundError: [Errno 2] No such file or directory: '/src/data/raw/linkedin/...'
```

**Solution:**
- Rebuild Docker image with updated Dockerfile
- The directories are now created during image build

### Selenium Connection Issues

**If you see:**
```
Selenium Grid did not become ready
```

**Check:**
- `SELENIUM_HOST` environment variable should be `selenium` (not `localhost`)
- Selenium container is running in the same job
- Both containers are in the same network

## Next Steps After Fixes

1. **Rebuild Docker Image:**
   ```bash
   ./infra/scripts/build_linkedin_image.sh
   ```

2. **Redeploy Job (if needed):**
   ```bash
   cd infra/bicep
   az deployment group create \
     --resource-group technical-news \
     --template-file main.bicep \
     --parameters @parameters.json
   ```

3. **Test Run:**
   ```bash
   az containerapp job start \
     --name linkedin-scraping-job \
     --resource-group technical-news
   ```

4. **Monitor Logs:**
   - Check Azure Portal → Logs
   - Look for the new error messages if CAPTCHA is detected
   - Verify directories are created

## Summary

The main fixes:
1. ✅ Detect headless mode and fail fast on CAPTCHA (no 5-minute wait)
2. ✅ Create all necessary directories in Dockerfile
3. ✅ Better error messages for debugging

These changes ensure the code behaves appropriately in both local and Azure environments.















