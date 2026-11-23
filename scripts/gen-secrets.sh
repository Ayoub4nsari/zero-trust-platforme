#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p secrets && chmod 700 secrets
RES=$(openssl rand -hex 32); WRONG=$(openssl rand -hex 32); ADM=$(openssl rand -hex 16)
DEMO=$(openssl rand -hex 12); REG=$(openssl rand -hex 24)
umask 077
cat > .env <<EOT
KEYCLOAK_ADMIN_PASSWORD=$ADM
RESERVATION_CLIENT_SECRET=$RES
WRONG_SCOPE_CLIENT_SECRET=$WRONG
DEMO_USER_PASSWORD=$DEMO
REGISTRATION_CLIENT_SECRET=$REG
EOT
printf '%s' "$RES" > secrets/reservation_client_secret
printf '%s' "$REG" > secrets/registration_client_secret
chmod 644 secrets/reservation_client_secret secrets/registration_client_secret
echo "Secrets générés dans .env et secrets/"