#!/usr/bin/env bash
set -euo pipefail
SRC=/vagrant
DST="$HOME/zero-trust-platforme"
mkdir -p "$DST"

rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude '__pycache__' --exclude '.vagrant' \
  --exclude '.env' --exclude 'secrets' --exclude 'certs' \
  "$SRC"/ "$DST"/
cd "$DST"

find . -type f \( -name '*.sh' -o -name '*.py' -o -name '*.yml' -o -name '*.json' \
  -o -name 'Caddyfile' -o -name 'Dockerfile' -o -name '*.txt' \) -exec sed -i 's/\r$//' {} +
chmod +x scripts/*.sh

[ -f .env ] || ./scripts/gen-secrets.sh
grep -q '^DEMO_USER_PASSWORD=' .env || echo "DEMO_USER_PASSWORD=$(openssl rand -hex 12)" >> .env
[ -f certs/ca.crt ] || ./scripts/gen-certs.sh

grep -q '^REGISTRATION_CLIENT_SECRET=' .env || echo "REGISTRATION_CLIENT_SECRET=$(openssl rand -hex 24)" >> .env
[ -f secrets/registration_client_secret ] || {
  printf '%s' "$(grep '^REGISTRATION_CLIENT_SECRET=' .env | cut -d= -f2-)" > secrets/registration_client_secret
  chmod 644 secrets/registration_client_secret
}

sudo docker compose config -q
sudo docker compose up -d --build

echo "Attente de Keycloak (premier démarrage ~1 min)..."
for i in $(seq 1 60); do
  sudo docker logs keycloak 2>&1 | grep -q "started in" && break
  sleep 3
done
sudo docker compose ps
echo "Déploiement terminé : https://localhost:8443 (depuis Windows)"