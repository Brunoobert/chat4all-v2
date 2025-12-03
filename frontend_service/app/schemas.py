from pydantic import BaseModel, Field
import uuid
from typing import Optional, List, Dict
from datetime import datetime

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

# --- CONVERSATIONS (RF-2.1) ---
class ConversationCreate(BaseModel):
    type: str # "private" ou "group"
    members: List[str]
    metadata: Optional[Dict[str, str]] = {}

class ConversationOut(BaseModel):
    conversation_id: uuid.UUID
    type: str
    members: List[str]
    metadata: Dict[str, str]
    created_at: datetime

# --- MESSAGES ---
class MessageIn(BaseModel):
    # sender_id removido (vem do token)
    chat_id: uuid.UUID
    content: Optional[str] = None
    file_id: Optional[str] = None
    # RF-2.3: Canais explícitos
    channels: Optional[List[str]] = ["all"] 

class MessageResponse(BaseModel):
    status: str = "accepted"
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)