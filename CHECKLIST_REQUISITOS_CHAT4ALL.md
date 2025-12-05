# Checklist de Requisitos - Chat4All v2
## Objetivo: Atender 100% dos requisitos funcionais e não funcionais

---

## 📋 2. REQUISITOS FUNCIONAIS

### 2.1 Mensageria Básica

#### ✅ Criar/Entrar em Conversas
- [] **RF-2.1.1**: Implementar `POST /v1/conversations` para criar conversas privadas (1:1)
  - Body: `{ "type": "private", "members": ["userA", "userB"], "metadata": {} }`
  - Validar que ambos os usuários existem (via metadata_service)
  - Criar registro em Cassandra ou CockroachDB com `conversation_id`, `type`, `members`, `created_at`
  - Retornar `{ "conversation_id": "<uuid>", "type": "private", ... }`

- [ ] **RF-2.1.2**: Implementar `POST /v1/conversations` para criar grupos (n membros)
  - Body: `{ "type": "group", "members": ["userA", "userB", "userC", ...], "metadata": {"name": "..."} }`
  - Validar que todos os membros existem
  - Criar registro de grupo com lista de membros
  - Retornar `conversation_id` do grupo

- [ ] **RF-2.1.3**: Implementar `GET /v1/conversations` para listar conversas do usuário autenticado
  - Filtrar por `conversation_id` onde o usuário está em `members`
  - Retornar lista com metadados (última mensagem, timestamp, etc.)

- [] **RF-2.1.4**: Criar tabela/modelo de `conversations` em Cassandra ou CockroachDB
  - Campos: `conversation_id` (PK), `type` (private/group), `members` (list), `created_at`, `metadata` (map)

#### ✅ Envio de Mensagens
- [x] **RF-2.1.5**: `POST /v1/messages` já implementado (✅ OK)
- [ ] **RF-2.1.6**: Validar que `conversation_id` existe e usuário autenticado é membro antes de enviar
- [ ] **RF-2.1.7**: Suportar envio para múltiplos destinatários em grupos (campo `to` pode ser lista)

#### ✅ Envio de Arquivos até 2GB
- [x] **RF-2.1.8**: Upload básico para MinIO já existe (✅ OK)
- [x] **RF-2.1.9**: Implementar **chunked upload resumable** (protocolo tipo tus ou S3 multipart) (⚠️ PARCIAL)
  - `POST /v1/files/initiate` → retorna `upload_url` (presigned), `file_id`, `chunk_size` - ✅ Implementado
  - `PATCH /v1/files/{file_id}/chunk` → upload de chunk individual (com offset) - ❌ Falta implementar
  - `POST /v1/files/{file_id}/complete` → finaliza upload com checksum - ❌ Falta implementar
  - Armazenar manifest de chunks no DB (metadados: `file_id`, `total_size`, `chunks[]`, `checksum`) - ⚠️ Parcial

- [ ] **RF-2.1.10**: Validar tamanho máximo de 2GB no endpoint de initiate
- [ ] **RF-2.1.11**: Implementar lógica de resume (verificar chunks já enviados e continuar)

#### ✅ Recepção em Tempo Real / Entrega Retardada
- [x] **RF-2.1.12**: Implementar **WebSocket endpoint** para clientes internos conectados (✅ OK)
  - `WS /ws` com autenticação via token - ✅ Implementado
  - Enviar mensagens em tempo real quando destinatário está online - ✅ Implementado via Redis
  - Manter conexão ativa e heartbeat - ✅ Implementado

- [ ] **RF-2.1.13**: Implementar **Presence Service** (rastreia quem está online)
  - Endpoint: `POST /v1/presence/heartbeat` (chamado periodicamente pelo cliente)
  - Armazenar em cache (Redis) ou DB: `user_id` → `last_seen`, `status` (online/offline)
  - Endpoint: `GET /v1/presence/{user_id}` para consultar status

