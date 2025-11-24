import json
import logging
import os
import time
import random
import requests # <--- Necessário para chamar a API
from kafka import KafkaConsumer

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WHATSAPP MOCK] - %(message)s')
logger = logging.getLogger(__name__)

# Configurações
KAFKA_BROKER = os.getenv("KAFKA_BROKER_URL", "kafka:9092")
TOPIC_NAME = "whatsapp_outbound"

def start_consumer():
    logger.info("Iniciando Connector WhatsApp Mock...")
    
    # Loop de conexão com retry
    while True:
        try:
            consumer = KafkaConsumer(
                TOPIC_NAME,
                bootstrap_servers=KAFKA_BROKER,
                auto_offset_reset='latest',
                group_id='whatsapp_mock_group',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            logger.info(f"Conectado ao Kafka. Ouvindo tópico: {TOPIC_NAME}")
            break
        except Exception as e:
            logger.warning(f"Kafka indisponível, tentando em 5s... ({e})")
            time.sleep(5)

    # Loop de processamento
    for message in consumer:
        data = message.value
        phone = data.get('destination', 'Desconhecido')
        content = data.get('content', '<sem texto>')
        
        logger.info(f"📩 Recebida mensagem para {phone}")
        
        # Simula tempo de envio (delay de rede)
        time.sleep(random.uniform(0.5, 2.0))
        
        # Log simulando o envio externo
        logger.info(f"✅ [WhatsApp API] Entregue ao usuário {phone}: {content[:20]}...")
        
        # --- LÓGICA DE CALLBACK (ATUALIZAÇÃO DE STATUS) ---
        try:
            # Pega os IDs que o Router passou
            msg_id = data.get('original_msg_id')
            chat_id = data.get('chat_id')
            
            if msg_id and chat_id:
                # Simula tempo de leitura do usuário (delay humano)
                time.sleep(1.5)
                
                # Chama a API (usando o nome do serviço no Docker: 'frontend_service')
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