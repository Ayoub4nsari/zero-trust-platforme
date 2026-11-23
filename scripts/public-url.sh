#!/usr/bin/env bash
# Démarre le tunnel Cloudflare et affiche l'URL publique
cd "$(dirname "$0")/.."
sudo docker compose --profile public up -d cloudflared
for i in $(seq 1 30); do
  url=$(sudo docker compose logs cloudflared 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | head -1)
  if [ -n "$url" ]; then echo "URL publique : $url"; exit 0; fi
  sleep 2
done
echo "URL introuvable. Voir : sudo docker compose logs cloudflared"; exit 1