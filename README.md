# Zero-Trust Platform (Réservation + Notification)

Plateforme de réservation de salles construite selon les principes **Zero Trust** : aucune confiance implicite, chaque appel est authentifié, autorisé et chiffré, même entre services internes.

- **Réservation** (Java 21 / Spring Boot) : pages web, connexion, inscription, API de réservations.
- **Notification** (Java 21 / Spring Boot) : envoie les notifications, joignable uniquement par Réservation.
- **Keycloak** : serveur d'identité (OAuth2 / OpenID Connect).
- **Caddy** : reverse proxy HTTPS, seul point d'entrée.
- **Cloudflare Tunnel** (optionnel) : rend l'application accessible sur Internet.
- **CI GitHub Actions** : Gitleaks (secrets), Checkov (configuration), Trivy (vulnérabilités), publication des images sur GHCR.

---

## 1. Architecture

```
Internet (optionnel)
      │
 [ cloudflared ]  ── tunnel HTTPS sortant, aucun port ouvert chez toi
      │
┌─────┴──────── réseau "frontend" ──────────┐
│  [ Caddy :443 → exposé sur 8443 ]         │
│        │ HTTP                             │
│  [ Reservation :8001 ]                    │
└────────┼──────────────────────────────────┘
         │
┌────────┼──────── réseau "backend" (interne, sans accès Internet) ─┐
│        ├── HTTP ──► [ Keycloak :8080 ]  (tokens, JWKS, comptes)   │
│        └── mTLS + Bearer ──► [ Notification :8002 ]               │
└───────────────────────────────────────────────────────────────────┘
```

### Mesures de sécurité

