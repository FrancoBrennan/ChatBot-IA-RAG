import faiss
import numpy as np
from embedder import Embedder
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import json


load_dotenv()

DB_USER = os.getenv("MYSQL_USER")
DB_PASS = os.getenv("MYSQL_PASSWORD")
DB_HOST = os.getenv("MYSQL_HOST")
DB_NAME = os.getenv("MYSQL_DB")

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}")

# Se abre el índice guardado con los embeddings de los chunks del documento.
index = faiss.read_index("faiss.index")

# Esto carga el modelo sentence-transformers para poder vectorizar nuevas preguntas.
embedder = Embedder()

# El parámetro top_k define cuántos vectores (chunks) similares se van a recuperar del índice FAISS cuando haces una búsqueda.
def search_similar_chunks_with_metadata(question, top_k=5, threshold=0.9):
    question_vector = embedder.embed([question])
    query_vector = np.array(question_vector).astype('float32')

    distances, indices = index.search(query_vector, top_k)

    with open("faiss_metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)

    selected_chunks = []
    fuentes_dict = {}

    with engine.connect() as conn:
        for idx, dist in zip(indices[0], distances[0]):
            if idx >= len(metadata) or dist > threshold:
                continue

            chunk_info = metadata[idx]
            selected_chunks.append(chunk_info["chunk"])

            doc_id = chunk_info["doc_id"]
            pagina = chunk_info.get("pagina", None)

            result = conn.execute(
                text("SELECT nombre_archivo FROM documentos WHERE id = :id"),
                {"id": doc_id}
            )
            nombre = result.scalar()
            if nombre and pagina is not None:
                if nombre not in fuentes_dict:
                    fuentes_dict[nombre] = set()
                fuentes_dict[nombre].add(pagina)

    if not selected_chunks:
        return None, []

    # Agrupar páginas por documento
    fuentes = []
    for nombre_archivo, paginas in fuentes_dict.items():
        paginas = sorted(paginas)
        if len(paginas) == 1:
            fuentes.append(f"{nombre_archivo} (p. {paginas[0]})")
        else:
            fuentes.append(f"{nombre_archivo} (p. {paginas[0]}-{paginas[-1]})")

    respuesta = " ".join(selected_chunks)
    return respuesta, fuentes



# Esta función devuelve sólo los vectores similares, es la parte "Retriever" del RAG, es decir, sin la implementación del LLM.
def retrieve_chunks(pregunta, top_k=2):
    question_vector = embedder.embed([pregunta])
    query_vector = np.array(question_vector).astype('float32')

    distances, indices = index.search(query_vector, top_k)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT texto_limpio FROM documentos"))
        all_texts = [row[0] for row in result]

    chunks = []
    for text_row in all_texts:
        for i in range(0, len(text_row), 500 - 100):
            chunk = text_row[i:i + 500]
            chunks.append(chunk)

    # Devolver los chunks más similares
    resultados = [chunks[i] for i in indices[0]]
    return resultados


def registrar_consulta_no_resuelta(pregunta: str):
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO consultas_no_resueltas (pregunta) VALUES (:pregunta)"),
            {"pregunta": pregunta}
        )
        conn.commit()
