from fastapi import FastAPI, File, UploadFile, Depends
from sqlalchemy.orm import Session
import shutil
import os
from database import SessionLocal, engine
from models import Base, Documento
from utils import extraer_texto_pdf
from datetime import datetime
from fastapi import Query
from search_engine import search_similar_chunk, retrieve_chunks
from generator import generar_respuesta


app = FastAPI()

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
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    texto = extraer_texto_pdf(file_path)

    doc = Documento(
        nombre_archivo=file.filename,
        fecha_subida=datetime.utcnow(),
        texto_limpio=texto
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {"message": "PDF subido exitosamente", "id": doc.id}

@app.get("/documents")
def listar_documentos(db: Session = Depends(get_db)):
    return db.query(Documento).all()

@app.get("/buscar")
def buscar_respuesta(pregunta: str):
    contexto = search_similar_chunk(pregunta, top_k=2)
    respuesta = generar_respuesta(pregunta, contexto)
    return {"respuesta": respuesta}

@app.get("/vector-similar")
def buscar_chunks(pregunta: str):
    chunks = retrieve_chunks(pregunta, top_k=2)
    return {"chunks_similares": chunks}
