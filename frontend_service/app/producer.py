import json
from kafka import KafkaProducer
from app.config import settings
import logging

# Configura um logger básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variável global para armazenar o produtor
_producer: KafkaProducer = None

def get_kafka_producer() -> KafkaProducer:
    """
    Retorna a instância singleton do KafkaProducer.
    """
    global _producer
    if _producer is None:
        logger.info(f"Inicializando KafkaProducer para: {settings.KAFKA_BOOTSTRAP_SERVER}")
        try:
            _producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVER,
                # Serializa o valor como JSON e depois para bytes
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            logger.info("KafkaProducer inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao inicializar KafkaProducer: {e}")
            raise
    return _producer

def close_kafka_producer():
    """
    Fecha o produtor Kafka (usado no shutdown da aplicação).
    """
    global _producer
    if _producer:
        logger.info("Fechando KafkaProducer...")
        _producer.flush()
        _producer.close()
        _producer = None
        logger.info("KafkaProducer fechado.")

def send_message_to_kafka(topic: str, message: dict):
    """
    Envia uma mensagem para um tópico Kafka.
    """
    try:
        producer = get_kafka_producer()
        # send() é assíncrono (fire-and-forget)
        producer.send(topic, value=message)
        # Em um cenário de produção, você pode querer registrar callbacks
        # para tratar erros de envio, mas para este caso,
        # o 'fire-and-forget' atende ao requisito.
        logger.info(f"Mensagem enviada para o tópico {topic}: {message['message_id']}")
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para o Kafka: {e}")
        # Aqui você pode decidir se quer levantar a exceção
        # ou apenas logar e continuar