#!/usr/bin/env bash
# One-command install/update of the calorie tracker + Telegram bot on an Ubuntu VPS.
#
# Run as root on the server:
#   curl -fsSL https://raw.githubusercontent.com/denis313/KBGU/claude/nifty-johnson-63kr58/deploy/install.sh \
#     | DOMAIN=example.com TELEGRAM_BOT_TOKEN=123:ABC bash
#
# Without TELEGRAM_BOT_TOKEN the script asks for it (input is hidden).
# Re-running is safe: it updates the code and keeps existing secrets and data.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/denis313/KBGU.git}"
BRANCH="${BRANCH:-claude/nifty-johnson-63kr58}"
APP_DIR="${APP_DIR:-/opt/calorie-tracker}"

say()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo -i, then repeat the command."
command -v apt-get >/dev/null || die "This script supports Ubuntu/Debian only."

if [ -z "${DOMAIN:-}" ] && [ -f "$APP_DIR/.env" ]; then
  DOMAIN="$(grep -E '^DOMAIN=' "$APP_DIR/.env" | cut -d= -f2- || true)"
fi
[ -n "${DOMAIN:-}" ] || die "Set DOMAIN, e.g.: DOMAIN=example.com"
DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN%%/*}"

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ -f "$APP_DIR/.env" ]; then
  TELEGRAM_BOT_TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$APP_DIR/.env" | cut -d= -f2- || true)"
fi
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  read -rsp "Telegram bot token from @BotFather: " TELEGRAM_BOT_TOKEN </dev/tty; echo
fi
[[ "$TELEGRAM_BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || die "That does not look like a bot token (expected 123456:ABC...)."

say "Installing base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl openssl ca-certificates iproute2 >/dev/null

say "Checking that $DOMAIN points to this server"
server_ip="$(curl -fsS4 -m 10 https://api.ipify.org || curl -fsS4 -m 10 https://ifconfig.me || true)"
domain_ip="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1 {print $1}' || true)"
echo "server IP: ${server_ip:-unknown}, $DOMAIN -> ${domain_ip:-not resolved}"
if [ -z "$domain_ip" ]; then
  die "$DOMAIN does not resolve yet. Create an A record pointing to ${server_ip:-this server} and retry."
elif [ -n "$server_ip" ] && [ "$server_ip" != "$domain_ip" ]; then
  warn "$DOMAIN points to $domain_ip, but this server is $server_ip."
  warn "HTTPS will not work until the A record is changed to $server_ip (continuing anyway)."
fi

say "Installing Docker"
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  if ! curl -fsSL https://get.docker.com | sh; then
    warn "get.docker.com failed, installing Docker from Ubuntu repositories"
    apt-get install -y -qq docker.io docker-compose-v2 >/dev/null
  fi
fi
systemctl enable --now docker >/dev/null 2>&1 || true
docker compose version >/dev/null || die "Docker Compose is not available."

if ! docker pull -q caddy:2 >/dev/null 2>&1; then
  if [ ! -f /etc/docker/daemon.json ]; then
    warn "Docker Hub is unreachable, switching to the mirror.gcr.io registry mirror"
    echo '{"registry-mirrors": ["https://mirror.gcr.io"]}' > /etc/docker/daemon.json
    systemctl restart docker
  fi
  docker pull -q caddy:2 >/dev/null || die "Cannot download Docker images (Docker Hub and mirror both failed)."
fi

say "Checking ports 80 and 443"
busy="$(ss -ltnpH '( sport = :80 or sport = :443 )' | grep -v docker-proxy || true)"
if [ -n "$busy" ]; then
  echo "$busy"
  die "Ports 80/443 are used by another web server (nginx/apache?). Stop it, e.g.: systemctl disable --now nginx apache2"
fi
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp >/dev/null; ufw allow 443 >/dev/null
fi

say "Downloading the app into $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch -q origin "$BRANCH"
  git -C "$APP_DIR" checkout -q -B "$BRANCH" "origin/$BRANCH"
else
  git clone -q -b "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

say "Writing settings to $APP_DIR/.env"
touch .env && chmod 600 .env
set_env() {  # set KEY=VALUE, replacing an existing line
  grep -v "^$1=" .env > .env.tmp || true
  printf '%s=%s\n' "$1" "$2" >> .env.tmp
  mv .env.tmp .env && chmod 600 .env
}
keep_or_generate() {  # never rotate existing secrets: POSTGRES_PASSWORD is baked into the database volume
  grep -qE "^$1=.+" .env || set_env "$1" "$(openssl rand -hex "$2")"
}
set_env COMPOSE_FILE docker-compose.prod.yml
set_env DOMAIN "$DOMAIN"
set_env TELEGRAM_BOT_TOKEN "$TELEGRAM_BOT_TOKEN"
keep_or_generate SECRET_KEY 32
keep_or_generate POSTGRES_PASSWORD 24
keep_or_generate TELEGRAM_WEBHOOK_SECRET 32

say "Building and starting (the first run takes a few minutes)"
docker compose up -d --build

say "Waiting for https://$DOMAIN"
for _ in $(seq 1 40); do
  if curl -fsS -m 5 "https://$DOMAIN/api/health" >/dev/null 2>&1; then
    echo "https://$DOMAIN is up"
    docker compose logs api 2>/dev/null | grep -E "Bot @|Telegram bot setup failed" | tail -1 || true
    say "Done. Open your bot in Telegram and send /start"
    echo "Logs:    cd $APP_DIR && docker compose logs -f api"
    echo "Webhook: cd $APP_DIR && docker compose exec api python -m app.bot info"
    exit 0
  fi
  sleep 5
done

warn "https://$DOMAIN did not respond within ~3 minutes. Recent logs:"
docker compose ps
docker compose logs --tail 30 caddy api
die "See the 'If something does not work' section in DEPLOY.md."
