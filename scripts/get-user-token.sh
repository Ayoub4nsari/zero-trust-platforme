#!/usr/bin/env bash
# usage : ./scripts/get-user-token.sh [utilisateur]   (par défaut : sara ; mot de passe lu dans .env)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
docker compose exec -T -e U="${1:-sara}" -e P="$DEMO_USER_PASSWORD" reservation python -c "
import os,json,urllib.request,urllib.parse
d=urllib.parse.urlencode({'grant_type':'password','client_id':'reservation-web','username':os.environ['U'],'password':os.environ['P']}).encode()
r=urllib.request.urlopen('http://keycloak:8080/realms/zerotrust/protocol/openid-connect/token',d)
print(json.load(r)['access_token'])"