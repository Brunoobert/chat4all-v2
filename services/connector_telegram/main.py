import json
import logging
import os
import requests
from kafka import KafkaConsumer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [TELEGRAM] - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.getenv("KAFKA_BROKER_URL", "kafka:9092")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TOPIC = "telegram_outbound"

def send_to_telegram(chat_id, text):
    if not TELEGRAM_TOKEN:
        logger.error("Token do Telegram não configurado!")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Mensagem enviada para {chat_id}")
        else:
            logger.error(f"Erro Telegram API: {response.text}")
    except Exception as e:
        logger.error(f"Falha na conexão: {e}")

def main():
    logger.info("Iniciando Connector Telegram...")
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id="telegram_connector_group",
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    for message in consumer:
        try:
            data = message.value
            # O worker manda 'destination' que seria o telefone/ID
            # Para teste, se vier vazio, você pode por hardcoded seu ID aqui para testar
            dest = data.get("destination") 
            content = data.get("content")
            
            logger.info(f"Processando mensagem para: {dest}")
            send_to_telegram(dest, content)
            
        except Exception as e:
            logger.error(f"Erro no loop: {e}")

if __name__ == "__main__":
    main()