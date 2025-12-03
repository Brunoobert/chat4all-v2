import json
import logging
import os
import uuid
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
from cassandra.cluster import Cluster
from prometheus_client import start_http_server, Counter

MESSAGES_PROCESSED = Counter('worker_messages_processed_total', 'Msgs processadas', ['status'])

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WORKER] - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

KAFKA_TOPIC_IN = os.getenv("KAFKA_TOPIC", "chat_messages")
KAFKA_BROKER = os.getenv("KAFKA_BROKER_URL", "kafka:9092")
CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra").split(',')
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "chat4all_ks")

TOPIC_WHATSAPP = "whatsapp_outbound"
TOPIC_INSTAGRAM = "instagram_outbound"

def get_cassandra_session():
    cluster = Cluster(CASSANDRA_HOSTS)
    session = cluster.connect()
    session.set_keyspace(CASSANDRA_KEYSPACE)
    return session

def process_messages():
    try:
        session = get_cassandra_session()
        insert_stmt = session.prepare("""
            INSERT INTO messages 
            (conversation_id, created_at, message_id, sender_id, content, status, type, file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """)

        consumer = KafkaConsumer(
            KAFKA_TOPIC_IN, bootstrap_servers=KAFKA_BROKER,
            auto_offset_reset='earliest', value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))

        logger.info("Worker iniciado...")

        for message in consumer:
            data = message.value
            data['status'] = 'DELIVERED' 
            
            try:
                conv_id = uuid.UUID(data['chat_id'])
                msg_id = uuid.UUID(data['message_id'])
                ts = datetime.fromisoformat(data.get('timestamp_utc')) if data.get('timestamp_utc') else datetime.now()

                session.execute(insert_stmt, (
                    conv_id, ts, msg_id, data['sender_id'], 
                    data.get('content'), data['status'], 
                    data.get('type', 'chat_message'), data.get('file_id')
                ))
                MESSAGES_PROCESSED.labels(status="success").inc()
                logger.info(f"Salvo: {data['message_id']}")

                # ROTEAMENTO (RF-2.3)
                channels = data.get('channels', ['all'])
                content = data.get('content', '')
                # Fallback para lógica antiga de @ se channels for 'all'
                if 'all' in channels and content.startswith('@'):
                    channels = ['instagram']
                
                routing_payload = {
                    "content": content or f"[Arquivo]",
                    "original_msg_id": data['message_id'],
                    "chat_id": data['chat_id']
                }

                if 'all' in channels or 'whatsapp' in channels:
                    routing_payload["destination"] = "+556299999999"
                    producer.send(TOPIC_WHATSAPP, routing_payload)
                    logger.info("-> WhatsApp")

                if 'all' in channels or 'instagram' in channels:
                    routing_payload["destination"] = "usuario_insta"
                    producer.send(TOPIC_INSTAGRAM, routing_payload)
                    logger.info("-> Instagram")

            except Exception as e:
                logger.error(f"Erro msg: {e}")

    except Exception as e:
        logger.critical(f"Erro fatal: {e}")

if __name__ == "__main__":
    start_http_server(8002)
    process_messages()