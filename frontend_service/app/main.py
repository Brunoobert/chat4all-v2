import uuid
import os
import logging
from datetime import datetime, timezone, timedelta 

from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from typing import List

# Imports do FastAPI
from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File
from contextlib import asynccontextmanager
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

# Seus schemas e lógica interna
from app.schemas import (
    User, Token, MessageIn, MessageResponse, 
    ConversationCreate, ConversationOut
)
from app.db import get_user
from app.security import create_access_token, get_current_user, verify_password
from app.producer import send_message_to_kafka, get_kafka_producer, close_kafka_producer
from app.config import settings

# Import das funções do S3 (MinIO) - NECESSÁRIO PARA O TESTE 1.3
from app.s3 import upload_file_to_minio, create_presigned_url

# Observabilidade
from prometheus_client import make_asgi_app, Counter, Histogram

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
        logger.critical(f"Falha ao conectar no Cassandra: {e}")

    yield
    logger.info("Desligando aplicação...")
    close_kafka_producer()
    if cassandra_session:
        cassandra_session.shutdown()

app = FastAPI(title="Chat4All v2", version="0.1.0", lifespan=lifespan)

# --- MONITORAMENTO ---
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

REQUESTS_TOTAL = Counter("http_requests_total", "Total reqs", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Latencia")

@app.middleware("http")
async def prometheus_middleware(request, call_next):
    start_time = datetime.now()
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        status_code = 500
        raise e
    finally:
        process_time = (datetime.now() - start_time).total_seconds()
        if "/metrics" not in request.url.path:
            REQUEST_LATENCY.observe(process_time)
            REQUESTS_TOTAL.labels(request.method, request.url.path, status_code).inc()

# --- ENDPOINTS ---

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# --- ROTA DE UPLOAD (A QUE ESTAVA FALTANDO) ---
@app.post("/v1/files/upload", tags=["Files"])
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Gera nome único
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    file_id = str(uuid.uuid4())
    object_name = f"{file_id}.{file_ext}"

    logger.info(f"Iniciando upload: {file.filename} -> {object_name}")

    # Envia para o MinIO
    success = upload_file_to_minio(file.file, object_name, file.content_type)

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao salvar arquivo no Storage.")

    # Gera URL
    download_url = create_presigned_url(object_name)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "download_url": download_url,
        "message": "Arquivo enviado com sucesso."
    }

# --- MENSAGENS ---
@app.post("/v1/messages", response_model=MessageResponse, status_code=202, tags=["Messages"])
async def post_message(message_in: MessageIn, current_user: User = Depends(get_current_user)):
    
    logger.info(f"Recebida mensagem para chat: {message_in.chat_id}")

    # --- VALIDAÇÃO DE SEGURANÇA ESTRITA (RF-2.1.6) ---
    if cassandra_session:
        try:
            # 1. Garante formato UUID
            chat_uuid = uuid.UUID(str(message_in.chat_id))
            
            # 2. Busca a conversa
            row = cassandra_session.execute(
                "SELECT members FROM conversations WHERE conversation_id = %s", 
                (chat_uuid,)
            ).one()
            
            # 3. Validação: Conversa Existe?
            if not row:
                # BLOQUEIA SE NÃO ACHAR! Não permite enviar para limbo.
                logger.warning(f"Conversa {chat_uuid} inexistente.")
                raise HTTPException(status_code=404, detail="Conversa não encontrada.")
            
            # 4. Validação: É membro?
            # Trata tanto dict quanto objeto para evitar erros de tipo
            members_list = row['members'] if isinstance(row, dict) else row.members
            
            if current_user.username not in members_list:
                logger.warning(f"BLOQUEIO: {current_user.username} tentou postar em {chat_uuid}")
                raise HTTPException(status_code=403, detail="Você não é membro desta conversa.")

        except HTTPException as he:
            raise he # Repassa os bloqueios (403/404)
        except Exception as e:
            logger.error(f"Erro técnico na validação: {e}")
            # FAIL-CLOSED: Se o banco falhar, bloqueia por segurança
            raise HTTPException(status_code=500, detail="Erro ao validar permissões.")
    else:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
    # -------------------------------------------

    message_id = uuid.uuid4()
    # Horário Local (Brasil)
    timestamp_utc = (datetime.utcnow() - timedelta(hours=3)).isoformat()

    msg_type = "chat_message"
    if message_in.file_id:
        msg_type = "file"
        logger.info("Detectado anexo de arquivo.")

    kafka_payload = message_in.model_dump(mode='json')
    kafka_payload.update({
        "sender_id": current_user.username,
        "message_id": str(message_id),
        "timestamp_utc": timestamp_utc,
        "type": msg_type,
        "status": "SENT",
        "channels": message_in.channels
    })

    try:
        send_message_to_kafka(
            settings.KAFKA_TOPIC_CHAT_MESSAGES,
            message=kafka_payload,
            key=str(message_in.chat_id)
        )
        return MessageResponse(status="accepted", message_id=message_id)
    
    except Exception as e:
        logger.error(f"Erro no envio: {e}")
        raise HTTPException(status_code=500, detail="Erro interno.")

@app.get("/v1/conversations/{conversation_id}/messages")
def get_history(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "Banco offline")
    rows = cassandra_session.execute("SELECT * FROM messages WHERE conversation_id = %s", (conversation_id,))
    return list(rows)

# --- CONVERSAS ---
@app.post("/v1/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(conversation: ConversationCreate, current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "Banco offline")
    
    if current_user.username not in conversation.members:
        conversation.members.append(current_user.username)
    
    cid = uuid.uuid4()
    created_at = datetime.now()
    
    cassandra_session.execute(
        "INSERT INTO conversations (conversation_id, type, members, metadata, created_at) VALUES (%s, %s, %s, %s, %s)",
        (cid, conversation.type, conversation.members, conversation.metadata, created_at)
    )
    return {**conversation.model_dump(), "conversation_id": cid, "created_at": created_at}

@app.get("/v1/conversations", response_model=List[ConversationOut])
def list_conversations(current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "Banco offline")
    rows = cassandra_session.execute("SELECT * FROM conversations LIMIT 100")
    # Filtro em memória (PoC)
    return [r for r in rows if current_user.username in r['members']]

# --- CALLBACK ---
class StatusUpdate(BaseModel):
    status: str
    conversation_id: uuid.UUID

@app.patch("/v1/messages/{message_id}/status")
def update_status(message_id: uuid.UUID, update: StatusUpdate):
    if not cassandra_session: raise HTTPException(503, "Banco offline")
    cassandra_session.execute(
        "UPDATE messages SET status = %s WHERE conversation_id = %s AND message_id = %s",
        (update.status, update.conversation_id, message_id)
    )
    return {"msg": "updated"}