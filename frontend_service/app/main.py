import uuid
import os
import logging
from datetime import datetime, timezone 

from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from typing import List

from fastapi import FastAPI, HTTPException, status, Depends
from contextlib import asynccontextmanager
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm

# Seus schemas e lógica interna
from app.schemas import User, Token, MessageIn, MessageResponse
from app.db import get_user
from app.security import create_access_token, get_current_user, verify_password
from app.producer import send_message_to_kafka, get_kafka_producer, close_kafka_producer
from app.config import settings

# Configura logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Variável Global para o Cassandra ---
# Inicializamos como None para evitar o erro "not defined" se a conexão falhar
cassandra_session = None

# --- Lifespan (Inicialização e Desligamento) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global cassandra_session
    logger.info("Iniciando aplicação...")
    
    # 1. Conectar Kafka
    try:
        get_kafka_producer()
        logger.info("Conexão com Kafka OK.")
    except Exception as e:
        logger.critical(f"Falha no Kafka: {e}")

    # 2. Conectar Cassandra (Tenta conectar na subida)
    try:
        CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra").split(',')
        cluster = Cluster(CASSANDRA_HOSTS)
        session = cluster.connect()
        session.set_keyspace('chat4all_ks')
        session.row_factory = dict_factory
        cassandra_session = session # Atribui à variável global
        logger.info("Conexão com Cassandra OK.")
    except Exception as e:
        logger.critical(f"Falha ao conectar no Cassandra durante o startup: {e}")
        # Não paramos a API, mas o GET vai falhar controladamente se não tiver banco

    yield  # Aplicação roda aqui

    # Shutdown
    logger.info("Desligando aplicação...")
    close_kafka_producer()
    if cassandra_session:
        cassandra_session.shutdown()

app = FastAPI(title="Chat4All v2", version="0.1.0", lifespan=lifespan)

# --- Endpoints ---

@app.post("/token", response_model=Token, tags=["Autenticação"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/v1/messages", response_model=MessageResponse, status_code=202, tags=["Messages"])
async def post_message(message_in: MessageIn, current_user: User = Depends(get_current_user)):
    logger.info(f"Recebida mensagem para chat: {message_in.chat_id}")

    message_id = uuid.uuid4()
    timestamp_utc = datetime.now(timezone.utc).isoformat()

    kafka_payload = message_in.model_dump(mode='json')
    kafka_payload.update({
        "sender_id": current_user.username,
        "message_id": str(message_id),
        "timestamp_utc": timestamp_utc,
        "type": "chat_message",
        "status": "SENT"
    })

    try:
        send_message_to_kafka(
            topic=settings.KAFKA_TOPIC_CHAT_MESSAGES,
            message=kafka_payload,
            key=str(message_in.chat_id)
        )
        return MessageResponse(status="accepted", message_id=message_id)
    
    except Exception as e:
        logger.error(f"Erro no envio: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao processar mensagem.")

@app.get("/v1/conversations/{conversation_id}/messages", tags=["Messages"])
def get_conversation_history(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user)):
    
    # Verificação de segurança: O banco está conectado?
    if cassandra_session is None:
        logger.error("Tentativa de ler histórico sem conexão com Cassandra.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados de mensagens indisponível no momento."
        )

    logger.info(f"Buscando histórico: {conversation_id}")
    query = "SELECT * FROM messages WHERE conversation_id = %s"
    try:
        rows = cassandra_session.execute(query, (conversation_id,))
        return list(rows)
    except Exception as e:
        logger.error(f"Erro Cassandra: {e}")
        raise HTTPException(status_code=500, detail="Erro ao ler histórico.")