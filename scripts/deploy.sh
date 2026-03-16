#!/usr/bin/env bash
# Deploy KidSketch Storyteller to GCP: backend and frontend to Cloud Run.
# Usage:
#   PROJECT_ID=my-project GCS_BUCKET_NAME=my-bucket ./scripts/deploy.sh
#   Or: ./scripts/deploy.sh my-project my-bucket [us-central1]
# Requires: gcloud CLI, and Secret Manager secret "gemini-api-key" with your GEMINI_API_KEY.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Project and region
if [[ -n "$3" ]]; then
  export PROJECT_ID="$1"
  export GCS_BUCKET_NAME="$2"
  export REGION="${3:-us-central1}"
elif [[ -n "$1" && -n "$2" ]]; then
  export PROJECT_ID="$1"
  export GCS_BUCKET_NAME="$2"
  export REGION="${REGION:-us-central1}"
else
  export PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
  export GCS_BUCKET_NAME="${GCS_BUCKET_NAME:?Set GCS_BUCKET_NAME (e.g. kidsketch-storyteller)}"
  export REGION="${REGION:-us-central1}"
fi

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: PROJECT_ID is not set."
  echo "Usage: PROJECT_ID=my-project GCS_BUCKET_NAME=my-bucket [REGION=us-central1] ./scripts/deploy.sh"
  exit 1
fi

BACKEND_SA_EMAIL="kidsketch-backend@${PROJECT_ID}.iam.gserviceaccount.com"
BACKEND_SERVICE="kidsketch-backend"
FRONTEND_SERVICE="kidsketch-frontend"
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-images/kidsketch-frontend:latest"

echo "Deploying to PROJECT_ID=$PROJECT_ID REGION=$REGION GCS_BUCKET_NAME=$GCS_BUCKET_NAME"
gcloud config set project "$PROJECT_ID"

# 1. GCP setup (APIs, service account, IAM)
"$SCRIPT_DIR/setup-gcp.sh"

# 2. Deploy backend first (allow unauthenticated for hackathon; restrict later if needed)
echo "Deploying backend from $REPO_ROOT/backend..."
gcloud run deploy "$BACKEND_SERVICE" \
  --source="$REPO_ROOT/backend" \
  --region="$REGION" \
  --platform=managed \
  --service-account="$BACKEND_SA_EMAIL" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GCS_BUCKET_NAME=${GCS_BUCKET_NAME},ALLOWED_ORIGINS=*" \
  --allow-unauthenticated \
  --quiet

BACKEND_URL="$(gcloud run services describe "$BACKEND_SERVICE" --region="$REGION" --format='value(status.url)' | tr -d '\r')"
echo "Backend URL: $BACKEND_URL"

# 3. Build frontend image with backend URL (build-time)
echo "Building frontend image with NEXT_PUBLIC_API_URL=$BACKEND_URL"
gcloud builds submit "$REPO_ROOT/frontend" \
  --config="$REPO_ROOT/frontend/cloudbuild.yaml" \
  --substitutions="_NEXT_PUBLIC_API_URL=${BACKEND_URL},_REGION=${REGION}" \
  --project="$PROJECT_ID"

# 4. Deploy frontend to Cloud Run
echo "Deploying frontend..."
gcloud run deploy "$FRONTEND_SERVICE" \
  --image="$FRONTEND_IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --quiet

FRONTEND_URL="$(gcloud run services describe "$FRONTEND_SERVICE" --region="$REGION" --format='value(status.url)' | tr -d '\r')"

# 5. Optional: tighten CORS by updating backend with frontend origin (comment out to keep ALLOWED_ORIGINS=*)
# echo "Updating backend ALLOWED_ORIGINS to $FRONTEND_URL"
# gcloud run services update "$BACKEND_SERVICE" --region="$REGION" \
#   --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GCS_BUCKET_NAME=${GCS_BUCKET_NAME},ALLOWED_ORIGINS=${FRONTEND_URL}" \
#   --quiet

echo ""
echo "Deployment complete."
echo "  Frontend: $FRONTEND_URL"
echo "  Backend:  $BACKEND_URL"
