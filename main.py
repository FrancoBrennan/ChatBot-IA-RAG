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
from utils import registrar_consulta_no_resuelta

# LangChain / RAG
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

# ---------- Mensajes ----------
NO_INDEX_MSG = "No hay documentos indexados."

def _no_index_answer(_q: str, history=None):
    return NO_INDEX_MSG, []

# valor por defecto seguro si aún no existe el índice
answer = _no_index_answer

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# Inicializar RAG si hay índice en disco
os.makedirs(INDEX_DIR, exist_ok=True)
if os.path.exists(os.path.join(INDEX_DIR, "index.faiss")):
    try:
        answer = build_rag()  # devuelve (question, history=None) -> (texto, fuentes)
    except Exception:
        answer = _no_index_answer

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
    titulo = _primer_frase(texto) or "Nueva conversación"
    if len(titulo) > max_len:
        titulo = titulo[:max_len].rstrip() + "…"
    return titulo

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    payload = verificar_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    user = db.get(Usuario, int(payload["sub"]))  # SQLAlchemy 2.0
    if not user or not user.activo:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    return user

def require_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins")
    return user

# ---------- Utils comunes para limpieza y fuentes ----------

import re

DOC_RE = re.compile(
    r"""^\s*(?P<file>.+?\.(?:pdf|docx?|pptx?|xlsx?|csv|md|txt))
        (?:\s*\(\s*p{1,2}\.\s*(?P<pages>[^)]+)\))?
        \s*$""", re.IGNORECASE | re.VERBOSE
)

def _compress_ranges(nums):
    if not nums: return []
    nums = sorted(set(nums))
    out, a, b = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == b + 1: b = n
        else: out.append((a,b)); a=b=n
    out.append((a,b))
    return [f"{x}" if x==y else f"{x}–{y}" for x,y in out]

def _format_pages(pages_set):
    if not pages_set: return ""
    parts = _compress_ranges(list(pages_set))
    return f" (p. {parts[0]})" if (len(parts)==1 and "–" not in parts[0]) else f" (pp. {', '.join(parts)})"

def _parse_pages_to_set(pages_value):
    page_set = set()
    if pages_value is None or pages_value == "": return page_set
    if isinstance(pages_value, int):
        page_set.add(pages_value); return page_set
    if isinstance(pages_value, (list, tuple, set)):
        for p in pages_value:
            try: page_set.add(int(str(p)))
            except: pass
        return page_set
    if isinstance(pages_value, str):
        tmp = [x.strip() for x in pages_value.replace(";", ",").split(",") if x.strip()]
        for token in tmp:
            token = token.replace("pp.", "").replace("p.", "").strip().replace("–","-")
            if "-" in token:
                try:
                    a,b = token.split("-",1); a,b = int(a), int(b)
                    for n in range(min(a,b), max(a,b)+1): page_set.add(n)
                except: pass
            else:
                try: page_set.add(int(token))
                except: pass
    return page_set

def normalize_sources(fuentes: list[dict | str]):
    """
    Devuelve (order, docs_pages) donde:
      - order: lista de archivos en orden de 1a aparición
      - docs_pages: dict archivo -> set(páginas)
    Acepta dict({'archivo','paginas'}) o str('file.pdf (pp. 2–4, 7)').
    """
    docs_pages, order = {}, []
    for f in (fuentes or []):
        if isinstance(f, dict):
            archivo = f.get("archivo"); pags = f.get("paginas")
            pages = _parse_pages_to_set(pags)
        else:
            s = str(f or "").strip()
            m = DOC_RE.match(s)
            if m:
                archivo = m.group("file")
                pages = _parse_pages_to_set(m.group("pages"))
            else:
                archivo, pages = (s if s else None), set()
        if not archivo: continue
        if archivo not in docs_pages:
            docs_pages[archivo] = set(); order.append(archivo)
        docs_pages[archivo].update(pages)
    return order, docs_pages

def format_sources_list(order, docs_pages):
    """Genera lista de 'archivo (pp. ...)' sin repeticiones."""
    return [f"{arc}{_format_pages(docs_pages.get(arc,set()))}" for arc in order]

def clean_text_remove_quote_lines(s: str) -> str:
    # quita líneas que son solo comillas; recorta comillas colgantes
    lines = [ln for ln in s.splitlines() if ln.strip() not in {'"', "''", '""'}]
    s = "\n".join(lines).strip()
    if s.startswith('"') and s.endswith('"') and "\n" not in s:
        s = s[1:-1].strip()
    return s

