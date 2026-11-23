#!/usr/bin/env bash
# usage : ./scripts/demo.sh [--expired]   (--expired attend 5 min pour tester un token expiré)
set -uo pipefail
cd "$(dirname "$0")/.."
PASS=0; FAIL=0

check() {  # nom, attendu, obtenu
  if [ "$2" = "$3" ]; then echo "[PASS] $1 (attendu $2)"; PASS=$((PASS+1))
  else echo "[FAIL] $1 (attendu $2, obtenu $3)"; FAIL=$((FAIL+1)); fi
}

call() {  # token chemin méthode -> code HTTP renvoyé par Notification (via Réservation, avec mTLS)
  docker compose exec -T -e T="$1" reservation python -c "
import os
from app.notify_client import _client, NOTIFICATION_URL
h={'Authorization':'Bearer '+os.environ['T']} if os.environ['T'] else {}
r=_client.request('$3',NOTIFICATION_URL+'$2',headers=h,json={'reservation_id':'1','user':'demo','room':'A1','date':'2026-12-01'} if '$3'=='POST' else None)
print(r.status_code)" 2>/dev/null | tr -d '\r'
}

code() {  # code HTTP d'une requête vers Réservation, via Caddy (HTTPS)
  curl -s -o /dev/null -w '%{http_code}' --cacert certs/caddy-root.crt "$@"
}

TOKEN=$(./scripts/get-token.sh | tr -d '\r'); WTOKEN=$(./scripts/get-token.sh wrong | tr -d '\r')
UTOKEN=$(./scripts/get-user-token.sh | tr -d '\r')
[ -n "$TOKEN" ] && [ -n "$WTOKEN" ] && [ -n "$UTOKEN" ] || { echo "Impossible d'obtenir les tokens (Keycloak prêt ?)"; exit 2; }
set -a; source .env; set +a
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt certs/caddy-root.crt >/dev/null 2>&1

echo "=== Démo 1 : requête légitime (utilisateur authentifié) ==="
body=$(curl -s --cacert certs/caddy-root.crt -X POST https://localhost:8443/reservations \
  -H "Authorization: Bearer $UTOKEN" -H 'content-type: application/json' \
  -d '{"room":"A1","date":"2026-12-01"}')
echo "$body" | grep -q '"status":"sent"' && r=sent || r=failed
check "Réservation par un utilisateur, puis notification" sent "$r"
check "Appel direct /notify avec token valide" 200 "$(call "$TOKEN" /notify POST)"

echo "=== Démo 2 : sans certificat client ==="
r=$(docker compose exec -T reservation python -c "
import ssl,urllib.request
ctx=ssl.create_default_context(cafile='/run/secrets/ca_cert')
try:
    urllib.request.urlopen('https://notification:8002/health',context=ctx,timeout=5); print('CONNECTED')
except Exception: print('REJECTED')" 2>/dev/null | tr -d '\r')
check "Connexion TLS sans certificat client" REJECTED "$r"

echo "=== Démo 3 : token invalide, mauvais scope ==="
check "Mauvais scope (notify:read)" 403 "$(call "$WTOKEN" /notify POST)"
check "Token invalide" 401 "$(call "x.y.z" /notify POST)"
check "Token absent" 401 "$(call "" /notify POST)"
if [ "${1:-}" = "--expired" ]; then
  echo "(attente de l'expiration du token, ~5 min...)"; sleep 310
  check "Token expiré" 401 "$(call "$TOKEN" /notify POST)"
fi

echo "=== Démo 4 : Réservation vers /admin ==="
check "/admin avec token valide" 403 "$(call "$TOKEN" /admin GET)"

echo "=== Démo 6 : authentification des utilisateurs sur Réservation ==="
check "Réservation sans token" 401 "$(code -X POST https://localhost:8443/reservations -H 'content-type: application/json' -d '{"room":"A1","date":"2026-12-01"}')"
check "Token de service refusé sur Réservation" 401 "$(code -X POST https://localhost:8443/reservations -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"room":"A1","date":"2026-12-01"}')"
check "Liste des réservations avec token utilisateur" 200 "$(code https://localhost:8443/reservations -H "Authorization: Bearer $UTOKEN")"
check "Page réservation sans session -> redirigée" 303 "$(code https://localhost:8443/app/reservation)"
check "API réservations sans session" 401 "$(code https://localhost:8443/reservations)"
check "Documentation API désactivée" 404 "$(code https://localhost:8443/docs)"
check "Login avec le bon mot de passe" 200 "$(code -X POST https://localhost:8443/login -H 'content-type: application/json' -d "{\"username\":\"sara\",\"password\":\"$DEMO_USER_PASSWORD\"}")"
check "Login avec un mauvais mot de passe" 401 "$(code -X POST https://localhost:8443/login -H 'content-type: application/json' -d '{"username":"sara","password":"mauvais"}')"

echo; echo "Résultat : $PASS PASS, $FAIL FAIL"; [ "$FAIL" -eq 0 ]