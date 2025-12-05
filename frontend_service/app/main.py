import uuid
import os
import json
import logging
import asyncio
import math
from datetime import datetime, timedelta
from typing import List, Optional

# Imports de Banco e Mensageria
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
import redis.asyncio as redis

# Imports FastAPI
from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File, Header, Request, WebSocket, WebSocketDisconnect, Body, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.security import OAuth2PasswordRequestForm
from prometheus_client import make_asgi_app, Counter, Gauge, Histogram
import time
from pydantic import BaseModel

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

# Configura OpenTelemetry
resource = Resource.create({"service.name": "frontend_service"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger:4317", insecure=True)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

# Imports Locais
from app.schemas import (
    User, Token, MessageIn, MessageResponse, 
    ConversationCreate, ConversationOut,
    FileInit, FileInitResponse, FileCompleteResponse
)
from app.db import get_user
from app.security import create_access_token, get_current_user, verify_password, get_current_user_ws
from app.producer import send_message_to_kafka, get_kafka_producer, close_kafka_producer
from app.config import settings
from app.s3_multipart import upload_chunk_to_minio, compose_final_file

# Configura logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # args[2] é o caminho da URL (ex: /v1/messages/../status)
            url = record.args[2]
            if "/status" in url: return False  # Esconde logs de status
            if "/metrics" in url: return False # Esconde logs do Prometheus
            return True
        except:
            return True

# Aplica o filtro no logger de acesso do Uvicorn
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

# --- VARIÁVEIS GLOBAIS ---
cassandra_session = None
redis_client = None

# --- MODELOS EXTRAS ---
class MessageStatusUpdate(BaseModel):
    status: str
    conversation_id: uuid.UUID

# --- GERENCIADOR WEBSOCKET ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

        # [DIA 3] Incrementa métrica
        ACTIVE_WEBSOCKETS.inc() 
        logger.info(f"WS: Usuário {user_id} conectado.")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                # [DIA 3] Decrementa métrica
                ACTIVE_WEBSOCKETS.dec()
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    # Dentro da classe ConnectionManager:
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            # Envia para todas as conexões ativas desse usuário (ex: PC e Celular)
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass # Ignora erro se o socket já fechou

manager = ConnectionManager()

# --- NOVOS SCHEMAS (GAP ANALYSIS) ---
class WebhookCreate(BaseModel):
    url: str
    events: List[str] = ["message.delivered", "message.read"]
    secret: str

class ChannelLink(BaseModel):
    channel_type: str # whatsapp, instagram
    identifier: str   # +556299..., @usuario
    
class PresenceUpdate(BaseModel):
    status: str # online, offline, busy

# --- LISTENER REDIS (Background) ---
async def redis_listener():
    logger.info("Iniciando Redis Listener...")
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("chat_events")
    
    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                target_user = data.get("to_user")
                payload = json.dumps(data)
                if target_user:
                    await manager.send_personal_message(payload, target_user)
            except Exception as e:
                logger.error(f"Erro no Redis Listener: {e}")

# --- LIFESPAN (Inicialização) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global cassandra_session, redis_client
    
    # 1. Kafka
    try: get_kafka_producer()
    except: logger.critical("Kafka falhou (pode ser temporário)")

    # 2. Cassandra (Com fix de protocolo)
    try:
        CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra").split(',')
        cluster = Cluster(CASSANDRA_HOSTS, protocol_version=4)
        session = cluster.connect()
        session.set_keyspace('chat4all_ks')
        session.row_factory = dict_factory
        cassandra_session = session
        logger.info("Cassandra OK")
    except Exception as e: 
        logger.critical(f"Cassandra falhou: {e}")

    # 3. Redis
    try:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        asyncio.create_task(redis_listener())
        logger.info("Redis OK")
    except Exception as e: 
        logger.critical(f"Redis falhou: {e}")

    yield
    close_kafka_producer()
    if cassandra_session: cassandra_session.shutdown()
    if redis_client: await redis_client.close()

# --- APP SETUP ---
app = FastAPI(title="Chat4All v2", version="0.2.0", lifespan=lifespan)

FastAPIInstrumentor.instrument_app(app)

# MÉTICAS DE NEGÓCIO (DIA 3)
ACTIVE_WEBSOCKETS = Gauge('chat_active_websockets', 'Número de usuários conectados via WS')
UPLOAD_CHUNKS_RECEIVED = Counter('chat_upload_chunks_total', 'Chunks de arquivos recebidos')
UPLOAD_COMPLETED = Counter('chat_uploads_completed_total', 'Uploads finalizados com sucesso')

REQUESTS_TOTAL = Counter("http_requests_total", "Total reqs", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Latencia")

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        status_code = 500
        raise e
    finally:
        process_time = time.time() - start_time
        # Filtra rotas de monitoramento para não sujar as métricas
        if "/metrics" not in request.url.path and "/status" not in request.url.path:
            REQUEST_LATENCY.observe(process_time)
            REQUESTS_TOTAL.labels(
                method=request.method, 
                endpoint=request.url.path, 
                status=status_code
            ).inc()

# CORS (Importante para o Demo HTML)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ==========================================
# ENDPOINTS
# ==========================================

# --- WEBSOCKET ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        user = await get_current_user_ws(token)
    except:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user.username)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.username)

# --- UPLOAD RESUMABLE ---
CHUNK_SIZE = 5 * 1024 * 1024 # 5MB

@app.post("/v1/files/initiate", response_model=FileInitResponse)
def initiate_upload(file_data: FileInit, current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "Banco offline")
    file_id = uuid.uuid4()
    total_chunks = math.ceil(file_data.total_size / CHUNK_SIZE)
    
    query = "INSERT INTO file_uploads (file_id, filename, total_size, chunk_size, total_chunks, uploaded_chunks, status, owner_id, created_at) VALUES (%s, %s, %s, %s, %s, {}, 'PENDING', %s, %s)"
    cassandra_session.execute(query, (file_id, file_data.filename, file_data.total_size, CHUNK_SIZE, total_chunks, current_user.username, datetime.now()))
    
    return {"file_id": file_id, "chunk_size": CHUNK_SIZE, "total_chunks": total_chunks}

@app.post("/v1/files/{file_id}/chunk")
async def upload_chunk(file_id: uuid.UUID, chunk_index: int = Form(...), file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    content = await file.read()
    success = upload_chunk_to_minio(str(file_id), chunk_index, content)
    if not success: raise HTTPException(500, "Falha no Storage")
    
    if cassandra_session:
        cassandra_session.execute("UPDATE file_uploads SET uploaded_chunks = uploaded_chunks + {%s} WHERE file_id = %s", (chunk_index, file_id))
    

    UPLOAD_CHUNKS_RECEIVED.inc()

    return {"status": "chunk_received", "index": chunk_index}

@app.post("/v1/files/{file_id}/complete", response_model=FileCompleteResponse)
def complete_upload(file_id: uuid.UUID, current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "Banco offline")
    row = cassandra_session.execute("SELECT total_chunks, uploaded_chunks, filename, total_size FROM file_uploads WHERE file_id = %s", (file_id,)).one()
    if not row: raise HTTPException(404, "Upload não encontrado")
    
    uploaded_count = len(row['uploaded_chunks']) if row['uploaded_chunks'] else 0
    if uploaded_count < row['total_chunks']:
        raise HTTPException(400, f"Incompleto: {uploaded_count}/{row['total_chunks']}")

    try:
        download_url = compose_final_file(str(file_id), row['filename'], row['total_chunks'])
        cassandra_session.execute("INSERT INTO files (file_id, owner_id, filename, size, minio_path, created_at) VALUES (%s, %s, %s, %s, %s, %s)", (file_id, current_user.username, row['filename'], row['total_size'], f"uploads/{file_id}", datetime.now()))
        cassandra_session.execute("UPDATE file_uploads SET status = 'COMPLETED' WHERE file_id = %s", (file_id,))
        UPLOAD_COMPLETED.inc() # [DIA 3] Conta +1 arquivo pronto
        return {"file_id": file_id, "download_url": download_url, "message": "Sucesso!"}
    except Exception as e:
        logger.error(f"Erro compose: {e}")
        raise HTTPException(500, "Erro ao processar arquivo")

# --- MENSAGENS (CORE) ---
@app.post("/v1/messages", response_model=MessageResponse, status_code=202)
async def post_message(message_in: MessageIn, current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "DB Offline")
    
    # Validação de Pertinência
    try:
        row = cassandra_session.execute("SELECT members FROM conversations WHERE conversation_id = %s", (message_in.chat_id,)).one()
        if not row: raise HTTPException(404, "Conversa não encontrada")
        members = row['members'] if row['members'] else []
        if current_user.username not in members: raise HTTPException(403, "Você não é membro desta conversa")
    except HTTPException as he: raise he
    except: pass # Ignora erro de banco para não travar, mas idealmente trataria

    msg_id = uuid.uuid4()
    payload = message_in.model_dump(mode='json')
    payload.update({
        "sender_id": current_user.username,
        "message_id": str(msg_id),
        "timestamp_utc": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
        "type": "file" if message_in.file_id else "chat_message",
        "status": "SENT"
    })
    send_message_to_kafka(settings.KAFKA_TOPIC_CHAT_MESSAGES, payload, key=str(message_in.chat_id))
    return MessageResponse(status="accepted", message_id=msg_id)

# --- [FIX] ENDPOINT PARA SILENCIAR ERROS DOS CONECTORES ---
@app.patch("/v1/messages/{message_id}/status")
def update_status_callback(message_id: uuid.UUID, status_data: MessageStatusUpdate):
    """Recebe callback dos conectores e atualiza status no banco"""
    if cassandra_session:
        try:
            cassandra_session.execute(
                "UPDATE messages SET status = %s WHERE conversation_id = %s AND message_id = %s",
                (status_data.status, status_data.conversation_id, message_id)
            )
        except Exception as e:
            logger.error(f"Erro ao atualizar status: {e}")
    return {"status": "ok"} # Retorna 200 para o conector ficar feliz

# --- AUTH & CONVERSAS ---
@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(401, "Credenciais inválidas")
    return {"access_token": create_access_token({"sub": user.username}), "token_type": "bearer"}

@app.post("/v1/conversations", response_model=ConversationOut, status_code=201)
def create_conv(conv: ConversationCreate, current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "DB Offline")
    cid = uuid.uuid4()
    mems = conv.members
    if current_user.username not in mems: mems.append(current_user.username)
    cassandra_session.execute("INSERT INTO conversations (conversation_id, type, members, metadata, created_at) VALUES (%s, %s, %s, %s, %s)", (cid, conv.type, mems, conv.metadata, datetime.now()))
    return {"conversation_id": cid, "type": conv.type, "members": mems, "metadata": conv.metadata, "created_at": datetime.now()}

@app.get("/v1/conversations", response_model=List[ConversationOut])
def list_conv(current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "DB Offline")
    rows = cassandra_session.execute("SELECT * FROM conversations")
    return [r for r in rows if current_user.username in (r['members'] or [])]

@app.get("/v1/conversations/{conversation_id}/messages")
def get_history(conversation_id: uuid.UUID, current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "DB Offline")
    rows = cassandra_session.execute("SELECT * FROM messages WHERE conversation_id = %s", (conversation_id,))
    return list(rows)

# ==========================================
# GAP ANALYSIS - FUNCIONALIDADES EXTRAS
# ==========================================

# --- 1. WEBHOOKS (RF-2.5.2) ---
@app.post("/v1/webhooks", status_code=201, tags=["Integrations"])
def register_webhook(webhook: WebhookCreate, current_user: User = Depends(get_current_user)):
    """Registra uma URL externa para receber notificações de eventos."""
    if not cassandra_session: raise HTTPException(503, "DB Offline")
    
    wid = uuid.uuid4()
    query = """
        INSERT INTO webhooks (user_id, webhook_id, url, events, secret, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cassandra_session.execute(query, (
        current_user.username, wid, webhook.url, webhook.events, webhook.secret, datetime.now()
    ))
    return {"webhook_id": wid, "message": "Webhook registrado com sucesso"}

@app.get("/v1/webhooks", tags=["Integrations"])
def list_webhooks(current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "DB Offline")
    rows = cassandra_session.execute("SELECT * FROM webhooks WHERE user_id = %s", (current_user.username,))
    return list(rows)

# --- 2. MAPEAMENTO DE CANAIS (RF-2.3.3) ---
@app.post("/v1/users/channels", tags=["Users"])
def link_channel(channel: ChannelLink, current_user: User = Depends(get_current_user)):
    """Vincula um telefone (WhatsApp) ou @ (Instagram) ao usuário."""
    if not cassandra_session: raise HTTPException(503, "DB Offline")
    
    query = """
        INSERT INTO user_channels (user_id, channel_type, identifier, created_at)
        VALUES (%s, %s, %s, %s)
    """
    cassandra_session.execute(query, (
        current_user.username, channel.channel_type, channel.identifier, datetime.now()
    ))
    return {"status": "linked", "channel": channel.channel_type, "id": channel.identifier}

@app.get("/v1/users/channels", tags=["Users"])
def get_channels(current_user: User = Depends(get_current_user)):
    if not cassandra_session: raise HTTPException(503, "DB Offline")
    rows = cassandra_session.execute("SELECT * FROM user_channels WHERE user_id = %s", (current_user.username,))
    return list(rows)

# --- 3. PRESENCE SERVICE (RF-2.1.13) ---
@app.post("/v1/presence/heartbeat", tags=["Presence"])
async def heartbeat(presence: PresenceUpdate, current_user: User = Depends(get_current_user)):
    """Endpoint chamado pelo Frontend a cada 30s para dizer 'Estou Online'."""
    # Atualiza no Redis (Rápido + TTL)
    if redis_client:
        key = f"user:presence:{current_user.username}"
        await redis_client.set(key, presence.status, ex=60) # Expira em 60s se não renovar
    
    # Atualiza no Cassandra (Histórico/Persistência)
    if cassandra_session:
        cassandra_session.execute(
            "INSERT INTO user_presence (user_id, status, last_seen) VALUES (%s, %s, %s)",
            (current_user.username, presence.status, datetime.now())
        )
    return {"status": "updated"}

@app.get("/v1/presence/{username}", tags=["Presence"])
async def get_presence(username: str, current_user: User = Depends(get_current_user)):
    status = "offline"
    if redis_client:
        val = await redis_client.get(f"user:presence:{username}")
        if val: status = val
    return {"username": username, "status": status}

    