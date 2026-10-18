#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# 1️⃣ Variables – adjust only if you renamed the defaults.
# ------------------------------------------------------------
DEPLOY_PATH="/home/ubuntu/app"          # <- same as DEPLOY_PATH secret
ENV_FILE="$DEPLOY_PATH/.env"
COMPOSE_FILE="$DEPLOY_PATH/docker-compose.prod.yml"

# ------------------------------------------------------------
# 2️⃣ Helper: ensure Docker & Docker‑Compose are available.
# ------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found – install it first" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose plugin not found – install it first" >&2
  exit 1
fi

# ------------------------------------------------------------
# 3️⃣ Create (or overwrite) .env using the environment variables
#    that the GitHub Actions runner exported when it SSH‑ed in.
# ------------------------------------------------------------
cat > "$ENV_FILE" <<'EOF'
DATABASE_URL="${DATABASE_URL}"
JWT_SECRET="${JWT_SECRET}"
SUPER_ADMIN_EMAIL="${SUPER_ADMIN_EMAIL}"
SECRETS_ENCRYPTION_KEY="${SECRETS_ENCRYPTION_KEY}"
GOOGLE_AI_API_KEY="${GOOGLE_AI_API_KEY:-}"
ADZUNA_APP_ID="${ADZUNA_APP_ID:-}"
ADZUNA_APP_KEY="${ADZUNA_APP_KEY:-}"
JSEARCH_API_KEY="${JSEARCH_API_KEY:-}"
NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL}"
EOF

chmod 600 "$ENV_FILE"

# ------------------------------------------------------------
# 4️⃣ Pull the latest images from GHCR (requires PAT).
# ------------------------------------------------------------
# The PAT is passed in the SSH session as the env var GHCR_PAT.
# We log in once; Docker caches the credentials for the session.

echo "$GHCR_PAT" | docker login ghcr.io -u "${GITHUB_ACTOR}" --password-stdin

# ------------------------------------------------------------
# 5️⃣ Pull and start the stack (detached).
# ------------------------------------------------------------
cd "$DEPLOY_PATH"

docker compose -f "$COMPOSE_FILE" pull

docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# ------------------------------------------------------------
# 6️⃣ Verify that everything is up.
# ------------------------------------------------------------
docker compose -f "$COMPOSE_FILE" ps

echo "✅ Deployment finished. Backend → http://<tailscale_ip>:8000   Front‑end → http://<tailscale_ip>:3100"
