from pydantic import BaseModel, Field
import uuid
from typing import Optional

# Schema para validar o corpo (JSON) da requisição POST
class MessageIn(BaseModel):
    #sender_id: str
    chat_id: str
    content: Optional[str] = None
    file_id: Optional[str] = None

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

from typing import List, Dict, Optional
from datetime import datetime

# ... (seus schemas anteriores MessageIn, etc) ...

# RF-2.1.1 e 2.1.2: Schema para criar conversa
class ConversationCreate(BaseModel):
    type: str # "private" ou "group"
    members: List[str]
    metadata: Optional[Dict[str, str]] = {}

# RF-2.1.3: Schema para resposta
class ConversationOut(BaseModel):
    conversation_id: uuid.UUID
    type: str
    members: List[str]
    metadata: Dict[str, str]
    created_at: datetime