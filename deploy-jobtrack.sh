#!/usr/bin/env bash
#
# JobTrack AI — deploy script for your homelab server.
#
# What it does, in order:
#   1. Shows what's currently running (listening ports + Docker containers)
#      so you can see conflicts BEFORE anything is installed.
#   2. Checks the specific ports this app wants (8000, 3100) and warns if
#      something is already bound to them.
#   3. Unzips the app into an install directory.
#   4. Sets up .env (prompts for the few values that must be real).
#   5. Runs docker compose up -d --build.
#
# Usage:
#   chmod +x deploy-jobtrack.sh
#   ./deploy-jobtrack.sh /path/to/jobtrack-ai.zip
#
# Safe to re-run: if the install directory already exists, it will ask
# before overwriting anything.

set -euo pipefail

ZIP_PATH="${1:-}"
INSTALL_DIR="${2:-$HOME/apps/jobtrack-ai}"
BACKEND_PORT=8000
FRONTEND_PORT=3100

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
red() { printf "\033[31m%s\033[0m\n" "$1"; }

if [[ -z "$ZIP_PATH" ]]; then
  red "Usage: $0 /path/to/jobtrack-ai.zip [install-dir]"
  exit 1
fi
if [[ ! -f "$ZIP_PATH" ]]; then
  red "Zip file not found: $ZIP_PATH"
  exit 1
fi

# ---------------------------------------------------------------------------
echo
bold "== Step 1: What's currently running on this server =="
echo

bold "-- Listening ports (TCP) --"
if command -v ss >/dev/null 2>&1; then
  sudo ss -tlnp 2>/dev/null || ss -tlnp
else
  sudo netstat -tlnp 2>/dev/null || netstat -tlnp
fi

echo
bold "-- Docker containers currently running --"
if command -v docker >/dev/null 2>&1; then
  docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
else
  yellow "Docker is not installed yet. Install it first: https://docs.docker.com/engine/install/ubuntu/"
  echo "(the rest of this script needs Docker + the Compose plugin to actually install the app)"
fi

# ---------------------------------------------------------------------------
echo
bold "== Step 2: Checking the ports JobTrack AI wants =="
echo

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tln | awk '{print $4}' | grep -qE "[:.]${port}\$"
  else
    netstat -tln 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"
  fi
}

CONFLICT=0
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if port_in_use "$port"; then
    red "  Port $port is already in use."
    CONFLICT=1
  else
    green "  Port $port is free."
  fi
done

if [[ "$CONFLICT" -eq 1 ]]; then
  echo
  yellow "One or more ports above are already taken. Before continuing, either:"
  yellow "  a) stop whatever is using that port, or"
  yellow "  b) edit docker-compose.yml after unzipping and change the host-side"
  yellow "     port (the LEFT number in \"HOST:CONTAINER\", e.g. \"3100:3000\")."
  echo
  read -rp "Continue anyway? [y/N] " CONFIRM
  if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Aborted. Fix the conflict and re-run this script."
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
echo
bold "== Step 3: Installing to $INSTALL_DIR =="
echo

if [[ -d "$INSTALL_DIR" ]]; then
  yellow "Install directory already exists: $INSTALL_DIR"
  read -rp "Overwrite its contents? [y/N] " OVERWRITE
  if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
    echo "Aborted. Choose a different install dir: $0 $ZIP_PATH /some/other/path"
    exit 1
  fi
  rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"
unzip -q "$ZIP_PATH" -d "$INSTALL_DIR"
green "Unzipped to $INSTALL_DIR"

cd "$INSTALL_DIR"

# ---------------------------------------------------------------------------
echo
bold "== Step 4: Setting up .env =="
echo

if [[ ! -f ".env" ]]; then
  cp .env.example .env

  TS_IP=$(command -v tailscale >/dev/null 2>&1 && tailscale ip -4 2>/dev/null || true)
  DEFAULT_HOST="${TS_IP:-localhost}"

  read -rp "Email to use as super admin: " ADMIN_EMAIL
  JWT_SECRET=$(openssl rand -hex 32)
  SECRETS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")

  if [[ -z "$SECRETS_KEY" ]]; then
    red "Couldn't auto-generate SECRETS_ENCRYPTION_KEY (python3/cryptography not found)."
    yellow "Install it or generate manually, then edit SECRETS_ENCRYPTION_KEY in .env before starting."
  fi

  sed -i "s|SUPER_ADMIN_EMAIL=.*|SUPER_ADMIN_EMAIL=${ADMIN_EMAIL}|" .env
  sed -i "s|JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" .env
  sed -i "s|SECRETS_ENCRYPTION_KEY=.*|SECRETS_ENCRYPTION_KEY=${SECRETS_KEY}|" .env
  sed -i "s|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=http://${DEFAULT_HOST}:${BACKEND_PORT}|" .env
  sed -i "s|FRONTEND_ORIGIN=.*|FRONTEND_ORIGIN=http://${DEFAULT_HOST}:${FRONTEND_PORT}|" .env

  echo
  yellow "Optional: Google AI (Gemini) key enables automatic inbox analysis"
  yellow "(reads connected users' inboxes for job replies/alerts). Get a free"
  yellow "key at https://aistudio.google.com/apikey \u2014 or press Enter to skip"
  yellow "(inbox analysis just stays off; everything else still works)."
  read -rp "Gemini API key (optional): " GEMINI_KEY
  if [[ -n "$GEMINI_KEY" ]]; then
    sed -i "s|GOOGLE_AI_API_KEY=.*|GOOGLE_AI_API_KEY=${GEMINI_KEY}|" .env
  fi

  green ".env created and filled in automatically."
  yellow "Double-check it before/after first boot: $INSTALL_DIR/.env"
else
  yellow ".env already exists — leaving it as-is."
fi

# ---------------------------------------------------------------------------
echo
bold "== Step 5: Building and starting the app =="
echo

if ! command -v docker >/dev/null 2>&1; then
  red "Docker isn't installed — stopping here. Install Docker + Compose, then run:"
  echo "  cd $INSTALL_DIR && docker compose up -d --build"
  exit 1
fi

docker compose up -d --build

echo
green "Done. Containers:"
docker compose ps

echo
bold "Backend:   http://<this-server>:${BACKEND_PORT}/docs"
bold "Frontend:  http://<this-server>:${FRONTEND_PORT}"
echo
yellow "Register with the super-admin email you entered above first — that account becomes admin automatically."
echo
echo "Watch logs with:  cd $INSTALL_DIR && docker compose logs -f"
