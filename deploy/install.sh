#!/usr/bin/env bash
# Первичная установка Deal Copilot на чистые машины. Повторный запуск безопасен:
# существующие настройки, пароль и токен не перезаписываются.
# Запуск с машины оператора из корня репозитория: deploy/install.sh
# После установки выполните deploy/release.sh, чтобы выложить код.
set -euo pipefail

SSH_OPTS=(-o BatchMode=yes ${KNOWN_HOSTS:+-o UserKnownHostsFile="$KNOWN_HOSTS"})
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "NORDIK: пользователь, каталоги, настройки, служба API"
scp -q "${SSH_OPTS[@]}" "$HERE/nordik/deal-copilot-api.service" nordik:/etc/systemd/system/
scp -q "${SSH_OPTS[@]}" "$HERE/nordik/backend.env.example" nordik:/tmp/deal-copilot-backend.env.example
ssh "${SSH_OPTS[@]}" nordik 'bash -s' <<'REMOTE'
set -euo pipefail
id dealcopilot >/dev/null 2>&1 || useradd --system --home /var/lib/deal-copilot --shell /usr/sbin/nologin dealcopilot
mkdir -p /opt/deal-copilot/releases /var/lib/deal-copilot/uploads /etc/deal-copilot /var/backups/deal-copilot
chown -R dealcopilot:dealcopilot /var/lib/deal-copilot
if [ ! -f /etc/deal-copilot/backend.env ]; then
  TOKEN=$(python3 -c "import secrets;print(secrets.token_urlsafe(40))")
  sed "s|^MODEL_ADMIN_TOKEN=.*|MODEL_ADMIN_TOKEN=$TOKEN|" /tmp/deal-copilot-backend.env.example > /etc/deal-copilot/backend.env
fi
chown root:dealcopilot /etc/deal-copilot/backend.env
chmod 640 /etc/deal-copilot/backend.env
systemctl daemon-reload
systemctl enable deal-copilot-api
REMOTE

echo "gala-msk: прокси с паролем, сеть, контейнеры, маршрут Traefik"
ssh "${SSH_OPTS[@]}" gala 'mkdir -p /opt/deal-copilot/proxy /opt/deal-copilot/releases'
scp -q "${SSH_OPTS[@]}" "$HERE/gala/nginx-default.conf" gala:/opt/deal-copilot/proxy/default.conf
scp -q "${SSH_OPTS[@]}" "$HERE/gala/traefik-deal-copilot.yml" gala:/opt/deal-copilot/proxy/traefik-deal-copilot.yml

# Пароль сайта: открытый текст хранится на NORDIK, на gala-msk — только хеш.
if ! ssh "${SSH_OPTS[@]}" gala test -s /opt/deal-copilot/proxy/htpasswd; then
  PASSWORD="$(ssh "${SSH_OPTS[@]}" nordik 'python3 -c "import secrets;print(secrets.token_urlsafe(18))"')"
  printf 'login: deal\npassword: %s\n' "$PASSWORD" | ssh "${SSH_OPTS[@]}" nordik \
    'umask 077; mkdir -p /opt/deal-copilot/secrets; cat > /opt/deal-copilot/secrets/web-basic-auth.txt'
  printf '%s' "$PASSWORD" | ssh "${SSH_OPTS[@]}" gala \
    'printf "deal:%s\n" "$(openssl passwd -apr1 -stdin)" > /opt/deal-copilot/proxy/htpasswd; chmod 644 /opt/deal-copilot/proxy/htpasswd'
  unset PASSWORD
fi

ssh "${SSH_OPTS[@]}" gala 'bash -s' <<'REMOTE'
set -euo pipefail
docker network inspect deal-copilot-net >/dev/null 2>&1 || docker network create deal-copilot-net >/dev/null
# Контейнер сайта создаёт deploy/release.sh: ему нужен уже выложенный релиз.
docker inspect deal-copilot-proxy >/dev/null 2>&1 || {
  docker run -d --name deal-copilot-proxy --restart unless-stopped \
    --network deal-copilot-net --memory 64m \
    -p 127.0.0.1:8095:80 -p 10.66.66.3:8095:80 \
    -v /opt/deal-copilot/proxy/default.conf:/etc/nginx/conf.d/default.conf:ro \
    -v /opt/deal-copilot/proxy/htpasswd:/etc/nginx/htpasswd:ro \
    nginx:alpine >/dev/null
  docker network connect dokploy-network deal-copilot-proxy
}
cp /opt/deal-copilot/proxy/traefik-deal-copilot.yml /etc/dokploy/traefik/dynamic/deal-copilot.yml
REMOTE

echo "ALEX: Ollama mini-PC для всей сети WireGuard"
scp -q "${SSH_OPTS[@]}" "$HERE/alex/ollama-wg-forward.service" alex:/etc/systemd/system/
ssh "${SSH_OPTS[@]}" alex 'command -v socat >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -qq socat >/dev/null; systemctl daemon-reload; systemctl enable --now ollama-wg-forward'

echo "Установка завершена. Дальше: deploy/release.sh main"
