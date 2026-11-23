import os

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jwt import PyJWKClient

# Fail closed : le service ne démarre pas si la config est absente
ISSUER = os.environ["OIDC_ISSUER"]
JWKS_URL = os.environ["OIDC_JWKS_URL"]
AUDIENCE = os.environ["OIDC_AUDIENCE"]
ALLOWED_CLIENT_IDS = {c for c in os.environ["ALLOWED_CLIENT_IDS"].split(",") if c}

_jwks = PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)
_bearer = HTTPBearer(auto_error=False)


def _401(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def require_scope(required: str):
    def dependency(creds=Depends(_bearer)):
        if creds is None:
            raise _401("Missing bearer token")
        token = creds.credentials
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
            raise _401("Token expired")
        except jwt.PyJWTError:
            raise _401("Invalid token")

        if claims.get("azp") not in ALLOWED_CLIENT_IDS:
            raise HTTPException(403, "Client not allowed")
        if required not in claims.get("scope", "").split():
            raise HTTPException(403, "Insufficient scope")
        return claims

    return dependency
