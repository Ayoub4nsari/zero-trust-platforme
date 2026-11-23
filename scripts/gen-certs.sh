#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p certs && chmod 700 certs && cd certs
DAYS=90

# --- CA interne ---
openssl ecparam -name prime256v1 -genkey -noout -out ca.key
openssl req -x509 -new -key ca.key -sha256 -days "$DAYS" \
  -subj "/CN=zerotrust-internal-ca" -out ca.crt
chmod 600 ca.key

issue() {  # nom, extendedKeyUsage, SAN
  local name=$1 eku=$2 san=$3
  openssl ecparam -name prime256v1 -genkey -noout -out "$name.key"
  openssl req -new -key "$name.key" -subj "/CN=$name" -out "$name.csr"
  cat > "$name.ext" <<EOT
basicConstraints=CA:FALSE
keyUsage=digitalSignature
extendedKeyUsage=$eku
subjectAltName=$san
EOT
  openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -days "$DAYS" -sha256 -extfile "$name.ext" -out "$name.crt"
  rm -f "$name.csr" "$name.ext"
}

issue notification serverAuth "DNS:notification"
issue reservation  clientAuth "DNS:reservation"

# Lisibles par l'utilisateur non-root des conteneurs ; le dossier reste en 700
chmod 644 ca.crt notification.crt notification.key reservation.crt reservation.key
rm -f ca.srl
echo "Certificats générés dans certs/ (valides $DAYS jours)"
