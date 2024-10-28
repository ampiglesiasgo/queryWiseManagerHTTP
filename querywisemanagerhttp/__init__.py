import logging
import os
import openai
import pyodbc
import azure.functions as func
from dotenv import load_dotenv

# Cargar las variables de entorno
load_dotenv()

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuración de la base de datos SQL
connection_string = os.getenv("SQL_CONNECTION_STRING")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Procesando una solicitud HTTP para la función de QA.')

    # Obtener la pregunta del cuerpo de la solicitud
    try:
        req_body = req.get_json()
        question = req_body.get("question")
    except ValueError:
        return func.HttpResponse("Por favor, envía una pregunta en formato JSON.", status_code=400)

    if not question:
        return func.HttpResponse("La pregunta no puede estar vacía.", status_code=400)

    # Consultar la base de datos y construir el contexto
    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT context FROM FAQ")
            context_data = " ".join([row[0] for row in cursor.fetchall()])
    except Exception as e:
        logging.error("Error al conectar con la base de datos: %s", e)
        return func.HttpResponse("Error de conexión con la base de datos.", status_code=500)

    # Realizar la consulta al modelo de OpenAI
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"{context_data}\nPregunta: {question}\nRespuesta:",
            max_tokens=100
        )
        answer = response.choices[0].text.strip()
        return func.HttpResponse(answer, status_code=200)
    except Exception as e:
        logging.error("Error al conectar con OpenAI: %s", e)
        return func.HttpResponse("Error al obtener respuesta del modelo.", status_code=500)
