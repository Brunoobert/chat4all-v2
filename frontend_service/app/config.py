from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Carrega variáveis de .env (se existir) e do ambiente
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Assume que o Kafka está rodando localmente,
    # mas pode ser sobreposto por uma variável de ambiente KAFKA_BOOTSTRAP_SERVER
    KAFKA_BOOTSTRAP_SERVER: str = "localhost:29092"
    KAFKA_TOPIC_CHAT_MESSAGES: str = "chat_messages"

# Instância única que será usada em toda a aplicação
settings = Settings()