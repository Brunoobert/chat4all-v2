import json
import logging
from kafka import KafkaProducer
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_producer = None

def get_kafka_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        logger.info(f"Inicializando KafkaProducer para: {settings.KAFKA_BOOTSTRAP_SERVER}")
        try:
            _producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVER,
                # Serializa o valor (JSON) para bytes
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                # Serializa a chave (String) para bytes <-- IMPORTANTE PARA O PARTICIONAMENTO
                key_serializer=lambda v: str(v).encode('utf-8')
            )
            logger.info("KafkaProducer inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao inicializar KafkaProducer: {e}")
            raise
    return _producer

def close_kafka_producer():
    global _producer
    if _producer:
        _producer.close()
        _producer = None

def send_message_to_kafka(topic: str, message: dict, key: str = None):
    """
    Envia mensagem ao Kafka. 
    O argumento 'key' é obrigatório agora para garantir a ordem das mensagens no chat.
    """
    try:
        producer = get_kafka_producer()
        # Agora passamos a KEY para o produtor
        producer.send(topic, value=message, key=key)
        logger.info(f"Mensagem enviada para tópico {topic}. Key: {key}")
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para o Kafka: {e}")
        raise e