import json
import logging
import uuid
import os
import time # Usado para os 'retries' de conexão
from kafka import KafkaConsumer
from cassandra.cluster import Cluster, Session
from cassandra.query import PreparedStatement

# --- Configurações ---
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "chat_messages")
# Usamos a porta EXTERNA 29092, pois este script roda no seu PC (localhost)
KAFKA_BROKER = os.getenv("KAFKA_BROKER_URL", "localhost:29092")
CASSANDRA_HOSTS_ENV = os.getenv("CASSANDRA_HOSTS", "localhost")
CASSANDRA_HOSTS = CASSANDRA_HOSTS_ENV.split(',')
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "chat4all_ks")

# Configuração de logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - [WORKER] - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def connect_to_cassandra() -> Session:
    """Tenta conectar ao Cassandra até ter sucesso."""
    logger.info("Tentando conectar ao Cassandra em %s...", CASSANDRA_HOSTS)
    while True:
        try:
            cluster = Cluster(CASSANDRA_HOSTS)
            session = cluster.connect(CASSANDRA_KEYSPACE)
            logger.info("Conectado ao Cassandra com sucesso!")
            return session
        except Exception as e:
            logger.warning("Falha ao conectar ao Cassandra: %s. Tentando novamente em 5s...", e)
            time.sleep(5)

def connect_to_kafka() -> KafkaConsumer:
    """Tenta conectar ao Kafka como consumidor até ter sucesso."""
    logger.info("Tentando conectar ao Kafka em %s...", KAFKA_BROKER)
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BROKER,
                # Garante que o consumidor comece do início se for novo
                auto_offset_reset='earliest', 
                # Deserializa o JSON que a API enviou
                value_deserializer=lambda v: json.loads(v.decode('utf-8'))
            )
            logger.info("Conectado ao Kafka (tópico: %s) com sucesso!", KAFKA_TOPIC)
            return consumer
        except Exception as e:
            logger.warning("Falha ao conectar ao Kafka: %s. Tentando novamente em 5s...", e)
            time.sleep(5)

def main():
    session = connect_to_cassandra()
    consumer = connect_to_kafka()

    # Prepara a query de INSERT (muito mais eficiente)
    # Prepara a query de INSERT (muito mais eficiente)
    insert_query: PreparedStatement = session.prepare(
        """
        INSERT INTO messages (conversation_id, message_id, sender_id, content, created_at)
        VALUES (?, ?, ?, ?, toTimestamp(now())) 
        """
        # AQUI ESTÁ A CORREÇÃO:
        # Removemos o 'uuid(...)' e 'timeuuid(...)' e deixamos apenas os '?'
        # O driver do Python cuidará da conversão dos tipos.
    )

    logger.info("--- Router Worker iniciado e ouvindo mensagens ---")
    try:
        # Loop infinito que "trava" o script, esperando mensagens
        for message in consumer:
            # message.value já é um dicionário Python graças ao value_deserializer
            data = message.value
            logger.info(f"Mensagem recebida: {data.get('message_id')}")

            try:
                # Execute o INSERT
                # ⚠️ ATENÇÃO AQUI ⚠️
                session.execute(
                    insert_query,
                    [
                        uuid.UUID(data.get('chat_id')),    # <-- CONVERTE PARA UUID
                        uuid.UUID(data.get('message_id')), # <-- CONVERTE PARA UUID
                        data.get('sender_id'),
                        data.get('content')
                    ]
                )
                logger.info(f"Mensagem {data.get('message_id')} salva no Cassandra.")

            except Exception as e:
                logger.error(f"Erro ao salvar no Cassandra: {e}. Mensagem: {data}")

    except KeyboardInterrupt:
        logger.info("Encerrando o worker (Ctrl+C)...")
    finally:
        consumer.close()
        session.cluster.shutdown()
        logger.info("Worker encerrado.")

if __name__ == "__main__":
    main()