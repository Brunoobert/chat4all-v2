# /services/metadata_service/app/main.py

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager # <--- Faltava este import
import uuid
import grpc
import asyncio

# Imports locais
from .grpc_handler import AuthService
from .proto import auth_pb2_grpc
from . import models, schemas
from .database import SessionLocal, engine, get_db
from .security import get_password_hash

# Variável global para o servidor gRPC
grpc_server = None

# --- Lifespan (Inicialização e Desligamento) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global grpc_server
    
    # 1. Cria as tabelas no Banco (CockroachDB)
    models.Base.metadata.create_all(bind=engine)
    
    # 2. Inicia o Servidor gRPC (Assíncrono)
    try:
        grpc_server = grpc.aio.server()
        auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), grpc_server)
        grpc_server.add_insecure_port('[::]:50051') # Escuta na porta 50051
        
        # Inicia em background (sem bloquear a API REST)
        await grpc_server.start()
        print("✅ Servidor gRPC rodando na porta 50051")
    except Exception as e:
        print(f"❌ Falha ao iniciar gRPC: {e}")

    yield # A aplicação roda aqui

    # 3. Desligamento gracioso
    if grpc_server:
        print("🛑 Parando servidor gRPC...")
        await grpc_server.stop(0)

# --- Instanciação ÚNICA do App ---
app = FastAPI(
    title="Metadata Service",
    description="Serviço para gerenciar usuários, chats e permissões.",
    version="0.1.0",
    lifespan=lifespan # <--- OBRIGATÓRIO PARA O GRPC FUNCIONAR
)

# --- Endpoints HTTP (REST) ---

@app.get("/health", tags=["Health"])
def read_health_check():
    """Verifica se o serviço está online."""
    return {"status": "ok", "service": "metadata_service"}

@app.post("/v1/users", 
          response_model=schemas.UserInDB, 
          status_code=status.HTTP_201_CREATED,
          tags=["Users"])
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Cria um novo utilizador no CockroachDB.
    """
    # Verifica se o utilizador ou email já existem
    db_user = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == user.email)
    ).first()
    
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username ou email já registado."
        )

    # Cria o objeto modelo do SQLAlchemy com senha hasheada
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user