- [x] **RF-2.1.14**: Implementar lógica de **store-and-forward** no router_worker (✅ PARCIAL)
  - Se destinatário está offline → persistir em Cassandra (✅ já faz)
  - Se destinatário está online → enviar via WebSocket (✅ implementado via Redis)
  - Quando usuário volta online, consultar mensagens pendentes e entregar - ⚠️ Falta lógica de consulta de pendentes

---

### 2.2 Controle de Envio / Entrega / Leitura

#### ✅ Estados de Mensagem
- [x] **RF-2.2.1**: Estados SENT/DELIVERED/READ já implementados (✅ OK)
- [ ] **RF-2.2.2**: Criar **tabela de histórico de estados** (não apenas campo único)
  - Tabela: `message_status_history` com campos: `message_id`, `status`, `timestamp`, `source`
  - Registrar cada transição: SENT → DELIVERED → READ

- [ ] **RF-2.2.3**: Implementar `GET /v1/messages/{message_id}/status/history`
  - Retornar array de estados com timestamps: `[{ "status": "SENT", "timestamp": "...", ... }, ...]`

- [ ] **RF-2.2.4**: Implementar **idempotência e deduplicação**
  - No `router_worker`, antes de inserir em Cassandra, verificar se `message_id` já existe
  - Usar `INSERT IF NOT EXISTS` ou `SELECT` antes de `INSERT` em Cassandra
  - Se duplicado detectado, logar e pular processamento

- [ ] **RF-2.2.5**: Aceitar `message_id` fornecido pelo cliente (UUIDv4) ou gerar se não fornecido
  - Validar formato UUID no frontend_service antes de enviar ao Kafka

- [ ] **RF-2.2.6**: Implementar confirmação de entrega/leitura solicitável pelo remetente
  - Adicionar campo opcional `request_delivery_receipt: bool` no `MessageIn`
  - Se `true`, garantir que callbacks sejam enviados quando DELIVERED/READ

---

### 2.3 Multiplataforma e Roteamento por Canal

#### ✅ Seleção de Canais
- [x] **RF-2.3.1**: Modificar `POST /v1/messages` para aceitar campo `channels` (✅ OK)
  - Body aceita: `"channels": ["whatsapp", "instagram"]` ou `"channels": ["all"]` - ✅ Schema implementado
  - Validar que canais são suportados (lista de canais disponíveis) - ⚠️ Falta validação

- [ ] **RF-2.3.2**: Modificar `router_worker` para rotear baseado em `channels` (não heurística de `@`)
  - Ler campo `channels` do payload Kafka - ⚠️ Campo existe no schema, mas roteamento ainda usa heurística
  - Se `["all"]` → enviar para todos os tópicos de connectors disponíveis
  - Se lista específica → enviar apenas para tópicos correspondentes (`whatsapp_outbound`, `instagram_outbound`, etc.)

- [ ] **RF-2.3.3**: Criar **mapeamento de usuários entre plataformas** (Metadata Service)
  - Tabela: `user_channels` com campos: `user_id`, `channel_type` (whatsapp/instagram/telegram), `channel_identifier` (phone/@handle), `is_active`
  - Endpoint: `POST /v1/users/{user_id}/channels` para vincular canais
  - Endpoint: `GET /v1/users/{user_id}/channels` para listar canais do usuário

- [ ] **RF-2.3.4**: Implementar roteamento cross-channel inteligente
  - Quando mensagem chega de WhatsApp para usuário X, verificar canais de X
  - Se X tem Instagram configurado, enviar também para Instagram
  - Permitir que usuário WhatsApp envie mensagem que chegue ao Direct do Instagram de outro usuário

- [ ] **RF-2.3.5**: Criar **registry de connectors disponíveis**
  - Arquivo/config: lista de connectors ativos e seus tópicos Kafka
  - Exemplo: `{"whatsapp": "whatsapp_outbound", "instagram": "instagram_outbound", "telegram": "telegram_outbound"}`

