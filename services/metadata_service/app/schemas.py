from pydantic import BaseModel, EmailStr
import uuid

# --- User Schemas ---

# Schema 'base' (campos comuns)
class UserBase(BaseModel):
    username: str
    email: EmailStr

# Schema para CRIAR um utilizador (o que recebemos no POST)
class UserCreate(UserBase):
    password: str # Vamos receber a password em texto plano

# Schema para LER um utilizador (o que devolvemos da API)
# Não queremos devolver a password!
class UserInDB(UserBase):
    id: uuid.UUID
    is_active: bool

    class Config:
        orm_mode = True # Diz ao Pydantic para ler dados de objetos (ORM)