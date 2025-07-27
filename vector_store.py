import numpy as np
import faiss
import pymysql
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
from embedder import Embedder

load_dotenv()

# Config DB
DB_USER = os.getenv("MYSQL_USER")
DB_PASS = os.getenv("MYSQL_PASSWORD")
DB_HOST = os.getenv("MYSQL_HOST")
DB_NAME = os.getenv("MYSQL_DB")

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}")

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
    documents = get_all_documents()
    embedder = Embedder()
    all_chunks = []
    metadata = []

    for doc_id, text in documents:
        chunks = chunk_text(text)
        embeddings = embedder.embed(chunks)
        all_chunks.extend(embeddings)
        metadata.extend([(doc_id, chunk) for chunk in chunks])

    dim = len(all_chunks[0])
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(all_chunks).astype('float32'))

    faiss.write_index(index, "faiss.index")
    print(f"Index creado con {len(all_chunks)} vectores.")


if __name__ == "__main__":
    index_documents()