---

### 2.4 Persistência

#### ✅ Armazenamento de Mensagens
- [x] **RF-2.4.1**: Persistência em Cassandra já implementada (✅ OK)
- [ ] **RF-2.4.2**: Adicionar TTL configurável para mensagens antigas (opcional, conforme PDF)
  - Configurar TTL na tabela `messages` do Cassandra (ex.: 1 ano)

#### ✅ Armazenamento de Arquivos
- [x] **RF-2.4.3**: MinIO já configurado (✅ OK)
- [ ] **RF-2.4.4**: Criar tabela de metadados de arquivos em Cassandra/CockroachDB
  - Campos: `file_id`, `filename`, `content_type`, `size`, `checksum`, `chunk_manifest` (JSON), `upload_status`, `created_at`, `download_url`
  - Relacionar `file_id` com mensagens na tabela `messages`

- [ ] **RF-2.4.5**: Implementar endpoint `GET /v1/files/{file_id}` para download
  - Retornar presigned URL ou stream direto do MinIO
  - Validar permissões (usuário tem acesso à conversa que contém o arquivo)

---

### 2.5 API Pública e SDKs

#### ✅ Endpoints REST/gRPC
- [x] **RF-2.5.1**: Endpoints básicos já implementados (✅ OK)
- [ ] **RF-2.5.2**: Implementar `POST /v1/webhooks` para registro de webhooks
  - Body: `{ "url": "https://...", "events": ["message.delivered", "message.read"], "secret": "..." }`
  - Armazenar em CockroachDB: tabela `webhooks` com `user_id`, `url`, `events[]`, `secret`, `is_active`
  - Validar URL e secret antes de salvar

- [ ] **RF-2.5.3**: Implementar disparo de webhooks quando eventos ocorrem
  - No `router_worker` ou connectors, quando status muda para DELIVERED/READ:
    - Consultar webhooks registrados para o usuário remetente
    - Filtrar por eventos (`message.delivered`, `message.read`)
    - Fazer POST HTTP para cada webhook com payload: `{ "message_id": "...", "status": "...", "timestamp": "..." }`
    - Assinar payload com HMAC usando `secret` do webhook

- [ ] **RF-2.5.4**: Implementar retry exponencial para webhooks falhos
  - Se webhook falha (timeout/5xx), reenfileirar com backoff
  - Máximo de 3 tentativas

- [ ] **RF-2.5.5**: Gerar documentação OpenAPI/Swagger completa
  - FastAPI já gera `/docs`, mas adicionar:
    - Descrições detalhadas de cada endpoint
    - Exemplos de request/response
    - Códigos de erro possíveis
    - Exportar para arquivo `openapi.json` e versionar

- [ ] **RF-2.5.6**: Criar SDK Python básico
  - Classe `Chat4AllClient` com métodos: `send_message()`, `get_conversations()`, `upload_file()`, `register_webhook()`
  - Publicar em PyPI ou disponibilizar como pacote local

- [ ] **RF-2.5.7**: Criar SDK JavaScript/TypeScript básico (opcional, mas recomendado)
  - Similar ao Python, para uso em frontend web

---

### 2.6 Extensibilidade de Canais

#### ✅ Interface Padronizada para Adapters
- [ ] **RF-2.6.1**: Criar **interface/contrato formal** para connectors
  - Documentar: `connect()`, `sendMessage(dest, payload)`, `sendFile(dest, fileReference)`, `onWebhookEvent(event)`
  - Criar classe base abstrata ou protocolo (Python `Protocol` ou ABC)

- [ ] **RF-2.6.2**: Refatorar connectors existentes para seguir a interface
  - `connector_whatsapp` e `connector_instagram` devem implementar métodos padronizados
  - Padronizar formato de payload Kafka de entrada