def strip_residual_titles_from_text(texto: str, order, docs_pages) -> str:
    """
    Elimina del cuerpo líneas sueltas que coinciden con el 'título' del documento
    (basename sin extensión, guiones/underscores como espacios), típicamente
    encabezados que el LLM copió.
    """
    if not texto: return texto
    # candidatos de títulos
    candidates = set()
    for arc in order:
        base = os.path.splitext(os.path.basename(arc))[0]
        norm = re.sub(r"[_\-]+", " ", base, flags=re.UNICODE).strip()
        candidates.add(norm.lower())
        # también versiones capitalizadas
        candidates.add(norm.title().lower())

    # limpia párrafos que sean exactamente uno de los candidatos (case-insensitive)
    new_lines = []
    for ln in texto.splitlines():
        ln_norm = re.sub(r"\s+", " ", ln).strip().lower()
        if ln_norm in candidates:
            # saltear SOLO si es línea aislada o en borde de párrafo
            # (si aparece embebida en otra frase, no tocar)
            continue
        new_lines.append(ln)
    return "\n".join(new_lines).strip()


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
    u = db.get(Usuario, user_id)
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
    u = db.get(Usuario, user_id)
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
    # Permitir content-type variable, validar por extensión
    if not archivo.filename.lower().endswith(".pdf"):
        return {"error": "Solo se permiten archivos PDF"}

    existing = db.query(Documento).filter_by(nombre_archivo=archivo.filename).first()
    if existing:
        return {"error": "Este archivo ya fue subido previamente"}

    file_path = os.path.join(UPLOAD_DIR, os.path.basename(archivo.filename))
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
    try:
        answer = build_rag()
    except Exception:
        answer = _no_index_answer

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
        try:
            os.remove(ruta_archivo)
        except PermissionError:
            pass  # Windows a veces bloquea el archivo si está abierto

    db.delete(documento)
    db.commit()

    # Reindexar para limpiar índices y refrescar función de respuesta
    global answer
    try:
        build_faiss(INDEX_DIR)
        answer = build_rag()
    except Exception:
        answer = _no_index_answer

    return {"mensaje": "Documento eliminado y reindexado correctamente"}

@app.delete("/documento/{id}", tags=["Documentos"])
def eliminar_documento(id: int, _: Usuario = Depends(require_admin)):
    with engine.begin() as conn:
        existe = conn.execute(text("SELECT COUNT(*) FROM documentos WHERE id = :id"), {"id": id}).scalar()
        if not existe:
            raise HTTPException(status_code=404, detail=f"Documento con id {id} no encontrado.")
        conn.execute(text("DELETE FROM documentos WHERE id = :id"), {"id": id})
    return {"mensaje": f"Documento con id {id} eliminado correctamente."}

@app.post("/actualizar-documentos")
def actualizar_documentos(_: Usuario = Depends(require_admin)):
    global answer
    try:
        build_faiss(INDEX_DIR)
        answer = build_rag()
        return {"mensaje": "Documentos reindexados correctamente"}
    except RuntimeError:
        answer = _no_index_answer
        return {"mensaje": NO_INDEX_MSG}
    except Exception:
        answer = _no_index_answer
        raise HTTPException(status_code=500, detail="Error al reindexar")

@app.get("/buscar")
def buscar_respuesta(pregunta: str):
    fn = answer if callable(answer) else _no_index_answer
    texto, fuentes = fn(pregunta)

    if not texto or texto.strip() == "":
        return {"respuesta": INSUFF_MSG, "fuentes": []}

    txt = clean_text_remove_quote_lines(texto)
    if txt in (INSUFF_MSG, NO_INDEX_MSG):
        return {"respuesta": txt, "fuentes": []}

    order, docs_pages = normalize_sources(fuentes)
    fuentes_fmt = format_sources_list(order, docs_pages)

    # elimina títulos-residuo dentro del cuerpo
    txt = strip_residual_titles_from_text(txt, order, docs_pages)

    respuesta_txt = txt
    if fuentes_fmt:
        respuesta_txt = f"{txt}\n\nBasado en: {'; '.join(fuentes_fmt)}"

    return {"respuesta": respuesta_txt, "fuentes": fuentes_fmt}


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

class PreguntaIn(BaseModel):
    pregunta: str

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

    # Título automático en el 1er mensaje del usuario
    hay_mensajes = db.query(Mensaje.id).filter(Mensaje.conversacion_id == conv.id).first() is not None
    if not hay_mensajes and mensaje.rol.lower() == "user":
        conv.titulo = sugerir_titulo_con_keywords(mensaje.contenido)

    # 1) guardo el mensaje entrante
    db.add(Mensaje(conversacion_id=conv.id, rol=mensaje.rol, contenido=mensaje.contenido))
    db.commit()

    if mensaje.rol.lower() != "user":
        return {"mensaje": "Mensaje agregado"}

    # 2) armo historial (últimos N turnos)
    N = int(os.getenv("HISTORY_TURNS", "6"))
    mensajes = (db.query(Mensaje)
                  .filter(Mensaje.conversacion_id == conv.id)
                  .order_by(Mensaje.fecha.asc())
                  .all())
    history = [{"role": m.rol, "content": m.contenido} for m in mensajes][-N:]

    # 3) respondo con RAG + historial
    fn = answer if callable(answer) else _no_index_answer
    texto, fuentes = fn(mensaje.contenido, history=history)

    # 4) formateo “Basado en: …” con la misma lógica que /buscar
    order, docs_pages = normalize_sources(fuentes)
    fuentes_fmt = format_sources_list(order, docs_pages)

    # limpiar texto y quitar posibles títulos-residuo
    texto = clean_text_remove_quote_lines(texto)
    texto = strip_residual_titles_from_text(texto, order, docs_pages)

    respuesta_txt = texto
    if fuentes_fmt:
        respuesta_txt = f"{texto}\n\nBasado en: {'; '.join(fuentes_fmt)}"

    db.add(Mensaje(conversacion_id=conv.id, rol="assistant", contenido=respuesta_txt))
    db.commit()

    return {"respuesta": respuesta_txt, "fuentes": fuentes_fmt}

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
