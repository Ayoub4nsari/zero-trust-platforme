import logging
import os
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import COOKIE_NAME, require_scope, session_claims
from app.notify_client import notify

log = logging.getLogger("reservation")

TOKEN_URL = os.environ["OIDC_TOKEN_URL"]
USERS_URL = os.environ["KEYCLOAK_USERS_URL"]
REGISTRATION_SECRET_FILE = os.environ["REGISTRATION_CLIENT_SECRET_FILE"]
USER_CLIENT_ID = "reservation-web"
SCOPE = "reservations:use"
BASE_DIR = Path(__file__).parent
PAGES_DIR = BASE_DIR / "pages"

# Pas de /docs, /redoc ni /openapi.json : on n'expose pas la carte de l'API
app = FastAPI(title="Reservation Service", version="1.0.0",
              docs_url=None, redoc_url=None, openapi_url=None)

reservations = []


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    if request.url.path.startswith("/app"):
        response.headers["Cache-Control"] = "no-store"
    return response


class Reservation(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    room: str = Field(min_length=1, max_length=100)
    date: str = Field(min_length=1, max_length=100)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class Register(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,30}$")
    email: str = Field(max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=10, max_length=128)


# ---------- Pages ----------
def _html(name: str) -> FileResponse:
    return FileResponse(PAGES_DIR / name, media_type="text/html")


def _to(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


@app.get("/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
@app.get("/app/", include_in_schema=False)
def home(request: Request):
    return _to("/app/reservation" if session_claims(request, SCOPE) else "/app/login")


@app.get("/app/login", include_in_schema=False)
def page_login(request: Request):
    if session_claims(request, SCOPE):
        return _to("/app/reservation")
    return _html("login.html")


@app.get("/app/register", include_in_schema=False)
def page_register():
    return _html("register.html")


@app.get("/app/reservation", include_in_schema=False)
def page_reservation(request: Request):
    if not session_claims(request, SCOPE):
        return _to("/app/login")
    return _html("reservation.html")


@app.get("/app/mes-reservations", include_in_schema=False)
def page_mine(request: Request):
    if not session_claims(request, SCOPE):
        return _to("/app/login")
    return _html("mes-reservations.html")


# ---------- API ----------
@app.get("/health")
def health():
    return {"status": "healthy", "service": "reservation"}


@app.post("/register", status_code=201)
def register(data: Register):
    """Crée un compte dans Keycloak avec un client dédié (rôle manage-users uniquement)."""
    try:
        secret = Path(REGISTRATION_SECRET_FILE).read_text().strip()
        t = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": "registration-service",
                "client_secret": secret,
            },
            timeout=5,
        )
        t.raise_for_status()
        r = httpx.post(
            USERS_URL,
            headers={"Authorization": "Bearer " + t.json()["access_token"]},
            json={
                "username": data.username.lower(),
                "email": data.email,
                "firstName": data.first_name,
                "lastName": data.last_name,
                "enabled": True,
                "credentials": [{"type": "password", "value": data.password, "temporary": False}],
            },
            timeout=5,
        )
    except (httpx.HTTPError, OSError, KeyError) as exc:
        log.warning("registration backend error: %s", type(exc).__name__)
        raise HTTPException(503, "Service d'identité indisponible")
    if r.status_code == 201:
        return {"status": "created"}
    if r.status_code == 409:
        raise HTTPException(409, "Identifiant ou e-mail déjà utilisé")
    log.warning("registration refused by keycloak: %s", r.status_code)
    raise HTTPException(400, "Inscription refusée (vérifiez les champs et le mot de passe)")


@app.post("/login")
def login(creds: Login, response: Response):
    """Échange identifiant/mot de passe contre un token Keycloak, gardé dans un cookie HttpOnly."""
    try:
        r = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": USER_CLIENT_ID,
                "username": creds.username,
                "password": creds.password,
            },
            timeout=5,
        )
    except httpx.HTTPError:
        raise HTTPException(503, "Service d'identité indisponible")
    if r.status_code != 200:
        raise HTTPException(401, "Identifiants incorrects")
    body = r.json()
    response.set_cookie(
        COOKIE_NAME,
        body["access_token"],
        max_age=body["expires_in"],
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {"username": creds.username, "expires_in": body["expires_in"]}


@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return {"status": "logged_out"}


@app.get("/me")
def me(claims: dict = Depends(require_scope(SCOPE))):
    return {"username": claims.get("preferred_username") or claims.get("sub")}


@app.post("/reservations", status_code=201)
def create_reservation(
    reservation: Reservation,
    claims: dict = Depends(require_scope(SCOPE)),
):
    username = claims.get("preferred_username") or claims.get("sub")
    data = reservation.model_dump()
    data["name"] = data["name"] or username
    new_reservation = {
        "id": str(uuid4()),
        **data,
        "user": username,   # propriétaire : issu du token, jamais du corps de la requête
    }
    reservations.append(new_reservation)

    try:
        confirmation = notify({**new_reservation, "user": new_reservation["name"]})
        new_reservation["notification_status"] = "sent"
        message = "Réservation confirmée"
    except Exception as exc:
        log.warning("notification failed: %s", exc)
        confirmation = {
            "status": "failed",
            "message": "La réservation est enregistrée mais la notification n'a pas pu être envoyée.",
        }
        new_reservation["notification_status"] = "failed"
        message = "Réservation créée, notification non envoyée"

    return {
        "message": message,
        "reservation": new_reservation,
        "notification": confirmation,
    }


@app.get("/reservations")
def list_reservations(claims: dict = Depends(require_scope(SCOPE))):
    username = claims.get("preferred_username") or claims.get("sub")
    return {"reservations": [r for r in reservations if r["user"] == username]}


# Assets publics (CSS/JS) : aucune donnée, les pages protégées sont servies par les routes ci-dessus
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")