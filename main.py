from fastapi import FastAPI, File, UploadFile, Depends, status, HTTPException, Path
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import shutil
import os
import re
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from database import SessionLocal, engine
from models import Base, Documento, Conversacion, Mensaje, Usuario
from utils import extraer_texto_pdf
# ⬇️ si lo dejaste en utils, mantené esta línea; si lo moviste a unresolved.py, cambiá el import
from utils import registrar_consulta_no_resuelta

# LangChain
from vectorstore_langchain import build_faiss, INDEX_DIR
from rag_chain import build_rag, INSUFF_MSG

from auth import crear_token, verificar_contraseña, verificar_token, hashear_contraseña

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# ===== LangChain Answer (build si ya hay índice) =====
answer = None
os.makedirs(INDEX_DIR, exist_ok=True)
if os.path.exists(os.path.join(INDEX_DIR, "index.faiss")):
    answer = build_rag()
else:
    def _empty_answer(_q: str):
        return INSUFF_MSG, []
    answer = _empty_answer

# ========= DB dependency =========
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ========= Auth / Schemas =========
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

class LoginInput(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

# ===== util títulos =====
def _primer_frase(texto: str) -> str:
    if not texto:
        return ""
    linea = texto.strip().splitlines()[0]
    for sep in [". ", "? ", "! ", " — ", " - "]:
        if sep in linea:
            linea = linea.split(sep, 1)[0]
            break
    linea = re.sub(r"\s+", " ", linea).strip()
    linea = linea.replace("“", "\"").replace("”", "\"").replace("’", "'")
    if linea and linea[0].islower():
        linea = linea[0].upper() + linea[1:]
    return linea

def sugerir_titulo_con_keywords(texto: str, max_len: int = 60) -> str:
    # Versión simple: solo primera frase (sin grafo)
    titulo = _primer_frase(texto) or "Nueva conversación"
    if len(titulo) > max_len:
        titulo = titulo[:max_len].rstrip() + "…"
    return titulo

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    payload = verificar_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    user = db.query(Usuario).get(int(payload["sub"]))
    if not user or not user.activo:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    return user

def require_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins")
    return user

# ========= Login & Perfil =========
@app.post("/login", response_model=TokenOut)
def login(data: LoginInput, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.username == data.username).first()
    if not user or not verificar_contraseña(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    if not user.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")
    token = crear_token(sub=str(user.id))
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me", response_model=UserOut)
def me(current_user: Usuario = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "is_admin": bool(current_user.is_admin)}

# ========= Admin: gestión de usuarios =========

@app.post("/init-admin")
def init_admin(db: Session = Depends(get_db)):
    if db.query(Usuario).filter_by(username="admin").first():
        return {"mensaje": "Ya existe un admin"}
    u = Usuario(
        username="admin",
        nombre="Administrador",
        password_hash=hashear_contraseña("admin123"),
        is_admin=True,
        activo=True
    )
    db.add(u)
    db.commit()
    return {"mensaje": "Admin creado", "id": u.id}

class UserCreateIn(BaseModel):
    username: str
    password: str
    nombre: str | None = None
    is_admin: bool = False
    activo: bool = True

class UserCreatedOut(BaseModel):
    id: int
    username: str
    nombre: str | None = None
    is_admin: bool
    activo: bool

@app.post("/admin/users", response_model=UserCreatedOut)
def crear_usuario(body: UserCreateIn, db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    nuevo = Usuario(
        username=body.username.strip(),
        nombre=(body.nombre or "").strip() or None,
        password_hash=hashear_contraseña(body.password),
        is_admin=bool(body.is_admin),
        activo=bool(body.activo),
    )
    db.add(nuevo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El usuario ya existe")
    db.refresh(nuevo)
    return UserCreatedOut(
        id=nuevo.id, username=nuevo.username, nombre=nuevo.nombre,
        is_admin=bool(nuevo.is_admin), activo=bool(nuevo.activo)
    )

@app.get("/admin/users", response_model=list[UserCreatedOut])
def listar_usuarios(db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    users = db.query(Usuario).order_by(Usuario.id).all()
    return [
        UserCreatedOut(
            id=u.id, username=u.username, nombre=u.nombre,
            is_admin=bool(u.is_admin), activo=bool(u.activo)
        ) for u in users
    ]

@app.patch("/admin/users/{user_id}/estado", response_model=UserCreatedOut)
def cambiar_estado_usuario(user_id: int, activo: bool, db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    u = db.query(Usuario).get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    u.activo = bool(activo)
    db.commit()
    db.refresh(u)
    return UserCreatedOut(
        id=u.id, username=u.username, nombre=u.nombre,
        is_admin=bool(u.is_admin), activo=bool(u.activo)
    )

@app.delete("/admin/users/{user_id}", status_code=204)
def borrar_usuario(user_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    u = db.query(Usuario).get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    db.delete(u)
    db.commit()
    return

# ========= Admin: Datasets (solo admin) =========
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_pdf(archivo: UploadFile = File(...), db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    if not archivo.filename.lower().endswith(".pdf") or archivo.content_type != "application/pdf":
        return {"error": "Solo se permiten archivos PDF"}

    existing = db.query(Documento).filter_by(nombre_archivo=archivo.filename).first()
    if existing:
        return {"error": "Este archivo ya fue subido previamente"}

    file_path = os.path.join(UPLOAD_DIR, archivo.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    texto_por_paginas = extraer_texto_pdf(file_path)
    texto_concatenado = "\n".join([texto for _, texto in texto_por_paginas]) if texto_por_paginas else ""

    if not texto_concatenado.strip():
        raise HTTPException(status_code=400, detail="No se pudo extraer texto del PDF")

    doc = Documento(
        nombre_archivo=archivo.filename,
        fecha_subida=datetime.utcnow(),
        texto_limpio=texto_concatenado
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Reindex con LangChain
    build_faiss(INDEX_DIR)
    global answer
    answer = build_rag()
    return {"message": "PDF subido exitosamente", "id": doc.id}

@app.get("/listar-datasets")
def listar_datasets(db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    documentos = db.query(Documento).all()
    return [{"id": d.id, "nombre": d.nombre_archivo} for d in documentos]

@app.delete("/eliminar-dataset/{id}")
def eliminar_dataset(id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_admin)):
    documento = db.query(Documento).filter(Documento.id == id).first()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    ruta_archivo = os.path.join(UPLOAD_DIR, documento.nombre_archivo)
    if os.path.exists(ruta_archivo):
        os.remove(ruta_archivo)

    db.delete(documento)
    db.commit()
    return {"mensaje": "Documento eliminado correctamente"}

@app.delete("/documento/{id}", tags=["Documentos"])
def eliminar_documento(id: int = Path(..., description="ID del documento a eliminar"), _: Usuario = Depends(require_admin)):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM documentos WHERE id = :id"), {"id": id})
        existe = result.scalar()
        if not existe:
            raise HTTPException(status_code=404, detail=f"Documento con id {id} no encontrado.")
        conn.execute(text("DELETE FROM documentos WHERE id = :id"), {"id": id})
        conn.commit()
    return {"mensaje": f"Documento con id {id} eliminado correctamente."}

@app.post("/actualizar-documentos")
def actualizar_documentos(_: Usuario = Depends(require_admin)):
    build_faiss(INDEX_DIR)
    global answer
    answer = build_rag()
    return {"mensaje": "Documentos reindexados correctamente"}

# ========= Búsqueda (pública) =========
@app.get("/buscar")
def buscar_respuesta(pregunta: str):
    texto, fuentes = answer(pregunta)

    # si no hay info suficiente → NO mandar fuentes
    if not texto or texto.strip() == "" or texto.strip() == INSUFF_MSG:
        return {"respuesta": INSUFF_MSG, "fuentes": []}

    # deduplicar fuentes y formatear
    uniq = []
    seen = set()
    for f in fuentes:
        if isinstance(f, dict):
            key = (f.get("archivo"), f.get("paginas"))
        else:
            key = f
        if key not in seen:
            seen.add(key)
            uniq.append(f)

    fuentes_fmt = [
        f"{f['archivo']}" + (f" (p. {f['paginas']})" if isinstance(f, dict) and 'paginas' in f else "")
        for f in uniq
    ]

    return {"respuesta": texto, "fuentes": fuentes_fmt}


# ========= Conversaciones (asociadas a usuario) =========
class ConversacionOut(BaseModel):
    id: int
    titulo: str
    class Config:
        from_attributes = True

class CreateConvIn(BaseModel):
    titulo: str | None = None

class MensajeInput(BaseModel):
    rol: str
    contenido: str

class MensajeOut(BaseModel):
    rol: str
    contenido: str
    fecha: str | None = None
    class Config:
        from_attributes = True

@app.post("/conversaciones/", response_model=ConversacionOut, status_code=201)
def crear_conversacion(
    body: CreateConvIn | None = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    titulo = (body.titulo if body else None) or "Nueva conversación"
    conv = Conversacion(titulo=titulo, user_id=current_user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@app.get("/conversaciones", response_model=list[ConversacionOut])
def listar_conversaciones(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    convs = db.query(Conversacion).filter(Conversacion.user_id == current_user.id) \
                                  .order_by(Conversacion.fecha_creacion.desc()).all()
    return convs

@app.get("/conversaciones/{conv_id}")
def obtener_conversacion(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    conv = db.query(Conversacion).filter(
        Conversacion.id == conv_id,
        Conversacion.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {
        "id": conv.id,
        "titulo": conv.titulo,
        "mensajes": [
            {"rol": m.rol, "contenido": m.contenido, "fecha": m.fecha.isoformat() if m.fecha else None}
            for m in conv.mensajes
        ],
    }

@app.post("/conversaciones/{conv_id}/mensaje", response_model=dict, status_code=201)
def agregar_mensaje(
    conv_id: int,
    mensaje: MensajeInput,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    conv = db.query(Conversacion).filter(
        Conversacion.id == conv_id,
        Conversacion.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    hay_mensajes = db.query(Mensaje.id).filter(Mensaje.conversacion_id == conv.id).first() is not None
    if not hay_mensajes and mensaje.rol.lower() == "user":
        conv.titulo = sugerir_titulo_con_keywords(mensaje.contenido)

    nuevo = Mensaje(conversacion_id=conv.id, rol=mensaje.rol, contenido=mensaje.contenido)
    db.add(nuevo)
    db.commit()
    return {"mensaje": "Mensaje agregado"}

@app.delete("/conversaciones/{conv_id}", status_code=204)
def borrar_conversacion(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    conv = db.query(Conversacion).filter(
        Conversacion.id == conv_id,
        Conversacion.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    db.delete(conv)
    db.commit()
    return
