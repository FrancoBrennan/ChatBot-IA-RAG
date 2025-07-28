import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def generar_respuesta(pregunta, contexto):
    response = client.chat.completions.create(
        model="mistralai/mixtral-8x7b-instruct",
        messages=[
            {
                "role": "system",
                "content": (
                    "Sos un asistente de soporte técnico especializado en IT. "
                    "Tu tarea es responder preguntas de manera clara, útil y profesional. "
                    "Utilizá únicamente la información del contexto que se te brinda, sin inventar datos. "
                    "No hagas referencia al nombre de los documentos fuente, ni menciones frases como 'según el documento', 'según la guía', 'en la FAQ', etc. "
                    "Tampoco repitas títulos o encabezados. "
                    "Respondé en tono directo y práctico, como lo haría un técnico capacitado ayudando a un usuario."
                )
            },
            {
                "role": "user",
                "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"
            }
        ]
    )
    return response.choices[0].message.content