- [ ] **RF-2.6.3**: Criar **documentação para desenvolver novos connectors**
  - README em `services/connector_template/` com:
    - Estrutura de projeto
    - Como consumir tópico Kafka
    - Como enviar callbacks de status
    - Exemplo mínimo funcional

- [ ] **RF-2.6.4**: Criar template/boilerplate de connector
  - Pasta `services/connector_template/` com código exemplo comentado
  - Dockerfile e requirements.txt de exemplo

---

## 📋 3. REQUISITOS NÃO FUNCIONAIS (NFR)

### 3.1 Escalabilidade

- [ ] **NFR-3.1.1**: Configurar **múltiplos brokers Kafka** no docker-compose
  - Adicionar `kafka-2`, `kafka-3` com `KAFKA_BROKER_ID` diferentes
  - Configurar replicação de tópicos (ex.: `replication-factor: 3`)

- [ ] **NFR-3.1.2**: Configurar **cluster Cassandra** (múltiplos nós)
  - Adicionar `cassandra-2`, `cassandra-3` no docker-compose
  - Configurar seeds e replication factor

- [ ] **NFR-3.1.3**: Configurar **múltiplas instâncias de workers** (horizontal scaling)
  - No docker-compose, usar `deploy.replicas: 3` ou múltiplos serviços `router_worker_1`, `router_worker_2`, etc.
  - Garantir que particionamento Kafka distribui carga entre workers

- [ ] **NFR-3.1.4**: Implementar **sharding dinâmico por conversation_id**
  - Particionar mensagens por `conversation_id` hash
  - Documentar estratégia de re-sharding sem downtime (se necessário)

- [ ] **NFR-3.1.5**: Criar **testes de carga** documentados
  - Usar `locustfile.py` existente ou criar scripts K6/Gatling
  - Testar: 100k mensagens/min (ajustar conforme escopo do curso)
  - Documentar resultados: throughput alcançado, latência p50/p95/p99

- [ ] **NFR-3.1.6**: Demonstrar **escalabilidade horizontal** em execução
  - Adicionar nós em tempo de execução e mostrar aumento de capacidade
  - Documentar com screenshots/métricas

---

### 3.2 Alta Disponibilidade / Tolerância a Falhas

- [ ] **NFR-3.2.1**: Configurar **replicação Kafka** (já mencionado em 3.1.1)
  - Tópicos com `replication-factor >= 2`
  - Configurar `min.insync.replicas`

- [ ] **NFR-3.2.2**: Configurar **replicação Cassandra** (já mencionado em 3.1.2)
  - Replication factor >= 3 para keyspace `chat4all_ks`
  - Configurar consistency level adequado (QUORUM para leitura/escrita)

- [ ] **NFR-3.2.3**: Implementar **health checks robustos** em todos os serviços
  - Endpoint `/health` que verifica dependências (Kafka, DB, MinIO)
  - Retornar `200` apenas se todas as dependências estão OK
  - Usar em `docker-compose` com `healthcheck`

- [ ] **NFR-3.2.4**: Implementar **circuit breaker** nos connectors
  - Se connector externo (WhatsApp/Instagram API) falha repetidamente, abrir circuit
  - Parar de enviar mensagens temporariamente e retomar após timeout
  - Usar biblioteca como `circuitbreaker` (Python)

- [ ] **NFR-3.2.5**: Implementar **retry com backoff exponencial** em pontos críticos
  - No `router_worker`, se falha ao salvar em Cassandra, retry com backoff
  - No envio de webhooks, retry com backoff (já mencionado em RF-2.5.4)

- [ ] **NFR-3.2.6**: Criar **testes de failover** documentados
  - Cenário: derrubar nó Kafka, nó Cassandra, worker
  - Demonstrar que sistema continua funcionando (com degradação aceitável)
  - Documentar perda de mensagens (se houver) e tempo de recuperação

