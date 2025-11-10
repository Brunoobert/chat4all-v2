from pydantic import BaseModel, Field
import uuid

# Schema para validar o corpo (JSON) da requisição POST
class MessageIn(BaseModel):
    sender_id: str
    chat_id: str
    content: str

# Schema para a resposta da nossa API
class MessageResponse(BaseModel):
    status: str = "accepted"
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)