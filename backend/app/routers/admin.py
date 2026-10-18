from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_super_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _admin: models.User = Depends(require_super_admin)):
    return db.query(models.User).order_by(models.User.created_at.asc()).all()


@router.post("/users/{user_id}/deactivate", response_model=schemas.UserOut)
def deactivate_user(user_id: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_super_admin)):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    target.is_active = False
    db.commit()
    db.refresh(target)
    return target


@router.post("/users/{user_id}/reactivate", response_model=schemas.UserOut)
def reactivate_user(user_id: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_super_admin)):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    target.is_active = True
    db.commit()
    db.refresh(target)
    return target
