#!/usr/bin/env bash
# Manually trigger a Container App Job execution (useful for ad-hoc runs).
#
# Usage:
#   ./infra/scripts/trigger_job.sh <job-name> <resource-group>
#
# Example:
#   ./infra/scripts/trigger_job.sh twitter-scraper-job rg-tech-news-pipeline
set -euo pipefail

JOB_NAME="${1:-}"
RESOURCE_GROUP="${2:-}"

if [[ -z "$JOB_NAME" || -z "$RESOURCE_GROUP" ]]; then
  echo "Usage: $0 <job-name> <resource-group>"
  exit 1
fi

echo "==> Triggering job: ${JOB_NAME} in ${RESOURCE_GROUP}"
az containerapp job start \
  --name "${JOB_NAME}" \
  --resource-group "${RESOURCE_GROUP}"

echo "==> Job started. Follow logs with:"
echo "    az containerapp job execution list --name ${JOB_NAME} --resource-group ${RESOURCE_GROUP} -o table"
