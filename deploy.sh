#!/usr/bin/env bash
# Deploy heatline to Cloud Run.
#
# Aashan runs this. It is not run on his behalf: it creates billable cloud
# resources under his account, and the free tier only stays free if the
# settings below stay as they are.
#
# What has to be true first, all one-time:
#   1. A Google Cloud project with billing enabled.
#   2. gcloud installed:  brew install --cask google-cloud-sdk
#   3. gcloud auth login  (opens a browser; cannot be done from a script)
#   4. GEMENI_AI_BUILDER_API_KEY exported, or in the workspace .env
#
# Then:  ./deploy.sh <project-id>

set -euo pipefail

# The project behind Aashan's AI Studio key, confirmed from the console on
# 2026-09-27: "AI Builder Project", number 535892924661. Projects created for an
# AI Studio key usually have no billing account, and Cloud Run needs one, so
# that is the step to check first if a deploy is refused.
DEFAULT_PROJECT="gen-lang-client-0038192721"
PROJECT="${1:-${GOOGLE_CLOUD_PROJECT:-$DEFAULT_PROJECT}}"
SERVICE="${SERVICE:-heatline}"
REGION="${REGION:-asia-south1}"   # Mumbai, the closest region to Karachi

if ! command -v gcloud >/dev/null; then
  echo "gcloud is not installed. brew install --cask google-cloud-sdk" >&2
  exit 1
fi

# The key never goes on a command line that could land in shell history or in
# the build log. It is read here and passed as a secret-shaped env var.
KEY="${GOOGLE_API_KEY:-${GEMENI_AI_BUILDER_API_KEY:-}}"
if [[ -z "$KEY" ]]; then
  ENV_FILE="$(cd "$(dirname "$0")/../../.." && pwd)/.env"
  if [[ -f "$ENV_FILE" ]]; then
    KEY="$(grep -E '^[[:space:]]*GEMENI_AI_BUILDER_API_KEY=' "$ENV_FILE" \
           | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"
  fi
fi
if [[ -z "$KEY" ]]; then
  echo "no Gemini key found. Export GOOGLE_API_KEY first." >&2
  exit 1
fi

echo "project  $PROJECT"
echo "service  $SERVICE"
echo "region   $REGION"
echo

# Check authentication before anything else. Without it the billing probe below
# fails too, and reports a billing problem that may not exist: the first run of
# this script said billing was disabled when the real state was no credentialed
# account. Two different problems deserve two different messages.
if ! gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null \
     | grep -q .; then
  cat >&2 <<'MSG'
No authenticated gcloud account.

  gcloud auth login

That opens a browser, so it cannot be done from a script. Run it, then run this
again.
MSG
  exit 1
fi

gcloud config set project "$PROJECT" --quiet

# Fail early and legibly rather than part way through a build.
BILLING="$(gcloud beta billing projects describe "$PROJECT" \
           --format='value(billingEnabled)' 2>&1 || true)"
if ! printf '%s' "$BILLING" | grep -qi '^true$'; then
  cat >&2 <<MSG
Cloud Run needs billing on this project, and the check did not come back true.

  gcloud reported: ${BILLING:-<nothing>}

Enable it here:
  https://console.cloud.google.com/billing/linkedaccount?project=${PROJECT}

  https://console.cloud.google.com/billing/linkedaccount?project=gen-lang-client-0038192721

The free tier still applies: 2 million requests a month, and this service
scales to zero when idle, so an unvisited demo costs nothing. Enabling billing
is not the same as being charged.
MSG
  exit 1
fi
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com --quiet

# --source builds with Cloud Build, so no local Docker is needed.
#
# The flags are the free-tier shape, and each one matters:
#   min-instances 0   scale to zero, so an idle demo costs nothing
#   max-instances 3   a ceiling, so a traffic spike cannot run up a bill
#   memory 512Mi      numpy plus the ADK fit; 256Mi does not
#   concurrency 20    one container serves many readers of a cached forecast
#   timeout 120       the agent can take 20s, and a cold start adds to that
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 20 \
  --timeout 120 \
  --set-env-vars "GOOGLE_API_KEY=${KEY},HEATLINE_ADVISE_LIMIT=5,HEATLINE_ADVISE_WINDOW=3600" \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" \
        --format 'value(status.url)')"

echo
echo "live at $URL"
echo
echo "checks:"
curl -fsS "$URL/health" | head -c 300; echo
curl -fsS "$URL/assess" | head -c 200; echo
echo
echo "open $URL on a phone. The agent is capped at 5 questions per hour per"
echo "visitor; the readings are not capped."
