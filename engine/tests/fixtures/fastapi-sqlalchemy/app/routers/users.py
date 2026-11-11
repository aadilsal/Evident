from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import get_db
from ..models import User

router = APIRouter(prefix="/users")


class UserIn(BaseModel):
    email: str


@router.get("/")
def list_users(db=Depends(get_db)):
    return db.query(User).all()


@router.post("/")
def create_user(payload: UserIn, db=Depends(get_db)):
    user = User(email=payload.email)
    db.add(user)
    db.commit()
    return user


@router.get("/{user_id}")
def get_user(user_id: int, db=Depends(get_db)):
    return db.get(User, user_id)