- [ ] **NFR-3.2.7**: Configurar **monitoramento de SLA** (99.95%)
  - Alertas no Prometheus/Alertmanager quando uptime < 99.95%
  - Dashboard no Grafana mostrando uptime por serviço

---

### 3.3 Consistência & Garantias de Entrega

- [ ] **NFR-3.3.1**: Implementar **deduplicação robusta** (já mencionado em RF-2.2.4)
  - Usar `message_id` como chave única em Cassandra (com `IF NOT EXISTS`)
  - Ou usar tabela separada `processed_messages` para tracking

- [ ] **NFR-3.3.2**: Garantir **ordem causal por conversa**
  - ✅ Já implementado via `key=str(chat_id)` no Kafka (OK)
  - Validar que múltiplos workers respeitam ordem (usar mesmo consumer group)

- [ ] **NFR-3.3.3**: Documentar estratégia de **at-least-once vs effectively-once**
  - Documentar que sistema garante at-least-once com deduplicação
  - Explicar trade-offs e quando effectively-once seria necessário

- [ ] **NFR-3.3.4**: Implementar **idempotent writes** em Cassandra
  - Usar `INSERT ... IF NOT EXISTS` ou `UPDATE` condicional
  - Garantir que múltiplas tentativas não criam duplicatas

---

### 3.4 Latência

- [ ] **NFR-3.4.1**: Medir e documentar **latência end-to-end**
  - Cliente → Frontend → Kafka → Worker → DB
  - Objetivo: < 200ms para caminhos internos
  - Usar tracing distribuído (OpenTelemetry) para identificar gargalos

- [ ] **NFR-3.4.2**: Otimizar queries Cassandra
  - Criar índices secundários se necessário
  - Evitar queries que fazem full scan

- [ ] **NFR-3.4.3**: Implementar **caching** onde apropriado
  - Cache de presença de usuários (Redis)
  - Cache de metadados de conversas (opcional)

---

### 3.5 Throughput

- [ ] **NFR-3.5.1**: Projetar para **milhares de mensagens/s por nó**
  - Testar throughput de um worker isolado
  - Documentar capacidade máxima por instância

- [ ] **NFR-3.5.2**: Implementar **particionamento eficiente** no Kafka
  - Aumentar número de partições do tópico `chat_messages` conforme necessidade
  - Garantir que particionamento por `conversation_id` distribui carga uniformemente

- [ ] **NFR-3.5.3**: Otimizar **batch processing** no worker
  - Processar múltiplas mensagens em batch quando possível
  - Configurar `batch_size` no Kafka consumer

---

### 3.6 Armazenamento de Arquivos (2GB, Chunked/Resume)

- [ ] **NFR-3.6.1**: Implementar **chunked upload** (já mencionado em RF-2.1.9)
  - Protocolo resumable (tus ou S3 multipart)
  - Suportar arquivos até 2GB

- [ ] **NFR-3.6.2**: Implementar **resume de upload** interrompido
  - Endpoint `GET /v1/files/{file_id}/status` retorna chunks já enviados
  - Cliente pode continuar de onde parou

- [ ] **NFR-3.6.3**: Validar **checksum** após upload completo
  - Calcular MD5/SHA256 do arquivo completo
  - Comparar com checksum fornecido pelo cliente
  - Rejeitar se não corresponder

- [ ] **NFR-3.6.4**: Implementar **estratégia de replicação** no MinIO (opcional)
  - Configurar MinIO em modo distribuído com múltiplos nós
  - Ou documentar que MinIO é single-node para PoC

---

### 3.7 Observabilidade

#### ✅ Prometheus & Grafana
- [x] **NFR-3.7.1**: Prometheus e Grafana já configurados (✅ OK)
- [ ] **NFR-3.7.2**: Adicionar **métricas customizadas** em todos os serviços
  - `frontend_service`: já tem métricas HTTP (✅ OK)
  - `router_worker`: já tem `MESSAGES_PROCESSED` (✅ OK)
  - Adicionar: latência de processamento, taxa de erro por connector, utilização de disco

