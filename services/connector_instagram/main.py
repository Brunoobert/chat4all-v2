import json
import logging
import os
import time
import random
import requests # <--- Necessário para o callback
from kafka import KafkaConsumer

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [INSTAGRAM MOCK] - %(message)s')
logger = logging.getLogger(__name__)

# Configurações
KAFKA_BROKER = os.getenv("KAFKA_BROKER_URL", "kafka:9092")
TOPIC_NAME = "instagram_outbound" # Tópico específico do Instagram

def start_consumer():
    logger.info("Iniciando Connector Instagram Mock...")
    
    # Loop de conexão com retry (para esperar o Kafka subir)
    while True:
        try:
            consumer = KafkaConsumer(
                TOPIC_NAME,
                bootstrap_servers=KAFKA_BROKER,
                auto_offset_reset='latest',
                group_id='instagram_mock_group', # Grupo diferente do WhatsApp
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            logger.info(f"Conectado ao Kafka. Ouvindo tópico: {TOPIC_NAME}")
            break
        except Exception as e:
            logger.warning(f"Kafka indisponível, tentando em 5s... ({e})")
            time.sleep(5)

    # Loop de processamento de mensagens
    for message in consumer:
        data = message.value
        # No Instagram, o destino geralmente é um @usuario
        user_handle = data.get('destination', '@unknown')
        content = data.get('content', '<sem texto>')
        
        logger.info(f"📸 Recebida DM para {user_handle}")
        
        # 1. Simula tempo de envio (delay de rede)
        time.sleep(random.uniform(0.5, 1.5))
        
        # Log simulando a API do Instagram
        logger.info(f"💜 [Instagram API] DM enviada para {user_handle}: {content[:20]}...")
        
        # 2. LÓGICA DE CALLBACK (ATUALIZAÇÃO DE STATUS PARA READ)
        try:
            # Pega os IDs que o Router passou
            msg_id = data.get('original_msg_id')
            chat_id = data.get('chat_id')
            
            if msg_id and chat_id:
                # Simula o tempo que a pessoa demora para abrir o app e ler
                time.sleep(1.0)
                
                # Chama a API interna (frontend_service) para avisar que foi lido
                url = f"http://frontend_service:8000/v1/messages/{msg_id}/status"
                
                payload = {
                    "status": "READ",
                    "conversation_id": chat_id
                }
                
                # Dispara o Webhook
                response = requests.patch(url, json=payload)
                
                if response.status_code == 200:
                    logger.info(f"👀 [Callback] Enviado status READ para API (Msg: {msg_id})")
                else:
                    logger.error(f"❌ [Callback] Erro ao notificar API: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Falha no callback: {e}")

if __name__ == "__main__":
    start_consumer()