#!/usr/bin/env bash
# Terraform init → plan → apply wrapper.
#
# Usage:
#   ./infra/scripts/tf_deploy.sh [plan|apply|destroy] [extra terraform flags]
#
# Examples:
#   ./infra/scripts/tf_deploy.sh plan
#   ./infra/scripts/tf_deploy.sh apply
#   ./infra/scripts/tf_deploy.sh apply -var="twitter_job={name=\"twitter-scraper-job\",image_name=\"twitter-scraper\",cron_schedule=\"0 */6 * * *\"}"
#   ./infra/scripts/tf_deploy.sh destroy
#
# Set TF_VAR_* env vars for sensitive values instead of putting them in tfvars:
#   export TF_VAR_twitter_credentials='{"email":"x@x.com","password":"secret"}'
set -euo pipefail

COMMAND="${1:-plan}"
shift || true

TF_DIR="$(git rev-parse --show-toplevel)/infra/terraform"

cd "${TF_DIR}"

echo "==> terraform init"
terraform init -upgrade

case "$COMMAND" in
  plan)
    echo "==> terraform plan"
    terraform plan "$@"
    ;;
  apply)
    echo "==> terraform apply"
    terraform apply "$@"
    ;;
  destroy)
    echo "WARNING: This will destroy all managed infrastructure."
    read -rp "Type 'yes' to confirm: " confirm
    [[ "$confirm" == "yes" ]] || { echo "Aborted."; exit 1; }
    terraform destroy "$@"
    ;;
  *)
    echo "Unknown command: ${COMMAND}"
    echo "  Expected: plan | apply | destroy"
    exit 1
    ;;
esac
