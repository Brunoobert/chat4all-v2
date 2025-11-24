from app.schemas import UserInDB
from app.security import get_password_hash
from typing import Optional

# --- A Nossa Base de Dados Falsa ---

fake_users_db = {
    "bruno": UserInDB(
        username="bruno",
        full_name="Bruno E. Bertoldo",
        email="bruno@example.com", # <-- Adicionado para evitar erro de validação
        hashed_password=get_password_hash("test"), # Senha: test
        disabled=False
    ).model_dump(),

    "alice": UserInDB( # <-- Padronizei usando UserInDB aqui também
        username="alice",
        full_name="Alice Wonderland",
        email="alice@example.com",
        hashed_password=get_password_hash("password123"), # Senha: password123
        disabled=False
    ).model_dump(),
}

# --- Funções de Acesso à BD ---

def get_user(username: str) -> Optional[UserInDB]:
    """Busca um utilizador na 'BD' pelo username."""
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)
    return None