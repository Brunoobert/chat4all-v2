from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

# --- Configuração de Hashing de Password ---
# Usamos bcrypt, o padrão da indústria
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Configuração do Esquema OAuth2 ---
# Isto diz ao FastAPI para procurar um token em:
# 1. Um cabeçalho "Authorization: Bearer <token>"
# 2. Um formulário de login com "username" e "password"
# O 'tokenUrl' é o endpoint que *cria* o token 
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# --- Funções de Hashing ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a password plana corresponde ao hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Gera um hash para a password plana."""
    return pwd_context.hash(password)


# --- Funções de Token JWT ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Cria um novo token de acesso JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Padrão de 15 minutos se não for especificado
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

# --- Dependência Principal de Segurança ---
# Esta é a função que vamos usar para proteger os nossos endpoints

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependência do FastAPI: Valida o token e retorna os dados do utilizador.
    Isto será injetado em qualquer endpoint que o exija.
    """
    # (Importamos aqui dentro para evitar importação circular)
    from app.db import get_user 
    from app.schemas import TokenData

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        token_data = TokenData(username=username)

    except JWTError:
        raise credentials_exception

    # Obtém o utilizador da nossa "BD"
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception

    # (Numa app real, você também verificaria se o utilizador está ativo)
    # if user.disabled:
    #     raise HTTPException(status_code=400, detail="Utilizador inativo")

    return user

async def get_current_user_ws(token: str):
    """Versão do get_current_user que não usa Depends, para WebSockets"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise Exception()
        from app.db import get_user
        user = get_user(username=username)
        if user is None: raise Exception()
        return user
    except JWTError:
        raise Exception("Token inválido")