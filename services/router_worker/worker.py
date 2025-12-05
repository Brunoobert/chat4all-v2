import json
import logging
import os
import uuid
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from prometheus_client import start_http_server, Counter
import redis

# Métricas
MESSAGES_PROCESSED = Counter('worker_messages_processed', 'Msgs processadas', ['status'])
REALTIME_EVENTS = Counter('worker_realtime_events_total', 'Eventos enviados ao Redis')

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WORKER] - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Variáveis de Ambiente
KAFKA_TOPIC_IN = os.getenv("KAFKA_TOPIC", "chat_messages")
KAFKA_BROKER = os.getenv("KAFKA_BROKER_URL", "kafka:9092")
CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra").split(',')
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "chat4all_ks")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Tópicos de Saída
TOPIC_WHATSAPP = "whatsapp_outbound"
TOPIC_INSTAGRAM = "instagram_outbound"
TOPIC_TELEGRAM = "telegram_outbound"

# Cliente Redis Global
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    logger.info(f"Conectado ao Redis: {REDIS_URL}")
except Exception as e:
    logger.error(f"Falha ao configurar Redis: {e}")
    redis_client = None

def get_cassandra_session():
    cluster = Cluster(CASSANDRA_HOSTS, protocol_version=4)
    session = cluster.connect()
    session.set_keyspace(CASSANDRA_KEYSPACE)
    session.row_factory = dict_factory
    return session

def process_messages():
    try:
        session = get_cassandra_session()
        
        insert_stmt = session.prepare("""
            INSERT INTO messages 
            (conversation_id, created_at, message_id, sender_id, content, status, type, file_id, channels)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """)

        select_members_stmt = session.prepare("""
            SELECT members FROM conversations WHERE conversation_id = ?
        """)

        consumer = KafkaConsumer(
            KAFKA_TOPIC_IN, bootstrap_servers=KAFKA_BROKER,
            group_id="router_worker_group",
            auto_offset_reset='earliest', 
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER, 
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        logger.info(f"Worker iniciado. Ouvindo tópico: {KAFKA_TOPIC_IN}")

        for message in consumer:
            data = message.value
            data['status'] = 'DELIVERED' 
            
            try:
                conv_id = uuid.UUID(data['chat_id'])
                msg_id = uuid.UUID(data['message_id'])
                ts = datetime.fromisoformat(data.get('timestamp_utc')) if data.get('timestamp_utc') else datetime.now()
                channels_list = data.get('channels', ['all'])

                # 1. Persistência
                session.execute(insert_stmt, (
                    conv_id, ts, msg_id, data['sender_id'], 
                    data.get('content'), data['status'], 
                    data.get('type', 'chat_message'), data.get('file_id'),
                    channels_list
                ))
                MESSAGES_PROCESSED.labels(status="success").inc()
                logger.info(f"Salvo no DB: {msg_id}")

                # 2. Real-Time (Redis)
                if redis_client:
                    try:
                        row = session.execute(select_members_stmt, (conv_id,)).one()
                        members = []
                        if row:
                            try: members = row['members']
                            except: members = row[0] # Fallback para tupla

                        if members:
                            ws_payload = {
                                "type": "message",
                                "conversation_id": str(conv_id),
                                "sender_id": data['sender_id'],
                                "content": data.get('content', ''),
                                "file_id": data.get('file_id'),
                                "timestamp": data.get('timestamp_utc'),
                                "to_user": ""
                            }
                            for member in members:
                                # Modo ECO ativado (comentado o if)
                                # if member != data['sender_id']: 
                                event = ws_payload.copy()
                                event["to_user"] = member
                                redis_client.publish("chat_events", json.dumps(event))
                                REALTIME_EVENTS.inc()
                                logger.info(f"⚡ REAL-TIME: Enviado para Redis -> {member}")
                    except Exception as rx:
                        logger.error(f"Erro Redis: {rx}")

                # 3. Roteamento Externo (Kafka)
                content = data.get('content', '')
                routing_payload = {
                    "content": content or f"[Arquivo ID: {data.get('file_id')}]",
                    "original_msg_id": str(msg_id),
                    "chat_id": str(conv_id),
                    "sender_id": data['sender_id']
                }

                destinations = []
                if 'all' in channels_list:
                    destinations.append((TOPIC_WHATSAPP, "whatsapp"))
                    destinations.append((TOPIC_INSTAGRAM, "instagram"))
                    destinations.append((TOPIC_TELEGRAM, "telegram"))
                else:
                    if 'whatsapp' in channels_list: destinations.append((TOPIC_WHATSAPP, "whatsapp"))
                    if 'instagram' in channels_list: destinations.append((TOPIC_INSTAGRAM, "instagram"))
                    if 'telegram' in channels_list: destinations.append((TOPIC_TELEGRAM, "telegram"))

                # Loop seguro: só tenta acessar channel_name SE houver destinos
                for topic, channel_name in destinations:
                    target = "unknown"
                    if channel_name == "whatsapp":
                        target = "+556299999999"
                    elif channel_name == "instagram":
                        target = "@usuario_insta"
                    elif channel_name == "telegram":
                        target = "8535109249" # SEU ID REAL DO TELEGRAM
                    
                    payload_final = routing_payload.copy()
                    payload_final["destination"] = target
                    
                    producer.send(topic, payload_final)
                    logger.info(f"-> Roteado para {channel_name} (Tópico: {topic})")

                producer.flush()

            except Exception as e:
                logger.error(f"Erro msg {data.get('message_id')}: {e}")
                MESSAGES_PROCESSED.labels(status="error").inc()

    except Exception as e:
        logger.critical(f"Erro fatal Worker: {e}")

if __name__ == "__main__":
    start_http_server(8002)
    process_messages()