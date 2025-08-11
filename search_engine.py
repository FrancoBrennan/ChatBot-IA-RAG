import faiss  # Biblioteca para búsquedas vectoriales rápidas
import numpy as np  # Para trabajar con arrays de vectores
from embedder import Embedder  # Carga el modelo de embeddings (sentence-transformers)
from sqlalchemy import create_engine, text  # Para conectarse a base de datos y ejecutar queries SQL
from dotenv import load_dotenv  # Para cargar variables de entorno desde .env
import os  # Para acceder a variables de entorno
import json  # Para trabajar con metadata en formato JSON
from knowledge_graph import grafo_conocimiento  # Importa el grafo de conceptos relacionados

load_dotenv()  # Carga las variables del archivo .env al entorno del sistema

# Variables de conexión a base de datos MySQL
DB_USER = os.getenv("MYSQL_USER")
DB_PASS = os.getenv("MYSQL_PASSWORD")
DB_HOST = os.getenv("MYSQL_HOST")
DB_NAME = os.getenv("MYSQL_DB")

# Crea el motor de conexión a MySQL
engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}")

# Carga el índice FAISS guardado en disco con los embeddings de los chunks
index = faiss.read_index("faiss.index")

# Instancia del modelo de embeddings
embedder = Embedder()

# Función principal de búsqueda: devuelve texto + fuentes
def search_similar_chunks_with_metadata(question, top_k=5, threshold=0.9):
    # Expande la pregunta agregando conceptos del grafo relacionados
    pregunta_expandida = construir_consulta_expandida(question, grafo_conocimiento)

    # Convierte la pregunta a vector
    question_vector = embedder.embed([pregunta_expandida])
    query_vector = np.array(question_vector).astype('float32')

    # Busca en el índice FAISS los vectores más similares
    distances, indices = index.search(query_vector, top_k)

    # Carga la metadata (posición del chunk, doc_id, etc.)
    with open("faiss_metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)

    selected_chunks = []  # Chunks de texto más relevantes
    fuentes_dict = {}  # Diccionario de fuentes por documento

    with engine.connect() as conn:
        for idx, dist in zip(indices[0], distances[0]):
            if idx >= len(metadata) or dist > threshold:
                continue  # Ignora si el índice es inválido o no es lo bastante similar

            chunk_info = metadata[idx]
            selected_chunks.append(chunk_info["chunk"])

            doc_id = chunk_info["doc_id"]
            pagina = chunk_info.get("pagina", None)

            # Consulta para obtener nombre del archivo
            result = conn.execute(
                text("SELECT nombre_archivo FROM documentos WHERE id = :id"),
                {"id": doc_id}
            )
            nombre = result.scalar()
            if nombre and pagina is not None:
                if nombre not in fuentes_dict:
                    fuentes_dict[nombre] = set()
                fuentes_dict[nombre].add(pagina)  # Agrega página consultada

    if not selected_chunks:
        return None, []  # Si no encontró resultados

    # Agrupa páginas por documento
    fuentes = []
    for nombre_archivo, paginas in fuentes_dict.items():
        paginas = sorted(paginas)
        if len(paginas) == 1:
            fuentes.append(f"{nombre_archivo} (p. {paginas[0]})")
        else:
            fuentes.append(f"{nombre_archivo} (p. {paginas[0]}-{paginas[-1]})")

    respuesta = " ".join(selected_chunks)  # Une los fragmentos seleccionados
    return respuesta, fuentes  # Devuelve el contexto + fuentes

# Registra preguntas no respondidas para posterior análisis
def registrar_consulta_no_resuelta(pregunta: str):
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO consultas_no_resueltas (pregunta) VALUES (:pregunta)"),
            {"pregunta": pregunta}
        )
        conn.commit()

# Extrae conceptos relacionados de la pregunta usando el grafo
def obtener_conceptos_relacionados(pregunta, grafo):
    conceptos_encontrados = []

    for concepto in grafo:
        if concepto.lower() in pregunta.lower():
            conceptos_encontrados.append(concepto)

    relacionados = set()
    for concepto in conceptos_encontrados:
        relacionados.add(concepto)
        relacionados.update(grafo[concepto]["relaciones"])

    return list(relacionados)

# Expande la pregunta con conceptos relacionados para mejorar el embedding
def construir_consulta_expandida(pregunta, grafo):
    conceptos = obtener_conceptos_relacionados(pregunta, grafo)
    texto_expandido = " ".join(conceptos) + " " + pregunta
    return texto_expandido
