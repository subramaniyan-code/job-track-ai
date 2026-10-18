from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..security import encrypt_dict

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("", response_model=list[schemas.ApiConnectionOut])
def list_connectors(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.ApiConnection).filter(models.ApiConnection.user_id == user.id).all()


@router.post("", response_model=schemas.ApiConnectionOut)
def add_connector(
    payload: schemas.ApiConnectionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    conn = models.ApiConnection(
        user_id=user.id,
        provider=payload.provider,
        label=payload.label,
        credentials_encrypted=encrypt_dict(payload.credentials),
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{connector_id}", status_code=204)
def delete_connector(connector_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    conn = db.query(models.ApiConnection).filter(
        models.ApiConnection.id == connector_id, models.ApiConnection.user_id == user.id
    ).first()
    if conn:
        db.delete(conn)
        db.commit()
