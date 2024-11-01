import logging
import os
import openai
import pyodbc
import azure.functions as func
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, exceptions
import datetime


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

    # Obtener la pregunta y la fecha del cuerpo de la solicitud
    try:
        req_body = req.get_json()
        question = req_body.get("question")
        filter_date_str = req_body.get("fecha")
    except ValueError:
        return func.HttpResponse("Por favor, envía una pregunta en formato JSON.", status_code=400)

    if not question:
        return func.HttpResponse("La pregunta no puede estar vacía.", status_code=400)

    # Preparar la consulta y construir el contexto basado en la fecha proporcionada o registros recientes
    try:
        if filter_date_str:
            # Convertir la fecha del JSON a un objeto datetime
            try:
                filter_date = datetime.fromisoformat(filter_date_str)
            except ValueError:
                return func.HttpResponse("Formato de fecha no válido. Utiliza 'YYYY-MM-DD'.", status_code=400)

            # Filtrar registros mayores o iguales a la fecha proporcionada
            query = (
                f"SELECT * FROM c WHERE "
                f"(IS_DEFINED(c.Prop_0) AND c.Prop_0 != null AND c.Prop_0 >= '{filter_date_str}' AND "
                f"c.Prop_0 LIKE '%-%-%') "
                f"OR (IS_DEFINED(c.Prop_1) AND c.Prop_1 != null AND c.Prop_1 >= '{filter_date_str}' AND "
                f"c.Prop_1 LIKE '%-%-%') "
                f"ORDER BY c.Prop_0 DESC"
            )
        else:
            # Si no hay fecha, obtener los últimos 5 registros donde Prop_0 o Prop_1 sean fechas válidas
            query = (
                f"SELECT * FROM c WHERE "
                f"(IS_DEFINED(c.Prop_0) AND c.Prop_0 != null AND c.Prop_0 LIKE '%-%-%') "
                f"OR (IS_DEFINED(c.Prop_1) AND c.Prop_1 != null AND c.Prop_1 LIKE '%-%-%') "
                f"ORDER BY c.Prop_0 DESC OFFSET 0 LIMIT 5"
            )


        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        # Formatear los registros en context_data
        context_data = "\n".join(
            [
                f"id: {item.get('id')}, Prop_0: {item.get('Prop_0')}, Prop_1: {item.get('Prop_1')}, "
                f"Prop_2: {item.get('Prop_2')}, Prop_3: {item.get('Prop_3')}, Prop_4: {item.get('Prop_4')}, "
                f"Prop_5: {item.get('Prop_5')}, Prop_6: {item.get('Prop_6')}"
                for item in items
            ]
        )

        if not context_data:
            return func.HttpResponse("No se encontraron datos para la fecha proporcionada o no hay registros recientes.", status_code=404)

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
            max_tokens=500
        )
        answer = response.choices[0].message['content'].strip()
        return func.HttpResponse(answer, status_code=200)
    except Exception as e:
        logging.error("Error al conectar con OpenAI: %s", e)
        return func.HttpResponse("Error al obtener respuesta del modelo.", status_code=500)