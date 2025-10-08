import os, json, re
from typing import List, Tuple
from collections import Counter

from sqlalchemy import text
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from database import SessionLocal
from text_pipeline import split_text
from utils import extraer_texto_pdf

INDEX_DIR = "indices"   # índice único
UPLOAD_DIR = "uploads"  # donde guardás los PDFs

# -------------------- Helpers --------------------
_WORD = re.compile(r"[a-záéíóúüñ0-9]{3,}", re.IGNORECASE)

def _norm(s: str) -> str:
    import unicodedata
    s = s.lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def __get_embeddings():
    # import diferido para evitar ciclos
    from embeddings_setup import dense
    return dense

# -------------------- Lectura de documentos --------------------
def get_all_documents() -> List[Tuple[int, str]]:
    with SessionLocal() as db:
        rows = db.execute(text("SELECT id, nombre_archivo FROM documentos")).fetchall()
        return [(r[0], r[1]) for r in rows]

def to_documents() -> List[Document]:
    """Lee PDFs desde /uploads para conservar número de página en metadata."""
    docs: List[Document] = []
    for doc_id, nombre in get_all_documents():
        pdf_path = os.path.join(UPLOAD_DIR, nombre)
        if not os.path.exists(pdf_path):
            # Si el archivo falta, salteamos (así preservamos pages correctas)
            continue
        for page_num, page_text in extraer_texto_pdf(pdf_path):
            meta = {"doc_id": doc_id, "source": nombre, "page": page_num}
            docs.extend(split_text(page_text, meta=meta))
    return docs

# -------------------- Construcción de índice + léxico --------------------
def build_lexicon(docs: List[Document], out_path=os.path.join(INDEX_DIR, "lexicon.json"), max_terms: int = 8000):
    cnt = Counter()
    for d in docs:
        for t in _WORD.findall(_norm(d.page_content)):
            cnt[t] += 1
    vocab = [w for w, _ in cnt.most_common(max_terms)]
    os.makedirs(INDEX_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False)

def build_faiss(dir_path: str = INDEX_DIR) -> FAISS:
    os.makedirs(dir_path, exist_ok=True)
    docs = to_documents()
    if not docs:
        raise RuntimeError("No hay documentos para indexar.")
    vs = FAISS.from_documents(docs, embedding=__get_embeddings())
    vs.save_local(dir_path)
    # Construye un léxico del corpus para expansión de consulta agnóstica
    build_lexicon(docs)
    return vs

def load_faiss(dir_path: str = INDEX_DIR) -> FAISS:
    os.makedirs(dir_path, exist_ok=True)
    return FAISS.load_local(dir_path, embeddings=__get_embeddings(), allow_dangerous_deserialization=True)

def build_bm25() -> BM25Retriever:
    docs = to_documents()
    if not docs:
        raise RuntimeError("No hay documentos para BM25.")
    return BM25Retriever.from_documents(docs)
