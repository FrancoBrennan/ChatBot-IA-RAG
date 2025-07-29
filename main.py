from fastapi import FastAPI, File, UploadFile, Depends
from sqlalchemy.orm import Session
import shutil
import os
from database import SessionLocal, engine
from models import Base, Documento
from utils import extraer_texto_pdf
from datetime import datetime
from fastapi import Query
from search_engine import search_similar_chunks_with_metadata, retrieve_chunks, registrar_consulta_no_resuelta
from generator import generar_respuesta
from vector_store import index_documents
from fastapi import Path
from knowledge_graph import grafo_conocimiento
from search_engine import obtener_conceptos_relacionados
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Permitir solicitudes desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # origen del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".pdf") or file.content_type != "application/pdf":
        return {"error": "Solo se permiten archivos PDF"}

    existing = db.query(Documento).filter_by(nombre_archivo=file.filename).first()
    if existing:
        return {"error": "Este archivo ya fue subido previamente"}

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    texto_por_paginas = extraer_texto_pdf(file_path)  # List[(pagina, texto)]
    texto_concatenado = "\n".join([texto for _, texto in texto_por_paginas])


    doc = Documento(
        nombre_archivo=file.filename,
        fecha_subida=datetime.utcnow(),
        texto_limpio=texto_concatenado
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 🟩 Reindexar documentos automáticamente después de subir
    index_documents()

    return {"message": "PDF subido exitosamente", "id": doc.id}

@app.get("/documents")
def listar_documentos(db: Session = Depends(get_db)):
    return db.query(Documento).all()


@app.get("/buscar")
def buscar_respuesta(pregunta: str):
    conceptos = obtener_conceptos_relacionados(pregunta, grafo_conocimiento)
    subgrafo = {k: grafo_conocimiento[k] for k in conceptos if k in grafo_conocimiento}

    contexto, fuentes = search_similar_chunks_with_metadata(pregunta)

    if contexto is None:
        registrar_consulta_no_resuelta(pregunta)
        return {
            "respuesta": "La información solicitada está fuera del dominio. Por favor, contactá con un humano.",
            "fuentes": []
    }

    respuesta = generar_respuesta(pregunta, contexto, grafo=subgrafo)
    return {"respuesta": respuesta, "fuentes": fuentes}


@app.get("/vector-similar")
def buscar_chunks(pregunta: str):
    chunks = retrieve_chunks(pregunta, top_k=2)
    return {"chunks_similares": chunks}

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


@app.post("/actualizar-documentos")
def actualizar_documentos():
    index_documents()
    return {"mensaje": "Documentos reindexados correctamente"}