- [ ] **NFR-3.7.3**: Criar **dashboards Grafana** completos
  - Dashboard: Throughput de mensagens (msg/s)
  - Dashboard: Latência de entrega (p50/p95/p99)
  - Dashboard: Taxa de erro por serviço
  - Dashboard: Utilização de recursos (CPU, memória, disco)
  - Exportar dashboards como JSON e versionar

#### ✅ Tracing Distribuído
- [ ] **NFR-3.7.4**: Implementar **OpenTelemetry** em todos os serviços
  - Instrumentar `frontend_service`, `router_worker`, connectors
  - Criar spans para cada operação crítica (envio de mensagem, processamento, entrega)
  - Configurar exportador para Jaeger ou Zipkin

- [ ] **NFR-3.7.5**: Adicionar **trace_id** e **span_id** nos logs
  - Correlacionar logs com traces
  - Usar formato estruturado (JSON) nos logs

#### ✅ Logs Estruturados
- [ ] **NFR-3.7.6**: Configurar **stack de logging centralizado** (ELK/EFK)
  - Adicionar Elasticsearch e Logstash/Fluentd no docker-compose
  - Ou usar Loki (mais leve) como alternativa
  - Configurar todos os serviços para enviar logs para stack centralizada

- [ ] **NFR-3.7.7**: Padronizar **formato de logs** (JSON estruturado)
  - Todos os serviços devem logar em JSON com campos: `timestamp`, `level`, `service`, `message`, `trace_id`, `message_id`

- [ ] **NFR-3.7.8**: Criar **dashboards de logs** no Grafana/Kibana
  - Visualizar logs por serviço, nível, trace_id
  - Filtrar por erro, warning, etc.

#### ✅ Métricas Chave
- [ ] **NFR-3.7.9**: Implementar métricas específicas mencionadas no PDF:
  - ✅ Mensagens/s (já implementado parcialmente)
  - [ ] Latência de entrega (adicionar histograma no worker)
  - [ ] Taxa de erro connectors (adicionar counter por connector)
  - [ ] Utilização de disco (usar node_exporter)
  - [ ] Throughput de object storage (adicionar métricas no MinIO ou proxy)

---

### 3.9 Extensibilidade / Manutenibilidade

- [x] **NFR-3.9.1**: Versionamento de API já implementado (`/v1/...`) (✅ OK)
- [ ] **NFR-3.9.2**: Criar **interface clean para adapters** (já mencionado em RF-2.6.1)
- [ ] **NFR-3.9.3**: Documentar **arquitetura** em README.md principal
  - Diagrama de componentes
  - Fluxo de mensagens (cliente → API → Kafka → Worker → Connectors)
  - Decisões técnicas (por que Kafka, Cassandra, etc.)

- [ ] **NFR-3.9.4**: Criar **guia de desenvolvimento** (DEVELOPMENT.md)
  - Como rodar localmente
  - Como adicionar novo connector
  - Como adicionar novo endpoint
  - Convenções de código

- [ ] **NFR-3.9.5**: Adicionar **testes unitários** para componentes críticos
  - Testes para `router_worker` (lógica de roteamento)
  - Testes para `frontend_service` (validações, autenticação)
  - Usar pytest ou similar

- [ ] **NFR-3.9.6**: Adicionar **testes de integração** end-to-end
  - Teste completo: criar conversa → enviar mensagem → verificar entrega → verificar status READ
  - Usar pytest com fixtures para subir serviços via docker-compose

---

## 📋 4. ARQUITETURA PROPOSTA (Validação)

### Componentes Principais

