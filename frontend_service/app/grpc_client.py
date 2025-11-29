import grpc
import os
from .proto import auth_pb2, auth_pb2_grpc

# Endereço do Metadata Service (nome do container + porta gRPC)
METADATA_GRPC_SERVER = "metadata_service:50051"

def get_user_from_metadata(username: str):
    """
    Conecta ao Metadata Service via gRPC e busca o usuário.
    """
    print(f"[gRPC Client] Conectando a {METADATA_GRPC_SERVER} para buscar: {username}")
    
    # 1. Cria o canal de comunicação
    with grpc.insecure_channel(METADATA_GRPC_SERVER) as channel:
        # 2. Cria o Stub (o cliente)
        stub = auth_pb2_grpc.AuthServiceStub(channel)
        
        # 3. Cria a mensagem de pedido
        request = auth_pb2.UserRequest(username=username)
        
        try:
            # 4. Faz a chamada remota (RPC)
            response = stub.GetUserByUsername(request)
            
            if response.found:
                print(f"[gRPC Client] Usuário encontrado: {response.username}")
                return {
                    "username": response.username,
                    "email": response.email,
                    "hashed_password": response.hashed_password,
                    "disabled": not response.is_active
                }
            else:
                print("[gRPC Client] Usuário não encontrado.")
                return None
                
        except grpc.RpcError as e:
            print(f"[gRPC Client] Erro de conexão: {e}")
            return None