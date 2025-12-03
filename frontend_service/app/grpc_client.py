import grpc
import os
# Importa os arquivos gerados pelo protoc (com o ponto . na frente)
from .proto import auth_pb2, auth_pb2_grpc

# Endereço do Metadata Service dentro da rede Docker
# Nome do container (metadata_service_c ou metadata_service) + porta gRPC
METADATA_GRPC_SERVER = os.getenv("METADATA_HOST", "metadata_service:50051")

def get_user_from_metadata(username: str):
    """
    Conecta ao Metadata Service via gRPC e busca os dados do usuário.
    """
    print(f"[gRPC Client] Conectando a {METADATA_GRPC_SERVER} para buscar: {username}")
    
    # 1. Abre o canal inseguro (dentro da rede docker é ok)
    with grpc.insecure_channel(METADATA_GRPC_SERVER) as channel:
        # 2. Cria o Stub (o cliente)
        stub = auth_pb2_grpc.AuthServiceStub(channel)
        
        # 3. Cria a mensagem de pedido
        request = auth_pb2.UserRequest(username=username)
        
        try:
            # 4. Faz a chamada remota
            response = stub.GetUserByUsername(request)
            
            if response.found:
                print(f"[gRPC Client] Usuário encontrado: {response.username}")
                # Retorna um dicionário compatível com o nosso UserInDB
                return {
                    "username": response.username,
                    "email": response.email,
                    "hashed_password": response.hashed_password,
                    "disabled": not response.is_active
                }
            else:
                print(f"[gRPC Client] Usuário '{username}' não encontrado.")
                return None
                
        except grpc.RpcError as e:
            print(f"[gRPC Client] Erro de conexão: {e}")
            return None