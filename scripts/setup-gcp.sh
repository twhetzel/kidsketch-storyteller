#!/usr/bin/env bash
# Idempotent GCP setup for KidSketch Storyteller: enable APIs, create dedicated
# backend service account, grant IAM roles, optionally create GCS bucket.
# Usage: PROJECT_ID=my-project GCS_BUCKET_NAME=my-bucket [REGION=us-central1] ./scripts/setup-gcp.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
GCS_BUCKET_NAME="${GCS_BUCKET_NAME:?Set GCS_BUCKET_NAME (e.g. kidsketch-storyteller)}"
REGION="${REGION:-us-central1}"
BACKEND_SA_NAME="kidsketch-backend"
BACKEND_SA_EMAIL="${BACKEND_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SECRET_NAME="gemini-api-key"

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: PROJECT_ID is not set and could not be read from gcloud config."
  echo "Usage: PROJECT_ID=my-project GCS_BUCKET_NAME=my-bucket ./scripts/setup-gcp.sh"
  exit 1
fi

echo "Using PROJECT_ID=$PROJECT_ID REGION=$REGION GCS_BUCKET_NAME=$GCS_BUCKET_NAME"
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  --project="$PROJECT_ID"

# Create dedicated backend service account if it doesn't exist
if ! gcloud iam service-accounts describe "$BACKEND_SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating service account $BACKEND_SA_EMAIL"
  gcloud iam service-accounts create "$BACKEND_SA_NAME" \
    --display-name="KidSketch Backend (Cloud Run)" \
    --project="$PROJECT_ID"
else
  echo "Service account $BACKEND_SA_EMAIL already exists"
fi

# Grant backend SA access to the GCS bucket (bucket-level IAM) with least privilege.
# legacyBucketWriter allows creating, overwriting, and listing objects without granting
# administrative control over object ACLs/IAM.
echo "Granting backend SA legacyBucketWriter access to GCS bucket gs://$GCS_BUCKET_NAME"
gsutil iam ch "serviceAccount:${BACKEND_SA_EMAIL}:legacyBucketWriter" "gs://${GCS_BUCKET_NAME}" 2>/dev/null || {
  echo "Note: Bucket gs://$GCS_BUCKET_NAME may not exist yet. Create it with: gsutil mb -p $PROJECT_ID -l $REGION gs://$GCS_BUCKET_NAME"
}

# Grant backend SA Vertex AI user (project-level)
echo "Granting backend SA Vertex AI (aiplatform.user) on project"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BACKEND_SA_EMAIL}" \
  --role="roles/aiplatform.user" \
  --quiet

# Grant backend SA access to Secret Manager secret (create secret if missing)
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
  echo "Granting backend SA access to secret $SECRET_NAME"
  gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
    --member="serviceAccount:${BACKEND_SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID" \
    --quiet
else
  echo "Secret $SECRET_NAME does not exist. Create it with:"
  echo "  echo -n 'YOUR_GEMINI_API_KEY' | gcloud secrets create $SECRET_NAME --data-file=- --project=$PROJECT_ID"
  echo "Then re-run this script to grant the backend SA access."
fi

# Ensure Cloud Build can deploy to Cloud Run (default Compute SA)
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
echo "Granting Cloud Build SA (run.builder) for deployments"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/run.admin" \
  --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet

# Optional: create GCS bucket if it doesn't exist
if ! gsutil ls "gs://${GCS_BUCKET_NAME}" &>/dev/null; then
  echo "Creating GCS bucket gs://$GCS_BUCKET_NAME"
  gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${GCS_BUCKET_NAME}"
  echo "Granting backend SA legacyBucketWriter access to newly created bucket gs://$GCS_BUCKET_NAME"
  gsutil iam ch "serviceAccount:${BACKEND_SA_EMAIL}:legacyBucketWriter" "gs://${GCS_BUCKET_NAME}"
fi

# Artifact Registry repo for frontend image (used by deploy.sh)
AR_REPO="cloud-run-images"
if ! gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  echo "Creating Artifact Registry repository $AR_REPO"
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT_ID"
fi

echo "Setup complete. Backend SA: $BACKEND_SA_EMAIL"
