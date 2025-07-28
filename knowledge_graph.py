import json

def cargar_grafo_conocimiento(ruta_json='knowledge_graph.json'):
    with open(ruta_json, 'r', encoding='utf-8') as f:
        return json.load(f)

grafo_conocimiento = cargar_grafo_conocimiento()
