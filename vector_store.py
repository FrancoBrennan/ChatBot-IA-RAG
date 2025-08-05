import numpy as np  # Para trabajar con vectores numéricos
import faiss  # Motor de búsqueda de similitud vectorial
import pymysql  # Conector para MySQL
from sqlalchemy import create_engine, text  # ORM para ejecutar queries SQL
from dotenv import load_dotenv  # Para cargar variables desde .env
import os  # Acceso a sistema de archivos y variables de entorno
from embedder import Embedder  # Clase que vectoriza texto con sentence-transformers
import json  # Para guardar y leer metadatos en JSON

load_dotenv()  # Carga las variables de entorno desde el archivo .env

# Configuración de conexión a base de datos MySQL
DB_USER = os.getenv("MYSQL_USER")
DB_PASS = os.getenv("MYSQL_PASSWORD")
DB_HOST = os.getenv("MYSQL_HOST")
DB_NAME = os.getenv("MYSQL_DB")

# Se crea el motor de conexión SQLAlchemy
engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}")

# Retorna el nombre del archivo PDF dado su ID
def get_filename_by_id(doc_id):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT nombre_archivo FROM documentos WHERE id = :id"), {"id": doc_id})
        return result.scalar()

# Devuelve todos los documentos con su ID y texto limpio
def get_all_documents():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, texto_limpio FROM documentos"))
        return [(row[0], row[1]) for row in result]

# Función para dividir un texto en bloques (chunks) con solapamiento
def chunk_text(text, chunk_size=500, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])  # Agrega un chunk de longitud 500
        start += chunk_size - overlap  # Se mueve con solapamiento de 100
    return chunks

# Función principal para indexar todos los documentos
def index_documents():
    from utils import extraer_texto_pdf  # Importación dentro de la función para evitar importaciones circulares

    documents = get_all_documents()  # Obtiene documentos desde DB
    embedder = Embedder()  # Instancia el modelo de embedding
    all_chunks = []  # Lista de vectores (embeddings)
    metadata = []  # Lista de metadatos asociados a cada chunk

    for doc_id, full_text in documents:
        # Obtiene el nombre del archivo físico del documento
        nombre_archivo = get_filename_by_id(doc_id)
        if not nombre_archivo:
            continue  # Si no lo encuentra, saltea

        pdf_path = os.path.join("uploads", nombre_archivo)

        try:
            # Extrae el texto por página del PDF
            paginas = extraer_texto_pdf(pdf_path)  # Devuelve lista de tuplas (nro_pagina, texto)
        except Exception as e:
            print(f"Error al procesar {pdf_path}: {e}")
            continue

        for pagina_num, texto in paginas:
            chunks = chunk_text(texto)  # Divide el texto en fragmentos
            embeddings = embedder.embed(chunks)  # Calcula embedding por chunk

            all_chunks.extend(embeddings)  # Acumula todos los vectores

            for chunk in chunks:
                # Se asocia metadatos a cada chunk: doc_id, texto, página
                metadata.append({
                    "doc_id": doc_id,
                    "chunk": chunk,
                    "pagina": pagina_num
                })

    if not all_chunks:
        print("No se encontraron chunks para indexar.")
        return

    # Crea índice FAISS con distancia L2
    dim = len(all_chunks[0])  # Dimensión del vector (ej: 384)
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(all_chunks).astype('float32'))  # Agrega todos los vectores al índice

    # Guarda el índice en disco
    faiss.write_index(index, "faiss.index")

    # Guarda los metadatos asociados a cada vector
    with open("faiss_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Index creado con {len(all_chunks)} vectores.")  # Log de éxito

# Permite ejecutar el script manualmente
if __name__ == "__main__":
    index_documents()
