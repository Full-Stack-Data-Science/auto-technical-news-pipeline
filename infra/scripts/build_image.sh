#!/bin/bash
set -e

# Defaults
IMAGE_TAG="latest"
MAIN_WORKDIR="./src"
ACR_NAME="technicalwebscrapingacr"

usage() {
  echo "Usage: $0 -i <image_name> -f <dockerfile> [-t <image_tag>]"
  exit 1
}

# Parse arguments
while getopts ":i:f:t:" opt; do
  case $opt in
    i) IMAGE_NAME="$OPTARG" ;;
    f) DOCKERFILE="$OPTARG" ;;
    t) IMAGE_TAG="$OPTARG" ;;
    *) usage ;;
  esac
done

# Validate required args
if [[ -z "$IMAGE_NAME" || -z "$DOCKERFILE" ]]; then
  usage
fi

echo "Building and Pushing Docker Image to ACR"
echo "Image: $IMAGE_NAME:$IMAGE_TAG"
echo "Dockerfile: $DOCKERFILE"

cd "$MAIN_WORKDIR"

# Check Dockerfile
if [ ! -f "$DOCKERFILE" ]; then
  echo "Error: Dockerfile not found at $DOCKERFILE"
  exit 1
fi
echo "✓ Dockerfile found"


echo ""
echo "Building and pushing image using ACR Build..."
echo "This will take 3–5 minutes..."
echo ""

az acr build \
  --registry "$ACR_NAME" \
  --image "$IMAGE_NAME:$IMAGE_TAG" \
  --file "$DOCKERFILE" \
  .

echo "✓ Image Built and Pushed Successfully!"
