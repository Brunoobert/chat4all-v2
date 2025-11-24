# Chat4All - Sistema de Mensageria Distribuída

Sistema de chat distribuído baseado em microserviços, utilizando Kafka para mensageria assíncrona, Cassandra para armazenamento de mensagens e CockroachDB para metadados.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Serviços](#serviços)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e Execução](#instalação-e-execução)
- [Fluxo de Mensagens](#fluxo-de-mensagens)
- [Endpoints da API](#endpoints-da-api)
- [Configuração](#configuração)
- [Desenvolvimento](#desenvolvimento)
- [Troubleshooting](#troubleshooting)

## 🎯 Visão Geral

O Chat4All é uma aplicação de mensageria distribuída que implementa uma arquitetura de microserviços para processamento assíncrono de mensagens. O sistema foi projetado para ser escalável, resiliente e seguir boas práticas de arquitetura distribuída.

### Características Principais

- **Arquitetura de Microserviços**: Separação clara de responsabilidades entre serviços
- **Mensageria Assíncrona**: Utilização do Apache Kafka para processamento de mensagens
- **Armazenamento Distribuído**: 
  - Cassandra para armazenamento de mensagens (alta performance de escrita)
  - CockroachDB para metadados (consistência transacional)
- **Autenticação JWT**: Sistema de autenticação baseado em tokens
- **Containerização**: Todos os serviços rodam em containers Docker

## 🏗️ Arquitetura

```
┌─────────────┐
│   Cliente   │
└──────┬──────┘
       │ HTTP/REST
       ▼
┌─────────────────────┐
│  Frontend Service   │ ◄─── FastAPI (Porta 8000)
│  (API Gateway)      │
└──────┬──────────────┘
       │
       │ Kafka Producer
       ▼
┌─────────────────────┐
│   Apache Kafka      │ ◄─── Message Broker
│   (Topic: chat_     │
│    messages)        │
└──────┬──────────────┘
       │
       │ Kafka Consumer
       ▼
┌─────────────────────┐
│  Router Worker      │ ◄─── Background Worker
│  (Consumer)         │
└──────┬──────────────┘
       │
       │ INSERT
       ▼
┌─────────────────────┐
│     Cassandra       │ ◄─── Message Store (Porta 9042)
│  (chat4all_ks)      │
└─────────────────────┘

┌─────────────────────┐
│ Metadata Service    │ ◄─── FastAPI (Porta 8001)
│  (User Management)  │
└──────┬──────────────┘
       │
       │ SQL
       ▼
┌─────────────────────┐
│   CockroachDB       │ ◄─── Metadata DB (Porta 26257)
│   (Users, Chats)    │
└─────────────────────┘
```

## 🛠️ Tecnologias

### Backend
- **Python 3.10/3.11**: Linguagem principal
- **FastAPI**: Framework web para APIs REST
- **Kafka-Python**: Cliente Python para Apache Kafka
- **Cassandra Driver**: Cliente para Apache Cassandra
- **SQLAlchemy**: ORM para CockroachDB
- **Pydantic**: Validação de dados e schemas
- **JWT**: Autenticação baseada em tokens

### Infraestrutura
- **Docker & Docker Compose**: Containerização e orquestração
- **Apache Kafka 7.3.0**: Message broker
- **Zookeeper**: Coordenação do Kafka
- **Apache Cassandra**: Banco de dados NoSQL para mensagens
- **CockroachDB**: Banco de dados SQL distribuído para metadados

## 📁 Estrutura do Projeto

```
Chat4All/
├── docker-compose.yml          # Orquestração de todos os serviços
├── requirements.txt             # Dependências Python globais
│
├── frontend_service/            # Serviço principal de API
│   ├── app/
│   │   ├── main.py             # Endpoints FastAPI
│   │   ├── producer.py         # Cliente Kafka Producer
│   │   ├── config.py           # Configurações
│   │   ├── schemas.py          # Modelos Pydantic
│   │   ├── security.py         # Autenticação JWT
│   │   └── db.py               # Acesso a dados (mock)
│   ├── Dockerfile
│   └── requirements.txt
│
├── services/
│   ├── router_worker/           # Worker que consome do Kafka
│   │   ├── worker.py           # Consumer e processamento
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── metadata_service/        # Serviço de metadados
│       ├── app/
│       │   ├── main.py         # Endpoints de usuários
│       │   ├── models.py       # Modelos SQLAlchemy
│       │   ├── schemas.py      # Schemas Pydantic
│       │   ├── database.py     # Configuração DB
│       │   └── security.py     # Hash de senhas
│       ├── Dockerfile
│       └── requirements.txt
│
└── client-python/               # Scripts de teste
    ├── test_producer.py
    └── test_consumer.py
```

## 🔧 Serviços

### 1. Frontend Service (Porta 8000)
**Responsabilidades:**
- Receber requisições HTTP de clientes
- Autenticar usuários via JWT
- Validar mensagens recebidas
- Enviar mensagens para o Kafka
- Consultar histórico de mensagens no Cassandra

**Endpoints principais:**
- `POST /token` - Autenticação
- `POST /v1/messages` - Enviar mensagem
- `GET /v1/conversations/{id}/messages` - Histórico
- `GET /health` - Health check

### 2. Router Worker
**Responsabilidades:**
- Consumir mensagens do tópico Kafka `chat_messages`
- Atualizar status das mensagens (SENT → DELIVERED)
- Persistir mensagens no Cassandra
- Processamento assíncrono em background

### 3. Metadata Service (Porta 8001)
**Responsabilidades:**
- Gerenciar usuários (CRUD)
- Gerenciar chats e conversas
- Gerenciar permissões
- Armazenar metadados no CockroachDB

**Endpoints principais:**
- `POST /v1/users` - Criar usuário
- `GET /health` - Health check

### 4. Infraestrutura

#### Kafka (Portas 9092, 29092)
- Broker de mensageria
- Tópico: `chat_messages`
- Particionamento por `chat_id` (chave da mensagem)

#### Cassandra (Porta 9042)
- Keyspace: `chat4all_ks`
- Tabela: `messages`
- Armazenamento de mensagens com alta performance de escrita

#### CockroachDB (Portas 26257, 8080)
- Banco de dados para metadados
- Tabela: `users`
- UI Admin disponível em `http://localhost:8080`

## 📦 Pré-requisitos

- **Docker** (versão 20.10 ou superior)
- **Docker Compose** (versão 2.0 ou superior)
- **Python 3.10+** (para desenvolvimento local, opcional)
- **Git** (para clonar o repositório)

## 🚀 Instalação e Execução

### 1. Clone o repositório

```bash
git clone <repository-url>
cd Chat4All
```

### 2. Inicie todos os serviços

```bash
docker-compose up -d
```

Este comando irá:
- Baixar as imagens necessárias
- Criar a rede Docker `chat4all_net`
- Iniciar Zookeeper, Kafka, Cassandra e CockroachDB
- Construir e iniciar os serviços Python

### 3. Verifique o status dos serviços

```bash
docker-compose ps
```

### 4. Visualize os logs

```bash
# Todos os serviços
docker-compose logs -f

# Serviço específico
docker-compose logs -f frontend_service
docker-compose logs -f router_worker
```

### 5. Pare os serviços

```bash
docker-compose down
```

Para remover também os volumes (dados persistentes):

```bash
docker-compose down -v
```

## 📨 Fluxo de Mensagens

### Fluxo Completo

1. **Cliente → Frontend Service**
   - Cliente faz POST em `/v1/messages` com autenticação JWT
   - Frontend Service valida o token e os dados da mensagem

2. **Frontend Service → Kafka**
   - Mensagem é enriquecida com:
     - `message_id` (UUID)
     - `sender_id` (do token JWT)
     - `timestamp_utc`
     - `status: "SENT"`
     - `type: "chat_message"`
   - Mensagem é enviada para o tópico `chat_messages` com `chat_id` como chave

3. **Kafka → Router Worker**
   - Worker consome mensagens do tópico
   - Atualiza status de `SENT` para `DELIVERED`

4. **Router Worker → Cassandra**
   - Mensagem é persistida na tabela `messages`
   - Campos: `conversation_id`, `message_id`, `sender_id`, `content`, `created_at`, `status`

### Diagrama de Sequência

```
Cliente          Frontend Service    Kafka          Router Worker    Cassandra
  │                    │               │                  │              │
  │──POST /messages───>│               │                  │              │
  │                    │               │                  │              │
  │                    │──produce()───>│                  │              │
  │                    │               │                  │              │
  │<──202 Accepted─────│               │                  │              │
  │                    │               │                  │              │
  │                    │               │──consume()──────>│              │
  │                    │               │                  │              │
  │                    │               │                  │──INSERT──────>│
  │                    │               │                  │              │
```

## 🔌 Endpoints da API

### Frontend Service (http://localhost:8000)

#### Autenticação

```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=bruno&password=test
```

**Resposta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Enviar Mensagem

```http
POST /v1/messages
Authorization: Bearer <token>
Content-Type: application/json

{
  "chat_id": "550e8400-e29b-41d4-a716-446655440000",
  "content": "Olá, esta é uma mensagem de teste"
}
```

**Resposta:**
```json
{
  "status": "accepted",
  "message_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

#### Obter Histórico

```http
GET /v1/conversations/{conversation_id}/messages
Authorization: Bearer <token>
```

**Resposta:**
```json
[
  {
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "message_id": "123e4567-e89b-12d3-a456-426614174000",
    "sender_id": "bruno",
    "content": "Olá, esta é uma mensagem de teste",
    "created_at": "2024-01-15T10:30:00Z",
    "status": "DELIVERED"
  }
]
```

#### Health Check

```http
GET /health
```

### Metadata Service (http://localhost:8001)

#### Criar Usuário

```http
POST /v1/users
Content-Type: application/json

{
  "username": "novo_usuario",
  "email": "usuario@example.com",
  "password": "senha_segura"
}
```

## ⚙️ Configuração

### Variáveis de Ambiente

#### Frontend Service
- `KAFKA_BOOTSTRAP_SERVER`: Endereço do Kafka (padrão: `kafka:9092` no Docker)
- `KAFKA_TOPIC_CHAT_MESSAGES`: Nome do tópico (padrão: `chat_messages`)
- `SECRET_KEY`: Chave secreta para JWT (gerada automaticamente)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Tempo de expiração do token (padrão: 30)
- `CASSANDRA_HOSTS`: Hosts do Cassandra (padrão: `cassandra`)

#### Router Worker
- `KAFKA_BROKER_URL`: URL do Kafka (padrão: `kafka:9092`)
- `KAFKA_TOPIC`: Nome do tópico (padrão: `chat_messages`)
- `CASSANDRA_HOSTS`: Hosts do Cassandra (padrão: `cassandra`)
- `CASSANDRA_KEYSPACE`: Keyspace do Cassandra (padrão: `chat4all_ks`)

#### Metadata Service
- `DATABASE_URL`: URL de conexão do CockroachDB

### Configuração do Kafka

O Kafka está configurado com dois listeners:
- **Interno (Docker)**: `kafka:9092` - Para comunicação entre containers
- **Externo (Host)**: `localhost:29092` - Para acesso do host local

### Inicialização do Cassandra

Antes de usar o Cassandra, é necessário criar o keyspace e a tabela:

```sql
-- Conectar ao Cassandra
docker exec -it cassandra cqlsh

-- Criar keyspace
CREATE KEYSPACE IF NOT EXISTS chat4all_ks
WITH REPLICATION = {
  'class': 'SimpleStrategy',
  'replication_factor': 1
};

-- Usar o keyspace
USE chat4all_ks;

-- Criar tabela de mensagens
CREATE TABLE IF NOT EXISTS messages (
    conversation_id UUID,
    message_id UUID,
    sender_id TEXT,
    content TEXT,
    created_at TIMESTAMP,
    status TEXT,
    PRIMARY KEY (conversation_id, message_id)
);
```

## 💻 Desenvolvimento

### Executando Localmente (sem Docker)

1. **Instale as dependências:**

```bash
# Frontend Service
cd frontend_service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Router Worker
cd ../services/router_worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Inicie apenas a infraestrutura:**

```bash
docker-compose up -d zookeeper kafka cassandra cockroachdb
```

3. **Execute os serviços localmente:**

```bash
# Terminal 1 - Frontend Service
cd frontend_service
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Router Worker
cd services/router_worker
python worker.py
```

### Testando com Clientes Python

O projeto inclui scripts de teste em `client-python/`:

```bash
# Testar produtor
python client-python/test_producer.py

# Testar consumidor
python client-python/test_consumer.py
```

## 🐛 Troubleshooting

### Problemas Comuns

#### 1. Kafka não está acessível

**Sintoma:** Erro `NoBrokersAvailable`

**Solução:**
- Verifique se o Kafka está rodando: `docker-compose ps`
- Verifique os logs: `docker-compose logs kafka`
- Aguarde alguns segundos após iniciar (Kafka demora para inicializar)

#### 2. Frontend Service não consegue conectar ao Kafka

**Sintoma:** Erro de conexão no startup

**Solução:**
- Verifique a variável `KAFKA_BOOTSTRAP_SERVER` no docker-compose
- Dentro do container, deve ser `kafka:9092`
- Fora do container, use `localhost:29092`

#### 3. Cassandra não está respondendo

**Sintoma:** Erro de conexão ao Cassandra

**Solução:**
- Verifique se o keyspace foi criado
- Verifique os logs: `docker-compose logs cassandra`
- Aguarde o healthcheck passar antes de iniciar serviços dependentes

#### 4. Mensagens não estão sendo processadas

**Sintoma:** Mensagens enviadas mas não aparecem no Cassandra

**Solução:**
- Verifique se o Router Worker está rodando: `docker-compose ps router_worker`
- Verifique os logs do worker: `docker-compose logs -f router_worker`
- Verifique se o tópico existe no Kafka

#### 5. Erro de autenticação JWT

**Sintoma:** `401 Unauthorized`

**Solução:**
- Verifique se está enviando o token no header: `Authorization: Bearer <token>`
- Verifique se o token não expirou (padrão: 30 minutos)
- Faça login novamente em `/token`

### Comandos Úteis

```bash
# Ver logs de todos os serviços
docker-compose logs -f

# Reiniciar um serviço específico
docker-compose restart frontend_service

# Reconstruir imagens após mudanças no código
docker-compose build --no-cache frontend_service

# Limpar tudo e começar do zero
docker-compose down -v
docker-compose up -d --build

# Verificar conectividade entre containers
docker exec -it frontend_service_c ping kafka
docker exec -it router_worker_c ping cassandra

# Acessar shell do container
docker exec -it frontend_service_c /bin/bash
```

## 📝 Notas Importantes

### Status das Mensagens

O sistema implementa um fluxo de status:
- **SENT**: Mensagem enviada para o Kafka (definido pelo Frontend Service)
- **DELIVERED**: Mensagem processada e salva no Cassandra (definido pelo Router Worker)

### Particionamento no Kafka

As mensagens são particionadas por `chat_id` (chave da mensagem), garantindo que mensagens do mesmo chat sejam processadas na ordem.

### Persistência de Dados

Os dados são persistidos em volumes Docker:
- `kafka_data`: Dados do Kafka
- `cassandra_data`: Dados do Cassandra
- `cockroachdb_data`: Dados do CockroachDB
- `zookeeper_data`: Dados do Zookeeper

Para limpar todos os dados: `docker-compose down -v`

## 🔒 Segurança

- **Autenticação**: JWT tokens com expiração configurável
- **Senhas**: Hash com bcrypt (no Metadata Service)
- **Rede**: Serviços isolados na rede Docker `chat4all_net`
- **Produção**: Ajustar configurações de segurança antes de deploy em produção

## 📚 Próximos Passos

- [ ] Implementar healthchecks mais robustos
- [ ] Adicionar métricas e monitoramento
- [ ] Implementar retry logic no produtor Kafka
- [ ] Adicionar testes automatizados
- [ ] Implementar rate limiting
- [ ] Adicionar documentação Swagger/OpenAPI completa
- [ ] Implementar sistema de notificações em tempo real
- [ ] Adicionar suporte a múltiplos tipos de mensagem

## 📄 Licença

[Adicione informações de licença aqui]

## 👥 Contribuidores

[Adicione informações de contribuidores aqui]

---

**Última atualização:** Janeiro 2024


