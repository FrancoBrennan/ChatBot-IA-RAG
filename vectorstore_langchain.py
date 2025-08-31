import os
from typing import List, Tuple
from sqlalchemy import text
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from database import SessionLocal
from embeddings_setup import dense
from text_pipeline import split_text

INDEX_DIR = "indices"  # índice único

def get_all_documents() -> List[Tuple[int, str, str]]:
    with SessionLocal() as db:
        rows = db.execute(text("SELECT id, nombre_archivo, texto_limpio FROM documentos")).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

def to_documents() -> List[Document]:
    docs = []
    for doc_id, nombre, texto in get_all_documents():
        if not texto:
            continue
        docs.extend(split_text(texto, meta={"doc_id": doc_id, "source": nombre}))
    return docs

def build_faiss(dir_path: str = INDEX_DIR) -> FAISS:
    os.makedirs(dir_path, exist_ok=True)
    docs = to_documents()
    if not docs:
        raise RuntimeError("No hay documentos para indexar.")
    vs = FAISS.from_documents(docs, dense)
    vs.save_local(dir_path)
    return vs

def load_faiss(dir_path: str = INDEX_DIR) -> FAISS:
    os.makedirs(dir_path, exist_ok=True)
    return FAISS.load_local(dir_path, dense, allow_dangerous_deserialization=True)

def build_bm25() -> BM25Retriever:
    docs = to_documents()
    if not docs:
        raise RuntimeError("No hay documentos para BM25.")
    return BM25Retriever.from_documents(docs)