- [x] **ARQ-1**: API Gateway / Ingress (stateless) - ✅ FastAPI stateless (OK)
- [x] **ARQ-2**: Frontend Service (Stateless) - ✅ Implementado (OK)
- [x] **ARQ-3**: Message Broker (Kafka) - ✅ Implementado (OK)
- [x] **ARQ-4**: Workers / Router Services - ✅ Implementado (OK)
- [x] **ARQ-5**: Connectors / Channel Adapters - ✅ Implementado (2 mocks) (OK)
- [x] **ARQ-6**: Metadata DB (CockroachDB) - ✅ Implementado (OK)
- [x] **ARQ-7**: Message Store (Cassandra) - ✅ Implementado (OK)
- [x] **ARQ-8**: Object Storage (MinIO) - ✅ Implementado (OK)
- [x] **ARQ-9**: Notification / Push Service - ✅ Implementado (WebSocket + Redis)
- [ ] **ARQ-10**: Presence Service - ⚠️ Não implementado (falta endpoints de heartbeat)
- [x] **ARQ-11**: Admin & Monitoring (Prometheus/Grafana) - ✅ Implementado (OK)

---

## 📋 5. DECISÕES TÉCNICAS (Validação)

- [x] **TEC-1**: Apache Kafka como backbone - ✅ OK
- [x] **TEC-2**: Particionamento por conversation_id - ✅ OK (via key)
- [x] **TEC-3**: MongoDB/Cassandra para mensagens - ✅ Cassandra OK
- [ ] **TEC-4**: Estratégia de replicação MinIO - ⚠️ Single-node apenas
- [x] **TEC-5**: Connectors como serviços independentes - ✅ OK
- [ ] **TEC-6**: Idempotência e deduplicação - ⚠️ Parcial (faltam checagens)
- [x] **TEC-7**: Observability (Prometheus) - ✅ Parcial (faltam tracing e logs centralizados)

---

## 📋 6. API PÚBLICA (Validação de Endpoints)

### 6.1 Autenticação
- [x] **API-1**: `POST /auth/token` - ✅ Implementado como `/token` (OK)

### 6.2 Conversas
- [ ] **API-2**: `POST /v1/conversations` - ⚠️ Não implementado
- [x] **API-3**: `GET /v1/conversations/{conversation_id}/messages` - ✅ Implementado (OK)

### 6.3 Enviar Mensagem
- [x] **API-4**: `POST /v1/messages` - ✅ Implementado (OK)
- [ ] **API-5**: Suportar campo `channels` no body - ⚠️ Não implementado

### 6.4 Upload de Arquivo (Resumable)
- [ ] **API-6**: `POST /v1/files/initiate` - ⚠️ Não implementado
- [ ] **API-7**: `PATCH/PUT` upload chunks - ⚠️ Não implementado
- [ ] **API-8**: `POST /v1/files/complete` - ⚠️ Não implementado
- [x] **API-9**: Upload simples existe - ✅ Mas não é resumable

### 6.5 Delivery / Read Callbacks (Webhooks)
- [ ] **API-10**: `POST /v1/webhooks` - ⚠️ Não implementado
- [ ] **API-11**: Callback payloads com message_id e status - ⚠️ Parcial (callbacks existem, mas não são configuráveis)

---

## 📋 7. REQUISITOS DE TESTE / VALIDAÇÃO

- [ ] **TEST-1**: **Teste de carga** documentado
  - Usar k6, Gatling ou Locust
  - Alvo: 100k msgs/min (ajustar conforme escopo)
  - Documentar resultados: throughput, latência, erros

- [ ] **TEST-2**: **Testes de falhas controladas**
  - Derrubar nó Kafka → demonstrar failover
  - Derrubar nó Cassandra → demonstrar recuperação
  - Derrubar worker → demonstrar rebalancing
  - Documentar perda de mensagens (se houver)

- [ ] **TEST-3**: **Teste cross-channel**
  - Enviar de WhatsApp para Instagram Direct
  - Demonstrar transição e callbacks
  - Documentar com screenshots/logs

- [ ] **TEST-4**: **Teste de upload/download de arquivos grandes**
  - Enviar arquivo ~1.8GB
  - Demonstrar chunking/resume
  - Validar checksum

