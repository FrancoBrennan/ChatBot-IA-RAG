import os
from datetime import datetime, timedelta
import jwt  # PyJWT
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET", "change-me")
ALGORITHM = os.getenv("JWT_ALG", "HS256")
ACCESS_MIN = int(os.getenv("JWT_EXPIRE_MIN", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verificar_contraseña(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hashear_contraseña(password):
    return pwd_context.hash(password)

def crear_token(sub: str, expires_minutes: int = ACCESS_MIN):
    to_encode = {"sub": sub, "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
