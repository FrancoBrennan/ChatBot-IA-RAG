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
        model="mistralai/mixtral-8x7b-instruct",  # También podés probar gpt-3.5-turbo, openchat, claude-3-haiku...
        messages=[
            {"role": "system", "content": "Sos un asistente de soporte técnico. Respondé con claridad y precisión usando el contexto proporcionado."},
            {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"}
        ]
    )
    return response.choices[0].message.content
