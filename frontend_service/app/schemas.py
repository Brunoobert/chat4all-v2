from pydantic import BaseModel, Field
import uuid
from typing import Optional

# Schema para validar o corpo (JSON) da requisição POST
class MessageIn(BaseModel):
    chat_id: uuid.UUID
    content: Optional[str] = None # O texto agora é opcional (pode ser só a foto)
    file_id: Optional[str] = None # Novo campo para o ID do arquivo

# Schema para a resposta da nossa API
class MessageResponse(BaseModel):
    status: str = "accepted"
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)

from pydantic import BaseModel, Field
import uuid
from typing import Optional # Adicione este import

# ... (MessageIn e MessageResponse) ...

# Schema para o Token
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Schema base do Utilizador
class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

# Schema do Utilizador como está na "BD"
class UserInDB(User):
    hashed_password: str