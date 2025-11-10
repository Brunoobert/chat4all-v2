import uuid
import datetime
from fastapi import FastAPI, HTTPException, status
from contextlib import asynccontextmanager

from app.schemas import MessageIn, MessageResponse
from app.producer import send_message_to_kafka, get_kafka_producer, close_kafka_producer
from app.config import settings
import logging

# Configura um logger básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gerenciador de ciclo de vida (startup/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código a ser executado antes do app iniciar
    logger.info("Iniciando aplicação...")
    # Pré-conecta o produtor Kafka
    try:
        get_kafka_producer()
        logger.info("Conexão com Kafka estabelecida na inicialização.")
    except Exception as e:
        logger.critical(f"Falha ao conectar com o Kafka na inicialização: {e}")
        # Você pode decidir se quer parar a aplicação aqui
        # raise
    
    yield  # O aplicativo fica em execução aqui
    
    # Código a ser executado após o app parar
    logger.info("Desligando aplicação...")
    close_kafka_producer()

# Cria a instância do FastAPI com o lifespan
app = FastAPI(
    title="Chat4All v2 - Frontend Service",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health Check"])
async def health_check():
    """Verifica a saúde do serviço."""
    return {"status": "ok"}

@app.post("/v1/messages", 
          response_model=MessageResponse, 
          status_code=status.HTTP_202_ACCEPTED,
          tags=["Messages"])
async def post_message(message_in: MessageIn):
    """
    Recebe uma nova mensagem e a enfileira no Kafka para processamento.
    Retorna imediatamente com um status de "aceito".
    """
    logger.info(f"Recebida mensagem para chat: {message_in.chat_id}")

    # 1. Gera um ID único e timestamp para a mensagem
    message_id = uuid.uuid4()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 2. Cria o payload completo que irá para o Kafka
    # (Pydantic model -> dict)
    kafka_payload = message_in.model_dump() 
    kafka_payload.update({
        "message_id": str(message_id),
        "timestamp_utc": timestamp,
        "type": "chat_message" # Ajuda na filtragem futura
    })

    try:
        # 3. Envia para o Kafka (assíncrono)
        send_message_to_kafka(
            topic=settings.KAFKA_TOPIC_CHAT_MESSAGES,
            message=kafka_payload
        )

        # 4. Retorna a resposta imediata
        return MessageResponse(
            status="accepted",
            message_id=message_id
        )
    
    except Exception as e:
        logger.error(f"Falha crítica ao tentar enviar para o Kafka: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível processar a mensagem no momento."
        )