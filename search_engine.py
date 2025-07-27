import faiss
import numpy as np
from embedder import Embedder
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

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
def search_similar_chunk(question, top_k=2):
    # Convierte la pregunta a un vector numérico del mismo tipo que los vectores del índice FAISS.
    question_vector = embedder.embed([question])
    query_vector = np.array(question_vector).astype('float32')

    # Se hace la búsqueda vectorial y se obtienen los índices del chunk más similar.
    distances, indices = index.search(query_vector, top_k)

    # Carga todo el texto limpio de los documentos. En esta primera versión, los chunks no están guardados individualmente, sino que hay que reconstruirlos.
    with engine.connect() as conn:
        result = conn.execute(text("SELECT texto_limpio FROM documentos"))
        all_texts = [row[0] for row in result]

    # Se parte cada documento en chunks de 500 caracteres con un solapamiento de 100, igual que en vector_store.py.
    chunks = []
    for text_row in all_texts:
        for i in range(0, len(text_row), 500 - 100):
            chunk = text_row[i:i + 500]
            chunks.append(chunk)

    # Unir los top_k chunks más relevantes
    selected_chunks = [chunks[i] for i in indices[0]]
    respuesta = " ".join(selected_chunks)

    return respuesta

    # Devuelve el chunk cuyo vector fue el más cercano al de la pregunta.
    # best_chunk = chunks[indices[0][0]]
    # return best_chunk

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
