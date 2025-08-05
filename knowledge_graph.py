import json  # Para trabajar con archivos JSON

# Función que carga el archivo de grafo en memoria
def cargar_grafo_conocimiento(ruta_json='knowledge_graph.json'):
    with open(ruta_json, 'r', encoding='utf-8') as f:
        return json.load(f)

# Carga el grafo al iniciar el backend
grafo_conocimiento = cargar_grafo_conocimiento()