| Mesure | Détail |
|---|---|
| mTLS | Réservation présente un certificat client à Notification, qui vérifie la CA interne et le nom d'hôte |
| JWT | Signature RS256 uniquement, vérification de `iss`, `exp` et `aud` |
| Scopes | `reservations:use` (utilisateurs web), `notify:send` (service Réservation) |
| Client autorisé | Claim `azp` vérifié (seul `reservation-web` peut appeler l'API utilisateur) |
| Session | Token stocké dans un cookie `__Host-session` HttpOnly, Secure, SameSite=Strict (jamais lu par le JavaScript) |
| En-têtes | CSP stricte, HSTS, `X-Content-Type-Options`, pas d'en-tête `Server` |
| Conteneurs | Utilisateur non-root, système de fichiers en lecture seule, `cap_drop: ALL`, `no-new-privileges` |
| Réseau | Keycloak et Notification n'ont aucun port publié, réseau `backend` interne |
| Secrets | Générés aléatoirement, montés comme Docker secrets, jamais dans Git |

---
Projet DevSecOps Mouad BENFILALI.
## 2. Structure du projet

```
.
├── docker-compose.yml          # Orchestration des services
├── Vagrantfile                 # VM Ubuntu (pour Windows)
├── proxy/Caddyfile             # Reverse proxy HTTPS
├── keycloak/realm-zerotrust.json   # Realm, clients, scopes, utilisateur "sara"
├── services/
│   ├── reservation/            # Java : pages, login, register, API réservations
│   └── notification/           # Java : endpoint /notify protégé
├── scripts/
│   ├── gen-secrets.sh          # Génère .env et secrets/
│   ├── gen-certs.sh            # Génère la CA interne et les certificats mTLS
│   ├── public-url.sh           # Démarre le tunnel Cloudflare (dans la VM)
│   ├── public-stop.sh          # Coupe l'accès public (dans la VM)
│   ├── provision-vm.sh         # Installation de Docker dans la VM
│   └── deploy-vm.sh            # Déploiement dans la VM
├── .github/workflows/ci.yml    # Pipeline CI/CD
├── .checkov.yml                # Configuration Checkov
├── .trivyignore                # Exceptions Trivy documentées
└── .gitleaks.toml              # Configuration Gitleaks
```

---

## 3. Prérequis

Choisis **une** des deux méthodes.

**Méthode A : Docker directement** (Linux, macOS, ou Windows avec WSL2)
- Git
- Docker Engine + Docker Compose v2 (`docker compose version`)
- OpenSSL (`openssl version`)
- Sous Windows : exécute tout dans un terminal **WSL (Ubuntu)** ou **Git Bash**, pas PowerShell

**Méthode B : VM Vagrant** (recommandée sous Windows, tout est automatisé)
- Git
- VirtualBox
- Vagrant
- 4 Go de RAM libres et 2 CPU pour la VM

---

## 4. Installation et lancement : Méthode A (Docker)

### 4.1 Récupérer le projet

```bash
git clone https://github.com/TON_USER/zero-trust-platforme.git
cd zero-trust-platforme
```

Sous Windows, évite que Git convertisse les fins de ligne des scripts :

```bash
git config core.autocrlf input
```

### 4.2 Générer les secrets et les certificats

Ces fichiers ne sont **pas** dans Git (ils sont dans `.gitignore`), il faut les générer à chaque nouvelle installation :

```bash
chmod +x scripts/*.sh
./scripts/gen-secrets.sh
./scripts/gen-certs.sh
```

Cela crée :
- `.env` : mots de passe et secrets clients Keycloak
- `secrets/` : secrets montés dans les conteneurs
- `certs/` : CA interne et certificats mTLS (valides 90 jours)

### 4.3 Construire et démarrer

```bash
docker compose up -d --build
```

Le premier démarrage prend 1 à 2 minutes (compilation Maven, démarrage de Keycloak et de Spring Boot). Vérifie l'état :

```bash
docker compose ps
```

Les services `keycloak`, `notification-service`, `reservation-service` et `caddy` doivent être `Up` (les deux services Java en `healthy`).

### 4.4 Ouvrir l'application

Ouvre **https://localhost:8443**.

Le navigateur affichera un avertissement de certificat : c'est normal, Caddy utilise sa propre autorité interne (`tls internal`). Clique sur « Avancé », puis « Continuer ».

### 4.5 Se connecter

- **Compte de démo** : utilisateur `sara`, mot de passe dans le fichier `.env` :
  ```bash
  grep DEMO_USER_PASSWORD .env
  ```
- **Nouveau compte** : page « Inscription » (`/app/register`). Le mot de passe doit faire au moins 10 caractères.

Après connexion, tu peux créer une réservation (salle + date), ce qui déclenche l'appel mTLS vers Notification, puis consulter « Mes réservations ».

---

## 5. Installation et lancement : Méthode B (Vagrant, Windows)

Depuis PowerShell, dans le dossier du projet :

```powershell
vagrant up
```

Le script installe Docker dans la VM (première fois), copie le projet, génère secrets et certificats, puis lance `docker compose up -d --build`.

Une fois terminé, ouvre **https://localhost:8443** sur Windows (le port 8443 est redirigé vers la VM).

Commandes utiles :

```powershell
vagrant ssh                 # entrer dans la VM
vagrant provision --provision-with deploy    # redéployer après une modification du code
vagrant halt                # éteindre la VM
vagrant destroy -f          # supprimer la VM
```

Dans la VM, le projet se trouve dans `~/zero-trust-platforme` et les commandes Docker nécessitent `sudo`.

---

## 6. Rendre l'application publique avec Cloudflare

Cloudflare Tunnel crée une connexion **sortante** depuis ta machine vers Cloudflare. Tu n'ouvres aucun port sur ta box et tu n'as besoin ni de domaine ni de compte (mode « quick tunnel »).

### 6.1 Démarrer le tunnel

**Méthode A (Docker directement)** :

```bash
docker compose --profile public up -d cloudflared
```

Puis récupère l'URL :

```bash
docker compose logs cloudflared 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | head -1
```

**Méthode B (Vagrant)** : dans la VM (`vagrant ssh`) :

```bash
cd ~/zero-trust-platforme
./scripts/public-url.sh
```

Le script affiche `URL publique : https://xxxx-xxxx.trycloudflare.com`.

### 6.2 Utiliser l'URL

Partage cette URL : n'importe qui peut ouvrir l'application depuis Internet, avec un certificat HTTPS valide. Le cookie de session `__Host-session` fonctionne car l'accès se fait en HTTPS.

### 6.3 Couper l'accès public

**Méthode A** :

```bash
docker compose --profile public stop cloudflared
docker compose --profile public rm -f cloudflared
```

**Méthode B** (dans la VM) :

```bash
./scripts/public-stop.sh
```

### 6.4 À savoir

- L'URL `trycloudflare.com` **change à chaque démarrage** du tunnel et n'est pas garantie pour un usage en production.
- Seule l'application web est exposée. Keycloak (et son console d'administration) et Notification ne sont jamais accessibles depuis Internet.
- L'inscription est ouverte à tout le monde : n'expose pas la plateforme longtemps sans surveillance. Coupe le tunnel après ta démonstration.
- Pour une URL fixe avec ton propre nom de domaine, il faut un compte Cloudflare gratuit et un « named tunnel » (`cloudflared tunnel create`). Ce n'est pas configuré dans ce projet.

---

## 7. API (pour les tests)

| Méthode | Chemin | Accès | Description |
|---|---|---|---|
| GET | `/health` | public | État du service |
| POST | `/login` | public | Connexion, pose le cookie de session |
| POST | `/register` | public | Création de compte |
| POST | `/logout` | public | Supprime le cookie |
| GET | `/me` | session | Nom de l'utilisateur connecté |
| POST | `/reservations` | session | Crée une réservation (`room`, `date`, `name` optionnel) |
| GET | `/reservations` | session | Liste **tes** réservations |
| GET | `/app/login`, `/app/register` | public | Pages HTML |
| GET | `/app/reservation`, `/app/mes-reservations` | session | Pages HTML protégées |

