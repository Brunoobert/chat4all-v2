
from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .database import Base # Importamos a 'Base' que criámos

class User(Base):
    __tablename__ = "users"

    # Definimos as colunas
    # Usamos o UUID do CockroachDB (compatível com PostgreSQL)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # (Mais tarde, podemos adicionar 'chats' aqui como uma relação)