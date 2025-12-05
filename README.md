

Aqui está o **README.md** definitivo e atualizado. Pode substituir o conteúdo do seu arquivo.

-----

# Chat4All v2 - Plataforma de Comunicação Ubíqua (Enterprise Edition)

**Versão:** 1.1.0 (Final Release)

Sistema de mensageria distribuída de alta performance, projetado para escalar horizontalmente e suportar comunicação em tempo real, uploads de arquivos gigantes e integração multi-canal. A arquitetura utiliza padrões de microsserviços, processamento assíncrono de eventos e observabilidade total.

## 📋 Índice

  - [Funcionalidades](https://www.google.com/search?q=%23-funcionalidades)
  - [Arquitetura](https://www.google.com/search?q=%23-arquitetura)
  - [Stack Tecnológico](https://www.google.com/search?q=%23-stack-tecnol%C3%B3gico)
  - [Pré-requisitos e Configuração](https://www.google.com/search?q=%23-pr%C3%A9-requisitos-e-configura%C3%A7%C3%A3o)
  - [Instalação e Execução](https://www.google.com/search?q=%23-instala%C3%A7%C3%A3o-e-execu%C3%A7%C3%A3o)
  - [Demonstrações (Demos)](https://www.google.com/search?q=%23-demonstra%C3%A7%C3%B5es-demos)
  - [Observabilidade e Testes](https://www.google.com/search?q=%23-observabilidade-e-testes)

-----

## 🚀 Funcionalidades

### 💬 Mensageria & Tempo Real

  - **Comunicação Híbrida:** Suporte a REST (assíncrono) e WebSocket (tempo real).
  - **Redis Pub/Sub:** Entrega instantânea de mensagens para usuários conectados sem *polling*.
  - **Roteamento Inteligente:** Despacho de mensagens para múltiplos canais (WhatsApp, Instagram, Telegram) baseado em regras de negócio.
  - **Integração Real:** Conector funcional com **Telegram Bot API**.

### 📂 Gestão de Arquivos (Large Files)

  - **Protocolo Resumable:** Upload segmentado (*Chunked*) permitindo arquivos de **2GB+**.
  - **Storage Híbrido:** Processamento temporário de blocos e composição final no **MinIO (S3)**.
  - **Assinatura Digital:** URLs de download seguras e temporárias (Presigned URLs).

### ⚙️ Gestão e Integração (Gap Analysis)

  - **Webhooks:** Registro de callbacks para sistemas externos.
  - **Presence Service:** Monitoramento de status Online/Offline (Heartbeat).
  - **User Channels:** Vínculo dinâmico de identificadores externos (telefone, @user).

### 🛡️ Resiliência e Operação

  - **Alta Disponibilidade:** Workers escaláveis horizontalmente.
  - **Zero Data Loss:** Persistência durável em Cassandra e Kafka.
  - **Observabilidade:** Dashboards métricos e Tracing distribuído.

-----

## 🏗️ Arquitetura

O sistema segue uma arquitetura orientada a eventos (EDA):

```mermaid
graph TD
    User((Usuário))
    
    subgraph "Frontend & API Layer"
        API[Frontend Service]
        WS[WebSocket Handler]
    end
    
    subgraph "Event Backbone & Storage"
        Kafka[(Apache Kafka)]
        Redis[(Redis Pub/Sub)]
        Cassandra[(Cassandra DB)]
        Cockroach[(CockroachDB Metadata)]
        MinIO[(MinIO Object Storage)]
    end
    
    subgraph "Processing & Routing"
        Worker[Router Worker (Scalable)]
    end
    
    subgraph "Connectors Layer"
        Tele[Telegram Connector]
        Meta[WhatsApp/Instagram Mock]
    end

    User -->|REST POST| API
    User <-->|WebSocket| WS
    User -->|Upload Chunks| API
    
    API -->|Produce| Kafka
    API -->|S3 Put| MinIO
    API -.->|Auth/Meta| Cockroach
    
    Kafka -->|Consume| Worker
    Worker -->|Persist| Cassandra
    Worker -->|Notify| Redis
    Worker -->|Route| Kafka
    
    Redis -->|Push| WS
    
    Kafka -->|Consume| Tele
    Tele -->|API Call| TelegramCloud[Telegram API]
```
-----

## 🛠️ Stack Tecnológico

| Categoria | Tecnologia | Uso Principal |
| :--- | :--- | :--- |
| **Linguagem** | Python 3.10+ | FastAPI, Workers, Scripts |
| **Broker** | Apache Kafka | Barramento de eventos e desacoplamento |
| **NoSQL** | Apache Cassandra | Armazenamento de alta escrita (Chat Log) |
| **SQL Distribuido** | CockroachDB | Gestão de Usuários e Metadados |
| **Cache/PubSub** | Redis | Estado de Presença e Eventos Real-Time |
| **Object Store** | MinIO | Compatível com S3 para arquivos grandes |
| **Observabilidade** | Prometheus + Grafana | Métricas e Dashboards |
| **Tracing** | Jaeger + OpenTelemetry | Rastreamento de requisições distribuídas |
| **Testes** | Locust | Teste de carga distribuído |

-----

## ⚙️ Pré-requisitos e Configuração

### 1\. Configurar Host (Para MinIO Local)

Para que os links de download funcionem no navegador, adicione esta entrada no seu arquivo `hosts` (Windows: `C:\Windows\System32\drivers\etc\hosts`):

```text
127.0.0.1 minio
```

### 2\. Configurar Token do Telegram (Opcional)

No arquivo `docker-compose.yml`, edite a variável `TELEGRAM_TOKEN` no serviço `connector_telegram` com o token obtido no @BotFather.

-----

## 🚀 Instalação e Execução

### 1\. Subir o Ambiente

```bash
docker-compose up --build -d
```

*Aguarde alguns minutos para o Cassandra e Kafka inicializarem completamente.*

### 2\. Inicializar Banco de Dados (Schema)

Execute este comando para criar todas as tabelas necessárias no Cassandra:

```bash
docker exec cassandra cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS chat4all_ks WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};
USE chat4all_ks;

-- Core
CREATE TABLE IF NOT EXISTS messages (conversation_id uuid, message_id uuid, sender_id text, content text, status text, created_at timestamp, type text, file_id text, channels list<text>, PRIMARY KEY (conversation_id, message_id)) WITH CLUSTERING ORDER BY (message_id DESC);
CREATE TABLE IF NOT EXISTS conversations (conversation_id uuid PRIMARY KEY, type text, members list<text>, metadata map<text,text>, created_at timestamp);

-- Uploads
CREATE TABLE IF NOT EXISTS file_uploads (file_id uuid PRIMARY KEY, filename text, total_size bigint, chunk_size int, total_chunks int, uploaded_chunks set<int>, status text, upload_url text, owner_id text, created_at timestamp);
CREATE TABLE IF NOT EXISTS files (file_id uuid PRIMARY KEY, owner_id text, filename text, size bigint, content_type text, minio_path text, created_at timestamp);

-- Gap Analysis
CREATE TABLE IF NOT EXISTS webhooks (user_id text, webhook_id uuid, url text, events list<text>, secret text, created_at timestamp, PRIMARY KEY (user_id, webhook_id));
CREATE TABLE IF NOT EXISTS user_channels (user_id text, channel_type text, identifier text, created_at timestamp, PRIMARY KEY (user_id, channel_type));
CREATE TABLE IF NOT EXISTS user_presence (user_id text PRIMARY KEY, status text, last_seen timestamp);
"
```

-----

## 🖥️ Demonstrações (Demos)

O projeto inclui interfaces web para facilitar a demonstração das funcionalidades complexas.

### 1\. Chat Real-Time (`demo_chat.html`)

  * Abra o arquivo no navegador.
  * Insira um Token JWT (gere via Postman `/token`) e um ID de Conversa.
  * Conecte e envie mensagens.
  * **Prova de Valor:** Recebe mensagens enviadas por outros clientes instantaneamente via WebSocket.

### 2\. Upload Gigante (`demo_upload.html`)

  * Abra no navegador.
  * Insira o Token JWT.
  * Selecione um arquivo grande (ex: 500MB).
  * **Prova de Valor:** Visualização da barra de progresso enviando *chunks* de 5MB sem travar o navegador ou o servidor.

-----

## 📊 Observabilidade e Testes

### Acessos Administrativos

  * **API Swagger:** [http://localhost:8000/docs](https://www.google.com/search?q=http://localhost:8000/docs)
  * **Grafana:** [http://localhost:3000](https://www.google.com/search?q=http://localhost:3000) (Login: `admin` / `admin`)
      * *Dashboard:* Importe o JSON fornecido para ver métricas de Upload e WS.
  * **Jaeger UI:** [http://localhost:16686](https://www.google.com/search?q=http://localhost:16686) (Tracing)
  * **MinIO Console:** [http://localhost:9001](https://www.google.com/search?q=http://localhost:9001) (Login: `minioadmin` / `minioadmin`)

### Teste de Carga (Stress Test)

Para validar a estabilidade sob pressão:

```bash
# Instalar Locust
pip install locust

# Iniciar Swarm
locust -f locustfile.py --host=http://localhost:8000
```

Acesse [http://localhost:8089](https://www.google.com/search?q=http://localhost:8089) e inicie com 50 usuários.

-----

**Autores:** Bruno Evangelista Bertoldo - Augusto Arantes Chaves - Enzo Alvarez Dias - Matheus Pereira Figueredo