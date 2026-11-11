import os

from .db import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = ""):
    if token != os.environ["API_TOKEN"]:
        raise PermissionError("bad token")
    return {"id": 1}
