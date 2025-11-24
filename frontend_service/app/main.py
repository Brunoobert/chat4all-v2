import uuid
import os
import logging
# 1. Imports de Data e Hora
from datetime import datetime, timezone, timedelta 

from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from typing import List

# 2. Adicionados UploadFile e File para o MinIO
from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File
from contextlib import asynccontextmanager
from fastapi.security import OAuth2PasswordRequestForm

# Seus schemas e lógica interna
from app.schemas import User, Token, MessageIn, MessageResponse
from app.db import get_user
from app.security import create_access_token, get_current_user, verify_password
from app.producer import send_message_to_kafka, get_kafka_producer, close_kafka_producer
from app.config import settings

# 3. Import das funções do S3 (MinIO)
from app.s3 import upload_file_to_minio, create_presigned_url

# Configura logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variável Global Cassandra
cassandra_session = None

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global cassandra_session
    logger.info("Iniciando aplicação...")
    
    try:
        get_kafka_producer()
        logger.info("Conexão com Kafka OK.")
    except Exception as e:
        logger.critical(f"Falha no Kafka: {e}")

    try:
        CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra").split(',')
        cluster = Cluster(CASSANDRA_HOSTS)
        session = cluster.connect()
        session.set_keyspace('chat4all_ks')
        session.row_factory = dict_factory
        cassandra_session = session
        logger.info("Conexão com Cassandra OK.")
    except Exception as e:
        logger.critical(f"Falha ao conectar no Cassandra durante o startup: {e}")

    yield
    logger.info("Desligando aplicação...")
    close_kafka_producer()
    if cassandra_session:
        cassandra_session.shutdown()

app = FastAPI(title="Chat4All v2", version="0.1.0", lifespan=lifespan)

# --- Endpoints ---

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health Check"])
async def health_check():
    return {"status": "ok"}

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

# --- ROTA DE UPLOAD (MINIO) ---
@app.post("/v1/files/upload", tags=["Files"])
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Faz upload de um arquivo para o MinIO e retorna um ID e URL temporária.
    """
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    file_id = str(uuid.uuid4())
    object_name = f"{file_id}.{file_ext}"

    logger.info(f"Iniciando upload: {file.filename} -> {object_name}")

    success = upload_file_to_minio(file.file, object_name, file.content_type)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Falha ao salvar arquivo no Storage."
        )

    download_url = create_presigned_url(object_name)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "download_url": download_url,
        "message": "Arquivo enviado com sucesso."
    }

# --- ROTA DE MENSAGENS (KAFKA) ---
@app.post("/v1/messages", response_model=MessageResponse, status_code=202, tags=["Messages"])
async def post_message(message_in: MessageIn, current_user: User = Depends(get_current_user)):
    
    logger.info(f"PAYLOAD RECEBIDO: {message_in.model_dump()}")
    
    message_id = uuid.uuid4()
    
    # Horário Brasília (UTC-3) forçado visualmente para o Cassandra
    horario_brasilia = (datetime.utcnow() - timedelta(hours=3)).isoformat()

    # Lógica de Tipo
    msg_type = "chat_message"
    if message_in.file_id:
        msg_type = "file"
        logger.info("Detectado anexo de arquivo. Tipo alterado para 'file'.")

    kafka_payload = message_in.model_dump(mode='json')
    kafka_payload.update({
        "sender_id": current_user.username,
        "message_id": str(message_id),
        "timestamp_utc": horario_brasilia,
        "type": msg_type,
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
    if cassandra_session is None:
        raise HTTPException(status_code=503, detail="Banco indisponível.")
    
    logger.info(f"Buscando histórico: {conversation_id}")
    query = "SELECT * FROM messages WHERE conversation_id = %s"
    try:
        rows = cassandra_session.execute(query, (conversation_id,))
        return list(rows)
    except Exception as e:
        logger.error(f"Erro Cassandra: {e}")
        raise HTTPException(status_code=500, detail="Erro ao ler histórico.")