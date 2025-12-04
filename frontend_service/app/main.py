import uuid
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List

from cassandra.cluster import Cluster
from cassandra.query import dict_factory

from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File, Header, Request
from contextlib import asynccontextmanager
from fastapi.security import OAuth2PasswordRequestForm
from prometheus_client import make_asgi_app, Counter, Histogram

# Seus schemas e lógica interna
from app.schemas import (
    User, Token, MessageIn, MessageResponse, 
    ConversationCreate, ConversationOut
)
from app.db import get_user
from app.security import create_access_token, get_current_user, verify_password
from app.producer import send_message_to_kafka, get_kafka_producer, close_kafka_producer
from app.config import settings
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

# --- ENDPOINTS ---

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# --- [RF-2.1.1] e [RF-2.1.2]: Criar Conversas (Privadas ou Grupos) ---
@app.post("/v1/conversations", response_model=ConversationOut, status_code=201, tags=["Conversations"])
def create_conversation(conversation: ConversationCreate, current_user: User = Depends(get_current_user)):
    if not cassandra_session: 
        raise HTTPException(503, "Banco offline")
    
    # Adiciona o criador aos membros se não estiver
    members_list = conversation.members
    if current_user.username not in members_list:
        members_list.append(current_user.username)
    
    # Gera ID único
    cid = uuid.uuid4()
    created_at = datetime.now()
    
    try:
        # Insere no Cassandra
        query = """
            INSERT INTO conversations (conversation_id, type, members, metadata, created_at) 
            VALUES (%s, %s, %s, %s, %s)
        """
        cassandra_session.execute(query, (
            cid, 
            conversation.type, 
            members_list, 
            conversation.metadata, 
            created_at
        ))
        
        logger.info(f"Conversa criada: {cid} do tipo {conversation.type}")
        
        return {
            "conversation_id": cid,
            "type": conversation.type,
            "members": members_list,
            "metadata": conversation.metadata,
            "created_at": created_at
        }
    except Exception as e:
        logger.error(f"Erro ao criar conversa: {e}")
        raise HTTPException(500, "Erro ao persistir conversa.")

# --- [RF-2.1.3]: Listar Conversas do Usuário ---
@app.get("/v1/conversations", response_model=List[ConversationOut], tags=["Conversations"])
def list_conversations(current_user: User = Depends(get_current_user)):
    if not cassandra_session: 
        raise HTTPException(503, "Banco offline")
    
    try:
        # Nota: Em produção, usaríamos uma tabela de lookup 'user_conversations'
        # Para PoC/Hackathon, fazemos SELECT ALL e filtramos no Python (ALLOW FILTERING é lento)
        rows = cassandra_session.execute("SELECT * FROM conversations")
        
        user_conversations = []
        for row in rows:
            # Cassandra retorna List como SortedSet ou List dependendo do driver, convertemos
            members = list(row['members']) if row['members'] else []
            if current_user.username in members:
                user_conversations.append(row)
        
        return user_conversations
    except Exception as e:
        logger.error(f"Erro ao listar conversas: {e}")
        raise HTTPException(500, "Erro interno ao buscar conversas.")

# --- MENSAGENS (Já existente, apenas mantendo a integridade) ---
@app.post("/v1/messages", response_model=MessageResponse, status_code=202, tags=["Messages"])
async def post_message(message_in: MessageIn, current_user: User = Depends(get_current_user)):
    # Validações básicas
    if not cassandra_session: raise HTTPException(503, "Banco offline")

    # Verifica se conversa existe (Opcional: Cachear isso seria bom no futuro)
    try:
        chat_uuid = message_in.chat_id # O Pydantic já converteu para UUID
        row = cassandra_session.execute(
            "SELECT members FROM conversations WHERE conversation_id = %s", (chat_uuid,)
        ).one()
        
        if not row:
            raise HTTPException(404, "Conversa não encontrada.")
        
        # Valida pertinência
        members = row['members'] if row['members'] else []
        if current_user.username not in members:
            raise HTTPException(403, "Você não é membro desta conversa.")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro validação: {e}")
        raise HTTPException(500, "Erro de validação.")

    # Prepara envio
    message_id = uuid.uuid4()
    timestamp_utc = (datetime.utcnow() - timedelta(hours=3)).isoformat()
    
    # Monta payload
    payload = message_in.model_dump(mode='json')
    payload.update({
        "sender_id": current_user.username,
        "message_id": str(message_id),
        "timestamp_utc": timestamp_utc,
        "type": "file" if message_in.file_id else "chat_message",
        "status": "SENT"
    })

    # Envia para Kafka
    try:
        send_message_to_kafka(settings.KAFKA_TOPIC_CHAT_MESSAGES, payload, key=str(message_in.chat_id))
        return MessageResponse(status="accepted", message_id=message_id)
    except Exception as e:
        logger.error(f"Kafka error: {e}")
        raise HTTPException(500, "Erro no envio da mensagem")

# --- HISTÓRICO ---
@app.get("/v1/conversations/{conversation_id}/messages", tags=["Messages"])
def get_history(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "Banco offline")
    # Busca mensagens ordenadas (graças ao CLUSTERING ORDER BY do Cassandra)
    rows = cassandra_session.execute(
        "SELECT * FROM messages WHERE conversation_id = %s", (conversation_id,)
    )
    return list(rows)

# --- UPLOAD SIMPLES (Será substituído no Dia 2) ---
@app.post("/v1/files/upload", tags=["Files"])
async def upload_file(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    file_id = str(uuid.uuid4())
    object_name = f"{file_id}_{file.filename}"
    upload_file_to_minio(file.file, object_name, file.content_type)
    return {"file_id": file_id, "url": create_presigned_url(object_name)}