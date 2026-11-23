#!/usr/bin/env bash
# usage : ./scripts/get-token.sh [reservation|wrong]
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
if [ "${1:-reservation}" = "wrong" ]; then ID=wrong-scope-client; SEC=$WRONG_SCOPE_CLIENT_SECRET
else ID=reservation-service; SEC=$RESERVATION_CLIENT_SECRET; fi
docker compose exec -T -e ID="$ID" -e SEC="$SEC" reservation python -c "
import os,json,urllib.request,urllib.parse
d=urllib.parse.urlencode({'grant_type':'client_credentials','client_id':os.environ['ID'],'client_secret':os.environ['SEC']}).encode()
r=urllib.request.urlopen('http://keycloak:8080/realms/zerotrust/protocol/openid-connect/token',d)
print(json.load(r)['access_token'])"
