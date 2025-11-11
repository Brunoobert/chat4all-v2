from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets

class Settings(BaseSettings):
    # Carrega variáveis de .env (se existir) e do ambiente
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Assume que o Kafka está rodando localmente,
    # mas pode ser sobreposto por uma variável de ambiente KAFKA_BOOTSTRAP_SERVER
    KAFKA_BOOTSTRAP_SERVER: str = "localhost:29092"
    KAFKA_TOPIC_CHAT_MESSAGES: str = "chat_messages"
    # Configurações de Segurança JWT
    # Para gerar um bom segredo, execute no terminal: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = secrets.token_hex(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

# Instância única que será usada em toda a aplicação
settings = Settings()