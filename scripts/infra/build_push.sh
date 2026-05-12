#!/usr/bin/env bash
# Build a Docker image and push it to ACR.
#
# Usage:
#   ./infra/scripts/build_push.sh <service> [tag]
#
# Arguments:
#   service   One of: twitter-scraper, linkedin-scraper, post-publisher
#   tag       Image tag (default: latest)
#
# Required env var:
#   ACR_NAME  Azure Container Registry name (e.g. technewsacr001)
#             Falls back to reading from `terraform output` if unset.
#
# Examples:
#   ACR_NAME=technewsacr001 ./infra/scripts/build_push.sh twitter-scraper
#   ./infra/scripts/build_push.sh post-publisher v1.2.3
set -euo pipefail

SERVICE="${1:-}"
TAG="${2:-latest}"
REPO_ROOT="$(git rev-parse --show-toplevel)"

if [[ -z "$SERVICE" ]]; then
  echo "Usage: $0 <service> [tag]"
  echo "  service: twitter-scraper | linkedin-scraper | post-publisher"
  exit 1
fi

# Resolve ACR name from env var or terraform output
if [[ -z "${ACR_NAME:-}" ]]; then
  echo "ACR_NAME not set — reading from terraform output..."
  ACR_NAME="$(cd "${REPO_ROOT}/infra/terraform" && terraform output -raw acr_login_server | cut -d. -f1)"
fi

ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"
FULL_IMAGE="${ACR_LOGIN_SERVER}/${SERVICE}:${TAG}"

# Map service name to Dockerfile location
case "$SERVICE" in
  twitter-scraper)
    DOCKERFILE="${REPO_ROOT}/Dockerfile.twitter"
    ;;
  linkedin-scraper)
    DOCKERFILE="${REPO_ROOT}/Dockerfile.linkedin"
    ;;
  post-publisher)
    DOCKERFILE="${REPO_ROOT}/Dockerfile.publisher"
    ;;
  *)
    echo "Unknown service: ${SERVICE}"
    echo "  Expected: twitter-scraper | linkedin-scraper | post-publisher"
    exit 1
    ;;
esac

echo "==> Logging in to ACR: ${ACR_LOGIN_SERVER}"
az acr login --name "${ACR_NAME}"

echo "==> Building: ${FULL_IMAGE}"
docker build \
  --file "${DOCKERFILE}" \
  --tag "${FULL_IMAGE}" \
  "${REPO_ROOT}"

echo "==> Pushing: ${FULL_IMAGE}"
docker push "${FULL_IMAGE}"

echo "==> Done: ${FULL_IMAGE}"