- [ ] **TEST-5**: **Teste de escalabilidade horizontal**
  - Adicionar nós em tempo de execução
  - Mostrar aumento de capacidade
  - Documentar com métricas

- [ ] **TEST-6**: **Demonstração de observabilidade**
  - Dashboards mostrando métricas
  - Tracing de fluxo de mensagens
  - Logs correlacionados

---

## 📋 8. ENTREGÁVEIS FINAIS

- [x] **ENT-1**: Código-fonte com README - ✅ OK
- [ ] **ENT-2**: Scripts de deploy (K8s manifests ou docker-compose) - ⚠️ docker-compose existe, mas falta K8s (opcional)
- [ ] **ENT-3**: Documentação da API (OpenAPI) - ⚠️ FastAPI gera, mas falta exportar e versionar
- [ ] **ENT-4**: Relatório técnico (máx 15 páginas) - ⚠️ Não verificado
- [ ] **ENT-5**: Script/instruções para demo - ⚠️ Não verificado
  - Cenário básico (chat interno)
  - Cenário cross-platform (WhatsApp → Instagram)
  - Cenário de stress
- [ ] **ENT-6**: Dashboards e logs de execução - ⚠️ Dashboards Grafana precisam ser criados
- [ ] **ENT-7**: Vídeo curto da demonstração (opcional) - ⚠️ Não verificado

---

## 📊 RESUMO DE STATUS

### Requisitos Funcionais
- ✅ **Implementados**: ~40%
- ⚠️ **Parciais**: ~35%
- ❌ **Não implementados**: ~25%

### Requisitos Não Funcionais
- ✅ **Implementados**: ~30%
- ⚠️ **Parciais**: ~40%
- ❌ **Não implementados**: ~30%

### Priorização Sugerida

#### 🔴 **ALTA PRIORIDADE** (Críticos para funcionalidade básica)
1. RF-2.1.1 a RF-2.1.3: Criar/gerenciar conversas
2. RF-2.2.4: Idempotência e deduplicação
3. RF-2.3.1 a RF-2.3.2: Seleção de canais pelo cliente
4. RF-2.1.9 a RF-2.1.11: Chunked upload resumable (2GB)
5. RF-2.5.2 a RF-2.5.4: Webhooks configuráveis

#### 🟡 **MÉDIA PRIORIDADE** (Importantes para completude)
6. RF-2.1.12 a RF-2.1.14: WebSocket e Presence Service
7. RF-2.2.2 a RF-2.2.3: Histórico de estados
8. RF-2.3.3 a RF-2.3.4: Mapeamento de usuários entre plataformas
9. NFR-3.7.4: OpenTelemetry tracing
10. NFR-3.7.6: Logs centralizados (ELK/Loki)

#### 🟢 **BAIXA PRIORIDADE** (Melhorias e polish)
11. RF-2.5.6 a RF-2.5.7: SDKs Python/JS
12. RF-2.6.1 a RF-2.6.4: Interface formal para connectors
13. NFR-3.1.1 a NFR-3.1.3: Múltiplos nós (escalabilidade real)
14. NFR-3.2.1 a NFR-3.2.7: Alta disponibilidade completa
15. TEST-1 a TEST-6: Testes de validação documentados

---

## 📝 NOTAS FINAIS

- Este checklist é baseado na análise do código atual e do documento `chat4all v2.pdf`
- Itens marcados com ✅ já estão implementados
- Itens marcados com ⚠️ estão parcialmente implementados
- Itens marcados com ❌ não estão implementados
- Priorize os itens de ALTA PRIORIDADE para atingir funcionalidade básica completa
- Use este checklist como guia de desenvolvimento e validação final

---

**Última atualização**: Baseado na análise do código em `frontend_service/`, `services/`, `docker-compose.yml` e requisitos do PDF.



