import grpc
from .proto import auth_pb2, auth_pb2_grpc
from .database import SessionLocal
from .models import User

# Esta classe implementa a interface que definimos no arquivo .proto
class AuthService(auth_pb2_grpc.AuthServiceServicer):
    
    def GetUserByUsername(self, request, context):
        """
        Recebe um username, busca no banco e retorna os dados.
        """
        # 1. Abre uma conexão com o banco
        db = SessionLocal()
        try:
            # 2. Busca o usuário
            print(f"[gRPC] Buscando usuário: {request.username}")
            user = db.query(User).filter(User.username == request.username).first()
            
            # 3. Se encontrar, retorna os dados preenchidos
            if user:
                return auth_pb2.UserResponse(
                    username=user.username,
                    email=user.email,
                    hashed_password=user.hashed_password,
                    is_active=user.is_active,
                    found=True
                )
            
            # 4. Se não encontrar, retorna com found=False
            else:
                return auth_pb2.UserResponse(found=False)
                
        except Exception as e:
            print(f"[gRPC] Erro: {e}")
            # Em caso de erro, retornamos não encontrado por segurança
            return auth_pb2.UserResponse(found=False)
        finally:
            # 5. Sempre fecha a conexão
            db.close()