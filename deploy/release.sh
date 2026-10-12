#!/usr/bin/env bash
# Выпуск Deal Copilot: API на NORDIK, сайт на gala-msk.
# Запуск с машины оператора из корня репозитория: deploy/release.sh [git-ref]
# Нужны SSH-алиасы nordik и gala (см. docs/deployment-architecture.md).
# Перед выпуском делает копию базы, загрузок и настроек; прежний релиз остаётся для отката.
set -euo pipefail

REF="${1:-main}"
SSH_OPTS=(-o BatchMode=yes ${KNOWN_HOSTS:+-o UserKnownHostsFile="$KNOWN_HOSTS"})
C="$(git rev-parse --short "$REF")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Выпуск $C ($REF)"
git archive --format=tar.gz -o "$TMP/dc-$C.tgz" "$C"
scp -q "${SSH_OPTS[@]}" "$TMP/dc-$C.tgz" nordik:/tmp/
scp -q "${SSH_OPTS[@]}" "$TMP/dc-$C.tgz" gala:/tmp/

echo "NORDIK: копия данных и новый релиз API"
ssh "${SSH_OPTS[@]}" nordik "C=$C bash -s" <<'REMOTE'
set -euo pipefail
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p /var/backups/deal-copilot
sqlite3 /var/lib/deal-copilot/deal_copilot.db ".backup /var/backups/deal-copilot/deal_copilot-$TS.db"
tar -czf /var/backups/deal-copilot/uploads-$TS.tgz -C /var/lib/deal-copilot uploads
install -m 600 /etc/deal-copilot/backend.env /var/backups/deal-copilot/backend.env-$TS
R=/opt/deal-copilot/releases/$C
mkdir -p "$R" && tar -xzf /tmp/dc-$C.tgz -C "$R"
cd "$R/backend"
python3.11 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q .
echo "прежний релиз: $(readlink /opt/deal-copilot/current || echo нет)"
ln -sfn "$R" /opt/deal-copilot/current
systemctl restart deal-copilot-api
sleep 6
curl -fsS http://10.66.66.16:8020/api/health; echo

# Сайт собирается здесь: на gala-msk мало памяти и нет Node.js.
W=/root/deal-copilot-build/$C
rm -rf "$W"; mkdir -p "$W"; tar -xzf /tmp/dc-$C.tgz -C "$W" frontend
cd "$W/frontend"
echo "NEXT_PUBLIC_API_URL=/api" > .env.production.local
npm ci --no-audit --no-fund --loglevel=error >/dev/null
npm run build >/dev/null
npm prune --omit=dev --no-audit --no-fund --loglevel=error >/dev/null
tar -czf /tmp/dc-web-$C.tgz package.json package-lock.json .next node_modules
REMOTE

echo "gala-msk: новый релиз сайта"
scp -3 -q "${SSH_OPTS[@]}" "nordik:/tmp/dc-web-$C.tgz" gala:/tmp/
ssh "${SSH_OPTS[@]}" gala "C=$C bash -s" <<'REMOTE'
set -euo pipefail
R=/opt/deal-copilot/releases/$C
mkdir -p "$R/frontend"
tar -xzf /tmp/dc-$C.tgz -C "$R"
tar -xzf /tmp/dc-web-$C.tgz -C "$R/frontend"
echo "прежний релиз: $(readlink /opt/deal-copilot/current || echo нет)"
ln -sfn "$R" /opt/deal-copilot/current
if docker inspect deal-copilot-web >/dev/null 2>&1; then
  docker restart deal-copilot-web >/dev/null
else
  docker run -d --name deal-copilot-web --restart unless-stopped     --network deal-copilot-net --memory 512m     -e NODE_ENV=production -e NEXT_TELEMETRY_DISABLED=1     -v /opt/deal-copilot/current/frontend:/app:ro -w /app     node:22-slim node node_modules/next/dist/bin/next start -H 0.0.0.0 -p 3000 >/dev/null
fi
sleep 8
echo "сайт без пароля: $(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8095/) (ожидается 401)"
REMOTE

echo "Готово: $C. Проверьте https://deal-copilot.tools01.ru"
