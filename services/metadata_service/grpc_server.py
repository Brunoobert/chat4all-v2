import grpc
from concurrent import futures
import time

# Imports dos arquivos gerados (estão na mesma pasta agora)
import permissions_pb2
import permissions_pb2_grpc

# Se você já tiver a conexão com o banco configurada no app.main ou database.py,
# você pode importá-la aqui. Exemplo:
# from app.database import SessionLocal
# from app.models import User

class AuthServiceImplementation(permissions_pb2_grpc.AuthServiceServicer):
    def CheckUserStatus(self, request, context):
        user_id = request.user_id
        print(f"[gRPC] Recebida verificação para User ID: {user_id}")

        # --- LÓGICA DE BANCO DE DADOS AQUI ---
        # Exemplo real seria:
        # db = SessionLocal()
        # user = db.query(User).filter(User.id == user_id).first()
        # is_active = user.is_active if user else False
        # db.close()

        # --- SIMULAÇÃO PARA TESTE (MOCK) ---
        # Se o ID for "123", dizemos que é inválido. Qualquer outro é válido.
        if user_id == "123":
            is_active = False
            msg = "Usuário Bloqueado (Simulação)"
        else:
            is_active = True
            msg = "Usuário Ativo"
        
        # Retorna a resposta no formato do contrato (.proto)
        return permissions_pb2.UserStatusResponse(
            is_active=is_active,
            status_message=msg
        )

def serve():
    print("Iniciando servidor gRPC...")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Registra nossa classe dentro do servidor
    permissions_pb2_grpc.add_AuthServiceServicer_to_server(
        AuthServiceImplementation(), server
    )
    
    # Escuta na porta 50051
    server.add_insecure_port('[::]:50051')
    server.start()
    print("🚀 Servidor gRPC rodando na porta 50051!")
    
    # Mantém o servidor rodando
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()