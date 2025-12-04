from pydantic import BaseModel, Field, model_validator
import uuid
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime

# --- ENUMS (Novos) ---
class ChannelType(str, Enum):
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    TELEGRAM = "telegram"
    ALL = "all"

# --- AUTH & USERS ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

# --- CONVERSATIONS ---
class ConversationCreate(BaseModel):
    type: str 
    members: List[str]
    metadata: Optional[Dict[str, str]] = {}

class ConversationOut(BaseModel):
    conversation_id: uuid.UUID
    type: str
    members: List[str]
    metadata: Optional[Dict[str, str]] = {}
    created_at: datetime

# --- MESSAGES (Atualizado) ---
class MessageIn(BaseModel):
    chat_id: uuid.UUID
    content: Optional[str] = None
    file_id: Optional[str] = None
    # Validação: aceita lista de canais ou "all" como padrão
    channels: Optional[List[ChannelType]] = [ChannelType.ALL]

    @model_validator(mode='after')
    def check_content_or_file(self):
        if not self.content and not self.file_id:
            raise ValueError('A mensagem deve conter texto ou um arquivo.')
        return self

class MessageResponse(BaseModel):
    status: str = "accepted"
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)