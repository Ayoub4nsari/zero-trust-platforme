import os

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

ISSUER = os.environ["OIDC_ISSUER"]
JWKS_URL = os.environ["OIDC_JWKS_URL"]
AUDIENCE = os.environ["OIDC_AUDIENCE"]
ALLOWED_CLIENT_IDS = {c.strip() for c in os.environ["ALLOWED_CLIENT_IDS"].split(",") if c.strip()}

COOKIE_NAME = "__Host-session"
_jwks = PyJWKClient(JWKS_URL, cache_keys=True)


def _extract_token(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def _check(request: Request, required: str) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(401, "Authentification requise")
    try:
        key = _jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expiré")
    except jwt.PyJWTError:
        raise HTTPException(401, "Token invalide")
    if claims.get("azp") not in ALLOWED_CLIENT_IDS:
        raise HTTPException(403, "Client non autorisé")
    if required not in claims.get("scope", "").split():
        raise HTTPException(403, "Scope insuffisant")
    return claims


def require_scope(required: str):
    def dependency(request: Request) -> dict:
        return _check(request, required)
    return dependency


def session_claims(request: Request, required: str):
    """Pour les pages : retourne les claims ou None (pas d'exception)."""
    try:
        return _check(request, required)
    except HTTPException:
        return None