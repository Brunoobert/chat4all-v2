from passlib.context import CryptContext

# Configura o contexto do Passlib para usar bcrypt
# "deprecated='auto'" permite atualizar hashes antigos automaticamente se mudarmos a segurança no futuro
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se uma senha em texto bate com o hash salvo no banco.
    Usaremos isso mais tarde no Login.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Gera o hash seguro de uma senha.
    Usamos isso ao criar o usuário.
    """
    return pwd_context.hash(password)