Tests rapides (`-k` ignore le certificat auto-signé local) :

```bash
curl -k https://localhost:8443/health
# {"status":"healthy","service":"reservation"}

curl -k -i https://localhost:8443/reservations
# HTTP 401 : sans token, accès refusé

curl -k -i https://localhost:8443/app/reservation
# HTTP 303 : redirection vers /app/login
```

Les réservations sont gardées **en mémoire** : elles disparaissent quand le service redémarre.

---

## 8. Commandes courantes

```bash
docker compose ps                          # état des conteneurs
docker compose logs -f reservation         # logs du service Réservation
docker compose logs -f notification        # logs du service Notification
docker compose logs -f keycloak            # logs Keycloak
docker compose build --no-cache reservation   # reconstruire après modification du code
docker compose up -d                       # redémarrer
docker compose down                        # tout arrêter
docker compose down -v                     # tout arrêter + supprimer les volumes
```

---

## 9. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| **502 Bad Gateway** | Le conteneur `reservation` n'est pas démarré | `docker compose ps -a` puis `docker logs reservation-service --tail=60` |
| `variable is not set. Defaulting to a blank string` | `.env` absent | Lancer `./scripts/gen-secrets.sh` |
| `Permission denied` sur `/run/secrets/...` | Droits des fichiers | `chmod 644 certs/* secrets/*` puis `docker compose up -d --force-recreate` |
| Erreur de clé privée PEM / SSL bundle | Clé EC au format SEC1 | Convertir en PKCS#8 (voir ci-dessous) |
| `BeanDefinitionOverrideException` | Deux beans de même nom | Vérifier que le bean `RestClient` s'appelle `notificationRestClient` |
| `\r: command not found` dans un script | Fins de ligne Windows | `sed -i 's/\r$//' scripts/*.sh` |
| L'ancien Python tourne encore | Image non reconstruite | `docker compose build --no-cache` puis `docker compose up -d` |
| Certificats expirés (après 90 jours) | Durée de validité | `./scripts/gen-certs.sh` puis `docker compose up -d --force-recreate` |

Conversion des clés en PKCS#8 :

```bash
cd certs
for k in reservation notification; do
  grep -q "BEGIN EC PRIVATE KEY" $k.key && \
  openssl pkcs8 -topk8 -nocrypt -in $k.key -out $k.pk8 && mv $k.pk8 $k.key
done
chmod 644 *.key *.crt
cd ..
docker compose up -d --force-recreate
```

**Problèmes Vagrant sous Windows**

- `VERR_ALREADY_EXISTS` : un dossier ou une VM `zerotrust` reste dans VirtualBox. Désenregistre la VM (`VBoxManage unregistervm <id>`), supprime `C:\Users\<toi>\VirtualBox VMs\zerotrust` et le dossier `.vagrant`, puis relance `vagrant up`.
- Démarrage très lent ou bloqué : Hyper-V et VirtualBox peuvent entrer en conflit (`bcdedit /set hypervisorlaunchtype off`, puis redémarrage).

---

## 10. Pipeline CI/CD

À chaque `push`, GitHub Actions exécute :

1. **Gitleaks** : détecte les secrets dans le code et l'historique Git.
2. **Checkov** : analyse la configuration (`docker-compose.yml`, Dockerfiles, workflows) avec `.checkov.yml`.
3. **Build + Trivy** : construit chaque image et bloque le pipeline s'il reste des vulnérabilités HIGH ou CRITICAL avec correctif disponible. Les exceptions acceptées sont listées, avec une date d'expiration, dans `.trivyignore`.
4. **Publication GHCR** (branche `main` uniquement) : pousse `ghcr.io/<owner>/zt-reservation` et `zt-notification`.

Règles importantes :
- Ne jamais commiter `.env`, `secrets/`, `certs/` ni de fichiers `*.key`.
- Un faux secret dans un fichier (même pour un test) fera échouer Gitleaks.

---

## 11. Sécurité : ce qu'il faut savoir avant de publier

- Keycloak tourne en mode `start-dev` : suffisant pour une démo, **pas pour la production** (base de données H2, pas de durcissement).
- Les secrets générés ne sont valables que pour ton installation : régénère-les pour chaque déploiement.
- Les certificats mTLS expirent après 90 jours.
- Le tunnel `trycloudflare.com` est prévu pour des démonstrations temporaires.

---

## 12. Licence

Projet DevSecOps Mouad BENFILALI.
