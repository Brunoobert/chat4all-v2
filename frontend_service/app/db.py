from app.schemas import UserInDB
from app.security import get_password_hash
from typing import Optional

# --- A Nossa Base de Dados Falsa ---
# Vamos pré-registar um utilizador "bruno" com a password "test"
# A password é "hasheada" para que não seja armazenada como texto puro.

fake_users_db = {
    "bruno": UserInDB(
        username="bruno",
        full_name="Bruno E. Bertoldo",
        hashed_password=get_password_hash("test"),
        disabled=False
    ).model_dump() # Armazena como um dict
}

# --- Funções de Acesso à BD ---

def get_user(username: str) -> Optional[UserInDB]:
    """Busca um utilizador na 'BD' pelo username."""
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)
    return None