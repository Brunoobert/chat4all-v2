from app.schemas import UserInDB
from typing import Optional
from .grpc_client import get_user_from_metadata

# --- FIM DO BANCO FALSO ---
# O dicionário fake_users_db foi removido.
# Agora a fonte da verdade é o Metadata Service.

def get_user(username: str) -> Optional[UserInDB]:
    """
    Busca o usuário no Metadata Service via gRPC.
    """
    # Chama a função do cliente gRPC
    user_data = get_user_from_metadata(username)
    
    if user_data:
        # Converte o dicionário para o objeto Pydantic que a API espera
        return UserInDB(**user_data)
    
    return None