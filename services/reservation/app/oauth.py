import os
import threading
import time

import httpx

TOKEN_URL = os.environ["OIDC_TOKEN_URL"]
CLIENT_ID = os.environ["OIDC_CLIENT_ID"]
SECRET_FILE = os.environ["OIDC_CLIENT_SECRET_FILE"]

_lock = threading.Lock()
_token: str | None = None
_expires_at = 0.0


def _read_secret() -> str:
    with open(SECRET_FILE) as f:
        return f.read().strip()


def get_token() -> str:
    global _token, _expires_at
    with _lock:
        if _token and time.time() < _expires_at - 30:
            return _token
        r = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": _read_secret(),
            },
            timeout=5,
        )
        r.raise_for_status()
        body = r.json()
        _token = body["access_token"]
        _expires_at = time.time() + body["expires_in"]
        return _token