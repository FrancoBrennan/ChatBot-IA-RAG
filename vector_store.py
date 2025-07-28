import numpy as np
import faiss
import pymysql
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
from embedder import Embedder
import json


load_dotenv()

# Config DB
DB_USER = os.getenv("MYSQL_USER")
DB_PASS = os.getenv("MYSQL_PASSWORD")
DB_HOST = os.getenv("MYSQL_HOST")
DB_NAME = os.getenv("MYSQL_DB")

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}")

def get_filename_by_id(doc_id):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT nombre_archivo FROM documentos WHERE id = :id"), {"id": doc_id})
        return result.scalar()


def get_all_documents():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, texto_limpio FROM documentos"))
        return [(row[0], row[1]) for row in result]

def chunk_text(text, chunk_size=500, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def index_documents():
    from utils import extraer_texto_pdf  # 👈 Lo importamos acá por si genera conflictos circulares
    documents = get_all_documents()
    embedder = Embedder()
    all_chunks = []
    metadata = []

    for doc_id, full_text in documents:
        # Ruta al archivo
        nombre_archivo = get_filename_by_id(doc_id)
        if not nombre_archivo:
            continue

        pdf_path = os.path.join("uploads", nombre_archivo)

        try:
            paginas = extraer_texto_pdf(pdf_path)  # List[Tuple[int, str]]
        except Exception as e:
            print(f"Error al procesar {pdf_path}: {e}")
            continue

        for pagina_num, texto in paginas:
            chunks = chunk_text(texto)
            embeddings = embedder.embed(chunks)
            all_chunks.extend(embeddings)
            for chunk in chunks:
                metadata.append({
                    "doc_id": doc_id,
                    "chunk": chunk,
                    "pagina": pagina_num
                })

    if not all_chunks:
        print("No se encontraron chunks para indexar.")
        return

    dim = len(all_chunks[0])
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(all_chunks).astype('float32'))

    faiss.write_index(index, "faiss.index")

    # Guardamos los metadatos (doc_id, chunk, pagina)
    with open("faiss_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Index creado con {len(all_chunks)} vectores.")



if __name__ == "__main__":
    index_documents()
