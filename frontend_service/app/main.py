import uuid
import datetime
from fastapi import FastAPI, HTTPException, status
from contextlib import asynccontextmanager
from datetime import timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas import User, Token # Adicione User e Token
from app.db import get_user
from app.security import (
    create_access_token, 
    get_current_user, 
    verify_password
)


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

@app.post("/token", response_model=Token, tags=["Autenticação"])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Endpoint de login. Recebe um formulário com 'username' e 'password'.
    Retorna um token de acesso se o login for válido.
    """
    # 1. Busca o utilizador na BD
    user = get_user(form_data.username)

    # 2. Verifica se o utilizador existe e se a password está correta
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de utilizador ou password incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Cria o token de acesso
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = create_access_token(
        data={"sub": user.username}, # "sub" (subject) é o nome padrão para o ID do utilizador no JWT
        expires_delta=access_token_expires
    )

    # 4. Retorna o token
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/v1/messages", 
          response_model=MessageResponse, 
          status_code=status.HTTP_202_ACCEPTED,
          tags=["Messages"])
async def post_message(
    message_in: MessageIn,
    # Esta dependência vai:
    # 1. Exigir um cabeçalho "Authorization: Bearer <token>"
    # 2. Validar o token
    # 3. Retornar o objeto User (ou dar erro 401 se o token for inválido)
    current_user: User = Depends(get_current_user)
):
    """
    Recebe uma nova mensagem e a enfileira no Kafka para processamento.
    Retorna imediatamente com um status de "aceito".
    """
    logger.info(f"Recebida mensagem para chat: {message_in.chat_id}")

    # 1. Gera um ID único e timestamp para a mensagem
    message_id = uuid.uuid4()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    kafka_payload = message_in.model_dump() 

    # ⭐ MUDANÇA DE SEGURANÇA CRÍTICA:
    # Nós IGNORAMOS o 'sender_id' que veio no JSON.
    # Nós usamos o 'username' do TOKEN, que é seguro.
    kafka_payload.update({
        "sender_id": current_user.username, # <--- MUDANÇA IMPORTANTE
        "message_id": str(message_id),
        "timestamp_utc": timestamp,
        "type": "chat_message"
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