from fastapi import FastAPI, File, UploadFile, Depends
from sqlalchemy.orm import Session
import shutil
import os
from database import SessionLocal, engine
from models import Base, Documento, Conversacion, Mensaje
from utils import extraer_texto_pdf
from datetime import datetime
from search_engine import search_similar_chunks_with_metadata, registrar_consulta_no_resuelta
from generator import generar_respuesta
from vector_store import index_documents
from fastapi import Path
from knowledge_graph import grafo_conocimiento
from search_engine import obtener_conceptos_relacionados
from fastapi.middleware.cors import CORSMiddleware
from models import Usuario
from fastapi import HTTPException
from pydantic import BaseModel

import bcrypt

app = FastAPI()  # Crea una instancia de la aplicación

# Habilita CORS para que el frontend pueda comunicarse
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Origen permitido (frontend)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)  # Crea las tablas en la base de datos si no existen

# Función para obtener una sesión de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define la carpeta donde se guardan los PDFs
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Crea la carpeta si no existe

# Ruta para subir PDFs
@app.post("/upload")
async def upload_pdf(archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    # Validación del archivo
    if not archivo.filename.endswith(".pdf") or archivo.content_type != "application/pdf":
        return {"error": "Solo se permiten archivos PDF"}

    # Evita duplicados
    existing = db.query(Documento).filter_by(nombre_archivo=archivo.filename).first()
    if existing:
        return {"error": "Este archivo ya fue subido previamente"}

    # Guarda el archivo en disco
    file_path = os.path.join(UPLOAD_DIR, archivo.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    # Extrae y concatena el texto del PDF
    texto_por_paginas = extraer_texto_pdf(file_path)  # List[(pagina, texto)]
    texto_concatenado = "\n".join([texto for _, texto in texto_por_paginas])

    # Crea objeto Documento
    doc = Documento(
        nombre_archivo=archivo.filename,
        fecha_subida=datetime.utcnow(),
        texto_limpio=texto_concatenado
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    index_documents()  # Indexa todos los documentos nuevamente

    return {"message": "PDF subido exitosamente", "id": doc.id}

# Ruta para listar todos los datasets cargados
@app.get("/listar-datasets")
def listar_datasets(db: Session = Depends(get_db)):
    documentos = db.query(Documento).all()
    return [{"id": d.id, "nombre": d.nombre_archivo} for d in documentos]

# Ruta para eliminar un dataset
@app.delete("/eliminar-dataset/{id}")
def eliminar_dataset(id: int, db: Session = Depends(get_db)):
    documento = db.query(Documento).filter(Documento.id == id).first()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Borra el archivo físico
    ruta_archivo = os.path.join(UPLOAD_DIR, documento.nombre_archivo)
    if os.path.exists(ruta_archivo):
        os.remove(ruta_archivo)

    db.delete(documento)
    db.commit()

    return {"mensaje": "Documento eliminado correctamente"}

# Ruta principal de búsqueda
@app.get("/buscar")
def buscar_respuesta(pregunta: str):
    conceptos = obtener_conceptos_relacionados(pregunta, grafo_conocimiento)
    subgrafo = {k: grafo_conocimiento[k] for k in conceptos if k in grafo_conocimiento}

    contexto, fuentes = search_similar_chunks_with_metadata(pregunta)

    if contexto is None:
        registrar_consulta_no_resuelta(pregunta)
        return {
            "respuesta": "La información solicitada está fuera del dominio. Se generará un ticket con mesa de ayuda, se pondrán en contacto contigo.",
            "fuentes": []
    }

    respuesta = generar_respuesta(pregunta, contexto, grafo=subgrafo)
    return {"respuesta": respuesta, "fuentes": fuentes}

# Eliminar documento por ID (usando SQL directa)
@app.delete("/documento/{id}", tags=["Documentos"])
def eliminar_documento(id: int = Path(..., description="ID del documento a eliminar")):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM documentos WHERE id = :id"), {"id": id})
        existe = result.scalar()
        if not existe:
            raise HTTPException(status_code=404, detail=f"Documento con id {id} no encontrado.")

        conn.execute(text("DELETE FROM documentos WHERE id = :id"), {"id": id})
        conn.commit()

    return {"mensaje": f"Documento con id {id} eliminado correctamente."}

# Reindexar documentos manualmente
@app.post("/actualizar-documentos")
def actualizar_documentos():
    index_documents()
    return {"mensaje": "Documentos reindexados correctamente"}

# Esquema de entrada para login
class LoginInput(BaseModel):
    username: str
    password: str

# Ruta para autenticación
@app.post("/login")
def login(data: LoginInput, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter_by(username=data.username).first()
    if not user or not bcrypt.checkpw(data.password.encode("utf-8"), user.password_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin
    }

# Crear nueva conversación
@app.post("/conversaciones/", response_model=dict)
def crear_conversacion(db: Session = Depends(get_db)):
    conv = Conversacion(titulo="Nueva conversación")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": conv.id}

# Esquema para mensajes en conversación
class MensajeInput(BaseModel):
    rol: str
    contenido: str

# Agregar mensaje a conversación
@app.post("/conversaciones/{id}/mensaje")
def agregar_mensaje(id: int, mensaje: MensajeInput, db: Session = Depends(get_db)):
    conversacion = db.query(Conversacion).filter_by(id=id).first()
    if not conversacion:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    
    nuevo = Mensaje(
        conversacion_id=id,
        rol=mensaje.rol,
        contenido=mensaje.contenido,
    )
    db.add(nuevo)
    db.commit()
    return {"mensaje": "Mensaje agregado"}

# Listar todas las conversaciones
@app.get("/conversaciones")
def listar_conversaciones(db: Session = Depends(get_db)):
    return db.query(Conversacion).all()

# Obtener una conversación específica
@app.get("/conversaciones/{conv_id}")
def obtener_conversacion(conv_id: int, db: Session = Depends(get_db)):
    conv = db.query(Conversacion).filter(Conversacion.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="No encontrada")
    return {
        "id": conv.id,
        "titulo": conv.titulo,
        "mensajes": [{"rol": m.rol, "contenido": m.contenido} for m in conv.mensajes]
    }