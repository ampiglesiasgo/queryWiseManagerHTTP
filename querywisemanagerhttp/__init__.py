import logging
import os
import openai
import pyodbc
import azure.functions as func
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, exceptions


# Cargar las variables de entorno
load_dotenv()

# Configuración de OpenAI
openai.api_key = os.getenv("AZURE_OPENAI_API_KEY")
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_type = "azure"
openai.api_version = "2024-08-01-preview"

# Nombre del despliegue (modelo)
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Configuración de Cosmos DB
cosmos_url = os.getenv("COSMOS_DB_URL")
cosmos_key = os.getenv("COSMOS_DB_KEY")
cosmos_database_name = os.getenv("COSMOS_DB_DATABASE_NAME")
cosmos_container_name = os.getenv("COSMOS_DB_CONTAINER_NAME")

# Inicializar el cliente de Cosmos DB
cosmos_client = CosmosClient(cosmos_url, credential=cosmos_key)
database = cosmos_client.get_database_client(cosmos_database_name)
container = database.get_container_client(cosmos_container_name)

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
        query = "SELECT c.id FROM c"
        context_data = " ".join([item["id"] for item in container.query_items(
            query=query,
            enable_cross_partition_query=True
        )])
    except exceptions.CosmosHttpResponseError as e:
        logging.error("Error al conectar con Cosmos DB: %s", e)
        return func.HttpResponse("Error de conexión con la base de datos.", status_code=500)


    # Realizar la consulta al modelo de OpenAI
    try:
        response = openai.ChatCompletion.create(
            engine=deployment_name,
            messages=[
                {"role": "system", "content": context_data},
                {"role": "user", "content": question}
            ],
            max_tokens=100
        )
        answer = response.choices[0].message['content'].strip()
        return func.HttpResponse(answer, status_code=200)
    except Exception as e:
        logging.error("Error al conectar con OpenAI: %s", e)
        return func.HttpResponse("Error al obtener respuesta del modelo.", status_code=500)