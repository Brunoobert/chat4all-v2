import time
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

print("Iniciando Produtor Kafka...")

# Tentar conectar ao Kafka. 
# A porta 29092 é a que expomos no docker-compose.yml para acesso externo (localhost).
producer = None
while producer is None:
    try:
        producer = KafkaProducer(
            bootstrap_servers='localhost:29092',
            # Serializador para converter nossa string 'Olá Kafka' em bytes
            value_serializer=lambda v: str(v).encode('utf-8') 
        )
    except NoBrokersAvailable:
        print("Kafka não está disponível. Tentando novamente em 5 segundos...")
        time.sleep(5)

# Definir o tópico e a mensagem
TOPICO_NOME = 'chat-test'
MENSAGEM = 'Olá Kafka, esta é a minha primeira mensagem!'

print(f"Conectado! Enviando mensagem para o tópico '{TOPICO_NOME}'...")

# Enviar a mensagem
try:
    # .send() é assíncrono. Ele envia e continua.
    producer.send(TOPICO_NOME, MENSAGEM)
    
    # .flush() força o envio de todas as mensagens pendentes antes de sair.
    producer.flush() 
    
    print(f"Mensagem enviada com sucesso: '{MENSAGEM}'")

except Exception as e:
    print(f"Erro ao enviar mensagem: {e}")

finally:
    # Fechar a conexão
    producer.close()
    print("Produtor encerrado.")