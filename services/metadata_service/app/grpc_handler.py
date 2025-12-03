# services/metadata_service/app/grpc_handler.py

import grpc
from .proto import auth_pb2, auth_pb2_grpc
from .database import SessionLocal
from .models import User

# Esta classe implementa a lógica que o main.py espera
class AuthService(auth_pb2_grpc.AuthServiceServicer):
    
    def GetUserByUsername(self, request, context):
        print(f"[gRPC Server] Buscando usuário no CockroachDB: {request.username}")
        
        # 1. Abre sessão com o banco real
        db = SessionLocal()
        try:
            # 2. Faz a query SQL via SQLAlchemy
            user = db.query(User).filter(User.username == request.username).first()
            
            if user:
                print(f"[gRPC Server] Usuário encontrado: {user.email}")
                # 3. Mapeia o modelo do Banco para a resposta gRPC
                return auth_pb2.UserResponse(
                    username=user.username,
                    email=user.email,
                    hashed_password=user.hashed_password, # Envia a senha criptografada para o frontend conferir
                    is_active=user.is_active,
                    found=True
                )
            else:
                print(f"[gRPC Server] Usuário não encontrado.")
                return auth_pb2.UserResponse(found=False)
                
        except Exception as e:
            print(f"[gRPC Server] Erro de banco de dados: {e}")
            return auth_pb2.UserResponse(found=False)
        finally:
            db.close()