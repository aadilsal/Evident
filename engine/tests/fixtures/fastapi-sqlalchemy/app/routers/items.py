from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, insert

from ..billing import charge
from ..deps import get_current_user, get_db
from ..models import Item

router = APIRouter(prefix="/items", tags=["items"])


@router.post("/")
async def create_item(request: Request, db=Depends(get_db)):
    data = await request.json()
    db.execute(insert(Item).values(**data))
    charge(100)


@router.delete("/{item_id}")
def delete_item(item_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    db.execute(delete(Item).where(Item.id == item_id))
