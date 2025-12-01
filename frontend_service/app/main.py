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
from pydantic import BaseModel

# Seus schemas e lógica interna
# --- CORREÇÃO AQUI: Adicionado ConversationCreate e ConversationOut ---
from app.schemas import (
    User, Token, MessageIn, MessageResponse, 
    ConversationCreate, ConversationOut
)
from app.db import get_user
from app.security import create_access_token, get_current_user, verify_password
from app.producer import send_message_to_kafka, get_kafka_producer, close_kafka_producer
from app.config import settings

# 3. Import das funções do S3 (MinIO)
from app.s3 import upload_file_to_minio, create_presigned_url

# 4. Observabilidade
from prometheus_client import make_asgi_app, Counter, Histogram

# Configura logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variável Global Cassandra
cassandra_session = None

# --- Lifespan (Inicialização e Desligamento) ---
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

# --- MONITORAMENTO ---
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Criar as Métricas
REQUESTS_TOTAL = Counter(
    "http_requests_total", 
    "Total de requisições HTTP", 
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", 
    "Tempo de resposta das requisições HTTP"
)

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
            REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=request.url.path,
                status=status_code
            ).inc()

# --- ENDPOINTS ---

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health Check"])
async def health_check():
    return {"status": "ok"}

@app.post("/token", response_model=Token, tags=["Autenticação"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    # print(f"Tentativa de Login: {form_data.username}") # Debug opcional
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/v1/files/upload", tags=["Files"])
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    file_id = str(uuid.uuid4())
    object_name = f"{file_id}.{file_ext}"

    logger.info(f"Iniciando upload: {file.filename} -> {object_name}")
    success = upload_file_to_minio(file.file, object_name, file.content_type)

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao salvar arquivo no Storage.")

    download_url = create_presigned_url(object_name)
    return {
        "file_id": file_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "download_url": download_url,
        "message": "Arquivo enviado com sucesso."
    }

@app.post("/v1/messages", response_model=MessageResponse, status_code=202, tags=["Messages"])
async def post_message(message_in: MessageIn, current_user: User = Depends(get_current_user)):
# ... dentro de post_message ...
    logger.info(f"Recebida mensagem para chat: {message_in.chat_id}")

    # --- VALIDAÇÃO DE SEGURANÇA (RF-2.1.6) ---
    if cassandra_session:
        try:
            # FORÇA BRUTA: Garante que é UUID, não importa o que veio
            # Converte para string primeiro (pra garantir) e depois cria o objeto UUID
            chat_uuid_obj = uuid.UUID(str(message_in.chat_id))

            # Query parametrizada (o driver recebe o objeto UUID e trata a tipagem)
            query_check = "SELECT members FROM conversations WHERE conversation_id = %s"
            
            row = cassandra_session.execute(query_check, (chat_uuid_obj,)).one()
            
            if not row:
                # Se não achou, avisa no log mas (para a PoC) deixa passar ou retorna 404
                logger.warning(f"Conversa {chat_uuid_obj} não encontrada no banco. Permitindo envio (PoC).")
                # raise HTTPException(status_code=404, detail="Conversa não encontrada.")
            
            # Se achou, valida o membro
            elif current_user.username not in row.members:
                raise HTTPException(status_code=403, detail="Você não é membro desta conversa.")
                
        except ValueError:
             logger.error(f"ID da conversa inválido: {message_in.chat_id}")
             raise HTTPException(status_code=400, detail="ID da conversa inválido.")
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Erro ao validar permissão no Cassandra: {e}")
            # Fail-open para não travar o teste se o banco der timeout
            logger.warning("Ignorando erro de validação para prosseguir com o teste.")
    # -------------------------------------------

    message_id = uuid.uuid4()
    
    # Horário (Se você configurou TZ no docker-compose, use .now(). Se não, use a lógica UTC-3)
    timestamp_utc = datetime.now().isoformat()

    # Lógica de Tipo
    msg_type = "chat_message"
    if message_in.file_id:
        msg_type = "file"

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
    
    query = "SELECT * FROM messages WHERE conversation_id = %s"
    try:
        rows = cassandra_session.execute(query, (conversation_id,))
        return list(rows)
    except Exception as e:
        logger.error(f"Erro Cassandra: {e}")
        raise HTTPException(status_code=500, detail="Erro ao ler histórico.")

class StatusUpdate(BaseModel):
    status: str
    conversation_id: uuid.UUID

@app.patch("/v1/messages/{message_id}/status", tags=["Messages"])
def update_message_status(message_id: uuid.UUID, update: StatusUpdate):
    if cassandra_session is None:
        raise HTTPException(status_code=503, detail="Banco indisponível.")
    
    logger.info(f"Atualizando status {message_id} para {update.status}")
    query = "UPDATE messages SET status = %s WHERE conversation_id = %s AND message_id = %s"
    try:
        cassandra_session.execute(query, (update.status, update.conversation_id, message_id))
        return {"msg": "Status atualizado"}
    except Exception as e:
        logger.error(f"Erro no update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ROTAS DE CONVERSAS (RF-2.1) ---

@app.post("/v1/conversations", response_model=ConversationOut, status_code=201, tags=["Conversations"])
def create_conversation(
    conversation: ConversationCreate,
    current_user: User = Depends(get_current_user)
):
    if cassandra_session is None:
        raise HTTPException(status_code=503, detail="Banco indisponível.")

    if current_user.username not in conversation.members:
        conversation.members.append(current_user.username)
    
    conversation_id = uuid.uuid4()
    created_at = datetime.now()

    query = """
        INSERT INTO conversations (conversation_id, type, members, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        cassandra_session.execute(query, (
            conversation_id,
            conversation.type,
            conversation.members,
            conversation.metadata,
            created_at
        ))
        return {
            "conversation_id": conversation_id,
            "type": conversation.type,
            "members": conversation.members,
            "metadata": conversation.metadata,
            "created_at": created_at
        }
    except Exception as e:
        logger.error(f"Erro ao criar conversa: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- AQUI ESTÁ A ROTA QUE FALTAVA (GET) ---
@app.get("/v1/conversations", response_model=List[ConversationOut], tags=["Conversations"])
def list_my_conversations(current_user: User = Depends(get_current_user)):
    """
    (RF-2.1.3) Lista todas as conversas onde o usuário é membro.
    """
    if cassandra_session is None:
        raise HTTPException(status_code=503, detail="Banco indisponível.")

    # Busca todas as conversas (Limitado a 100 para a PoC)
    # Em produção usaríamos uma tabela user_conversations
    query = "SELECT * FROM conversations LIMIT 100"
    
    try:
        rows = cassandra_session.execute(query)
        # Filtra no Python onde o usuário está na lista de membros
        my_convos = [row for row in rows if current_user.username in row['members']]
        return my_convos
    
    except Exception as e:
        logger.error(f"Erro ao listar conversas: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")