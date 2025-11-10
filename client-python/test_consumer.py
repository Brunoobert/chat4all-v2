from kafka import KafkaConsumer
import json

print("Iniciando Consumidor Kafka...")

# Definir o tópico que queremos "ouvir"
TOPICO_NOME = 'chat_messages'

# Criar o Consumidor
# Ele vai se conectar ao mesmo broker (Kafka)
consumer = KafkaConsumer(
    TOPICO_NOME,
    bootstrap_servers='localhost:29092',
    
    # Um ID de grupo. O Kafka usa isso para rastrear o que este grupo já leu.
    group_id='meu-grupo-teste', 
    
    # 'earliest' = ler desde o início do tópico (caso o produtor rode antes do consumidor)
    # 'latest' = ler apenas novas mensagens que chegarem
    auto_offset_reset='earliest', 
    
    # Deserializador para converter os bytes de volta para string
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))
)

print(f"Conectado! Aguardando mensagens no tópico '{TOPICO_NOME}'...")

try:
    # O Consumidor é um iterador. Este loop 'for' vai rodar para sempre,
    # bloqueando e esperando por novas mensagens.
    for message in consumer:
        print("\n--- MENSAGEM RECEBIDA! ---")
        print(f"  Tópico:    {message.topic}")
        print(f"  Partição:  {message.partition}")
        print(f"  Offset:    {message.offset}")
        print(f"  Timestamp: {message.timestamp}")
        print(f"  Valor:     {message.value}")
        print("----------------------------\n")

        remetente = message.value.get('sender_id', 'desconhecido')
        conteudo = message.value.get('content', '')
        print(f"Nova mensagem de [{remetente}]: {conteudo}")

except KeyboardInterrupt:
    print("Encerrando o consumidor (Ctrl+C pressionado)...")
finally:
    consumer.close()
    print("Consumidor encerrado.")