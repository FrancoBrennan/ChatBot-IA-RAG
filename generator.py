import os  # Para leer variables de entorno
from openai import OpenAI  # Cliente para usar la API compatible con OpenAI
from dotenv import load_dotenv  # Para cargar variables desde .env

load_dotenv()  # Carga las variables del archivo .env

# Configura el cliente de OpenAI apuntando a OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# Función que arma el mensaje y consulta al modelo
def generar_respuesta(pregunta, contexto, grafo=None):
    # Prompt de sistema: le indica al modelo cómo comportarse
    system_content = (
        "Sos un asistente de soporte técnico especializado en IT. "
        "Tu tarea es responder preguntas de manera clara, útil y profesional. "
        "Utilizá únicamente la información del contexto que se te brinda, sin inventar datos. "
        "No hagas referencia al nombre de los documentos fuente, ni menciones frases como 'según el documento', 'según la guía', 'en la FAQ', etc. "
        "Tampoco repitas títulos o encabezados. "
        "Respondé en tono directo y práctico, como lo haría un técnico capacitado ayudando a un usuario."
    )

    # Si hay grafo de conocimiento relacionado, lo agrega como contexto extra
    if grafo:
        system_content += "\n\nInformación estructurada adicional útil:\n"
        for concepto, datos in grafo.items():
            system_content += f"- {concepto}: {datos['descripcion']}\n"

    # Llama al modelo
    response = client.chat.completions.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"}
        ]
    )
    return response.choices[0].message.content  # Devuelve solo el texto generado
