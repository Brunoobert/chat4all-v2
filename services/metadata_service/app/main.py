# /services/metadata_service/app/main.py

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

# Importamos os nossos módulos .py locais
from . import models, schemas
from .database import SessionLocal, engine, get_db

# 1. Isto diz ao SQLAlchemy para criar todas as tabelas
#    que definimos em models.py (neste caso, a tabela 'users')
#    Isto é ótimo para desenvolvimento, mas para produção
#    usaríamos uma ferramenta de "migração" como o Alembic.
models.Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Metadata Service",
    description="Serviço para gerenciar usuários, chats e permissões.",
    version="0.1.0"
)

# --- Endpoints ---

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
    # NOTA: Ainda não estamos a fazer hash da password.
    # Vamos manter simples por agora.
    
    # Verifica se o utilizador ou email já existem
    db_user = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == user.email)
    ).first()
    
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username ou email já registado."
        )

    # Cria o objeto modelo do SQLAlchemy
    # (Por agora, guardamos a password como texto simples. Vamos corrigir isto mais tarde)
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=user.password # <--- SIMPLESMENTE PARA TESTAR
    )
    
    db.add(new_user)  # Adiciona à sessão
    db.commit()     # Salva no banco de dados
    db.refresh(new_user) # Recarrega o 'new_user' com o 'id' que o banco gerou
    
    return new_user