import os
import ssl

import httpx

from app.oauth import get_token

NOTIFICATION_URL = os.environ["NOTIFICATION_URL"]

# Fail closed : l'import échoue si les certificats sont absents
_ctx = ssl.create_default_context(cafile=os.environ["TLS_CA"])
_ctx.load_cert_chain(os.environ["TLS_CERT"], os.environ["TLS_KEY"])
_client = httpx.Client(verify=_ctx, timeout=5)


def notify(reservation: dict) -> dict:
    """Appelle Notification (mTLS + JWT) et renvoie sa confirmation."""
    r = _client.post(
        f"{NOTIFICATION_URL}/notify",
        json={
            "reservation_id": reservation["id"],
            "user": reservation["user"],
            "room": reservation["room"],
            "date": reservation["date"],
        },
        headers={"Authorization": f"Bearer {get_token()}"},
    )
    r.raise_for_status()
    return r.json()