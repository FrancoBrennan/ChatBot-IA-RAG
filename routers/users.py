from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, auth, database

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/login")
def login(username: str, password: str, db: Session = Depends(database.SessionLocal)):
    user = db.query(models.Usuario).filter(models.Usuario.username == username).first()
    if not user or not auth.verificar_contraseña(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = auth.crear_token({"sub": user.username, "is_admin": user.is_admin})
    return {"access_token": token, "token_type": "bearer"}
