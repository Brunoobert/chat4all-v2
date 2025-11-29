from app.schemas import UserInDB
from typing import Optional
from .grpc_client import get_user_from_metadata # <--- Importamos o cliente gRPC

# --- MUDANÇA CRÍTICA: O BANCO FALSO MORREU ---
# fake_users_db = { ... }  <-- Apagado!

def get_user(username: str) -> Optional[UserInDB]:
    """
    Agora busca o usuário no Metadata Service via gRPC.
    """
    # Chama o gRPC
    user_data = get_user_from_metadata(username)
    
    if user_data:
        # Converte o dicionário recebido para o modelo Pydantic
        return UserInDB(**user_data)
    
    return None