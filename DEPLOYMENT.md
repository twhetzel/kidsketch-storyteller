# Deploying KidSketch Storyteller to Google Cloud

This document describes how to run the app on **Google Cloud Platform (GCP)** using **Cloud Run** for both the backend (FastAPI) and frontend (Next.js), so the agents are hosted on Google Cloud as required by the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/).

---

## Architecture on GCP

- **Backend** (FastAPI): Cloud Run service `kidsketch-backend`. Uses a dedicated service account with access to Cloud Storage, Vertex AI, and Secret Manager. No key file on Cloud Run; the service identity is used automatically.
- **Frontend** (Next.js): Cloud Run service `kidsketch-frontend`. Built with `NEXT_PUBLIC_API_URL` set to the backend URL.
- **Secrets**: `GEMINI_API_KEY` is stored in Secret Manager and injected into the backend at runtime.
- **Storage**: Google Cloud Storage bucket for sketches, images, audio, and exported movies.
- **AI**: Vertex AI (Imagen 3) and Gemini API (including Multimodal Live) are called from the backend.

---

## Prerequisites

1. **Google Cloud CLI**  
   Install and authenticate: [Install gcloud](https://cloud.google.com/sdk/docs/install).

2. **GCP project**  
   Create or select a project and ensure billing is enabled.

3. **Gemini API key**  
   You will store it in Secret Manager (see below).

---

## One-time setup

### 1. Create the Secret Manager secret

Store your Gemini API key in Secret Manager so the backend can use it without env vars:

```bash
# Replace with your actual key
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=- --project=YOUR_PROJECT_ID
```

If the secret already exists, add a new version:

```bash
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=- --project=YOUR_PROJECT_ID
```

### 2. Run the setup script (APIs, service account, IAM)

This enables required APIs, creates the dedicated backend service account, and grants it access to the bucket, Vertex AI, and the secret:

```bash
export PROJECT_ID=your-gcp-project-id
export GCS_BUCKET_NAME=your-bucket-name   # e.g. kidsketch-storyteller
export REGION=us-central1                 # optional; default us-central1

./scripts/setup-gcp.sh
```

The script is idempotent. It will create the GCS bucket if it does not exist and an Artifact Registry repository for the frontend image.

---

## Deploy (automated)

From the repository root:

```bash
export PROJECT_ID=your-gcp-project-id
export GCS_BUCKET_NAME=your-bucket-name
# Optional: REGION=us-central1

./scripts/deploy.sh
```

Or with positional arguments:

```bash
./scripts/deploy.sh your-gcp-project-id your-bucket-name us-central1
```

The script will:

1. Run `scripts/setup-gcp.sh` if needed.
2. Deploy the backend from `backend/` to Cloud Run with the dedicated service account and Secret Manager for `GEMINI_API_KEY`.
3. Build the frontend Docker image with `NEXT_PUBLIC_API_URL` set to the backend URL.
4. Deploy the frontend to Cloud Run.

At the end it prints the frontend and backend URLs. Open the frontend URL in a browser.

---

## Updating the app after code changes

When you change the backend or frontend code and want to roll out an update to Cloud Run:

1. Make sure your local `.env` does **not** set `GOOGLE_APPLICATION_CREDENTIALS` when deploying to Cloud Run.  
   - You can keep `GOOGLE_APPLICATION_CREDENTIALS=...` for local development, but comment it out or remove it before running `./scripts/deploy.sh` so the container does not try to use a local path.
2. From the repository root, set the variables for your project and bucket (only needed once per terminal session):

```bash
export PROJECT_ID=your-gcp-project-id
export GCS_BUCKET_NAME=your-bucket-name
export REGION=us-central1   # optional; defaults to us-central1 if omitted
```

3. Redeploy both services:

```bash
./scripts/deploy.sh
```

The script will:

- Build and deploy a new backend revision to Cloud Run using the attached `kidsketch-backend` service account and Secret Manager for `GEMINI_API_KEY` (no key file needed).
- Build a new frontend image with `NEXT_PUBLIC_API_URL` pointing at the current backend URL.
- Deploy a new frontend revision to Cloud Run.

You do **not** need to re-run `scripts/setup-gcp.sh` for normal code updates; that script is only required when you first set up the project or change IAM / buckets / regions.

---

## Manual deployment (step-by-step)

If you prefer to run commands yourself:

### Backend

```bash
cd backend
gcloud run deploy kidsketch-backend \
  --source=. \
  --region=REGION \
  --service-account=kidsketch-backend@PROJECT_ID.iam.gserviceaccount.com \
  --set-secrets=GEMINI_API_KEY=gemini-api-key:latest \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=PROJECT_ID,GCS_BUCKET_NAME=BUCKET_NAME,ALLOWED_ORIGINS=* \
  --allow-unauthenticated
```

Record the service URL (e.g. `https://kidsketch-backend-xxxxx.run.app`).

### Frontend

Build the image with the backend URL, then deploy:

```bash
# From repo root; BACKEND_URL is the URL from the previous step
gcloud builds submit frontend \
  --config=frontend/cloudbuild.yaml \
  --substitutions=_NEXT_PUBLIC_API_URL=BACKEND_URL,_REGION=REGION

gcloud run deploy kidsketch-frontend \
  --image=REGION-docker.pkg.dev/PROJECT_ID/cloud-run-images/kidsketch-frontend:latest \
  --region=REGION \
  --allow-unauthenticated
```

---

## Proof of GCP deployment (hackathon)

To show that the backend runs on Google Cloud:

1. **Screen recording (recommended)**  
   Record a short clip that shows:
   - The [Cloud Run](https://console.cloud.google.com/run) console with both services (e.g. `kidsketch-backend`, `kidsketch-frontend`) listed.
   - The app loading in a browser from the frontend URL.

2. **Code**  
   The repo already uses GCP in the backend (e.g. `google-cloud-storage`, `google-cloud-aiplatform`, Vertex AI and GCS calls), which supports that the agent runs on GCP.

---

## CORS and WebSockets

- The deploy script sets `ALLOWED_ORIGINS=*` so the frontend can call the backend from its Cloud Run URL. For production you can restrict this to the frontend URL (see optional step in `scripts/deploy.sh`).
- Cloud Run supports WebSockets; the live voice path (frontend → backend WebSocket → Gemini Multimodal Live) works without extra configuration.

---

## Troubleshooting

- **Backend 500 / auth errors**  
  Ensure the Secret Manager secret `gemini-api-key` exists and the backend service account has `roles/secretmanager.secretAccessor` on it (run `./scripts/setup-gcp.sh` again).

- **Frontend can’t reach backend**  
  Confirm the frontend was built with the correct `NEXT_PUBLIC_API_URL` (the backend Cloud Run URL). Rebuild and redeploy the frontend if you changed the backend URL.

- **Storage or Vertex errors**  
  Re-run `./scripts/setup-gcp.sh` so the backend service account has the correct IAM roles (Storage on the bucket, `roles/aiplatform.user` on the project).
