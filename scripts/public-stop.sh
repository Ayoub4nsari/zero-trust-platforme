#!/usr/bin/env bash
# Coupe l'accès public
cd "$(dirname "$0")/.."
sudo docker compose --profile public stop cloudflared
sudo docker compose --profile public rm -f cloudflared
echo "Tunnel arrêté : le service n'est plus public."