import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_scope

log = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Notification Service",
    version="1.0.0"
)


class Notification(BaseModel):
    reservation_id: str = Field(min_length=1, max_length=100)
    user: str = Field(min_length=1, max_length=100)
    room: str = Field(min_length=1, max_length=100)
    date: str = Field(min_length=1, max_length=100)


@app.get("/")
def root():
    return {"state": "ok", "service": "notification"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "notification"}


@app.post("/notify")
def send_notification(
    notification: Notification,
    claims: dict = Depends(require_scope("notify:send")),
):
    log.info(
        "NOTIFICATION RECUE reservation_id=%s user=%s client=%s",
        notification.reservation_id, notification.user, claims.get("azp"),
    )
    return {
        "status": "sent",
        "notification_id": str(uuid4()),
        "reservation_id": notification.reservation_id,
        "recipient": notification.user,
        "message": (
            f"Bonjour {notification.user}, votre réservation de la salle "
            f"{notification.room} le {notification.date} est confirmée."
        ),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/admin")
def admin():
    raise HTTPException(
        status_code=403,
        detail="Forbidden"
    )