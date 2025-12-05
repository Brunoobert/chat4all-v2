# Requisitos Faltantes Mais Importantes - Chat4All v2

## 📊 Análise Atualizada do Projeto

Baseado na análise do código atual e comparação com o PDF `chat4all v2.pdf`, este documento lista os **requisitos mais críticos que ainda faltam** para atingir 100% de conformidade.

---

## 🔴 **CRÍTICOS - ALTA PRIORIDADE** (Bloqueiam funcionalidade básica)

### 1. **Gestão de Conversas** (RF-2.1.1 a RF-2.1.4)
**Status**: ❌ **NÃO IMPLEMENTADO**

**O que falta:**
- `POST /v1/conversations` para criar conversas privadas e grupos
- `GET /v1/conversations` para listar conversas do usuário
- Tabela/modelo de `conversations` em Cassandra ou CockroachDB
- Validação de membros antes de enviar mensagens

**Impacto**: Sem isso, não é possível criar conversas formalmente. O sistema atual assume que `conversation_id` já existe.

**Implementação sugerida:**
```python
# Em frontend_service/app/main.py
@app.post("/v1/conversations", response_model=ConversationOut)
async def create_conversation(
    conv: ConversationCreate, 
    current_user: User = Depends(get_current_user)
):
    # Validar membros via metadata_service
    # Criar registro em Cassandra/CockroachDB
    # Retornar conversation_id
```

**Prioridade**: 🔴 **CRÍTICA** - Bloqueia funcionalidade core

---

### 2. **Idempotência e Deduplicação** (RF-2.2.4, NFR-3.3.1)
**Status**: ⚠️ **PARCIAL** - Falta implementação robusta

**O que falta:**
- Verificação de `message_id` duplicado antes de inserir em Cassandra
- Uso de `INSERT IF NOT EXISTS` ou tabela de tracking `processed_messages`
- Validação de UUID no frontend antes de enviar ao Kafka

**Impacto**: Mensagens podem ser duplicadas em caso de retry ou falhas.

**Implementação sugerida:**
```python
# Em services/router_worker/worker.py
# Antes de INSERT, verificar:
select_stmt = session.prepare("SELECT message_id FROM messages WHERE message_id = ?")
existing = session.execute(select_stmt, (msg_id,)).one()
if existing:
    logger.warning(f"Duplicate message_id detected: {msg_id}")
    return  # Pular processamento
```

**Prioridade**: 🔴 **CRÍTICA** - Requisito de consistência

---

### 3. **Chunked Upload Resumable até 2GB** (RF-2.1.9 a RF-2.1.11, NFR-3.6.1 a NFR-3.6.3)
**Status**: ⚠️ **PARCIAL** - Endpoint `/v1/files/initiate` existe, mas falta completar

**O que falta:**
- `PATCH /v1/files/{file_id}/chunk` para upload de chunks individuais
- `POST /v1/files/{file_id}/complete` para finalizar com checksum
- `GET /v1/files/{file_id}/status` para verificar progresso e permitir resume
- Validação de checksum após upload completo
- Tabela de metadados de arquivos com manifest de chunks

**Impacto**: Não é possível enviar arquivos grandes (2GB) de forma confiável.

**Implementação sugerida:**
```python
# Em frontend_service/app/main.py
@app.patch("/v1/files/{file_id}/chunk")
async def upload_chunk(file_id: uuid.UUID, chunk_index: int, chunk_data: bytes):
    # Validar chunk_index
    # Salvar chunk no MinIO
    # Atualizar manifest no DB
    # Retornar status

@app.post("/v1/files/{file_id}/complete")
async def complete_upload(file_id: uuid.UUID, checksum: str):
    # Validar todos os chunks foram enviados
    # Calcular checksum final
    # Comparar com checksum fornecido
    # Gerar download_url
```

**Prioridade**: 🔴 **CRÍTICA** - Requisito explícito do PDF (2GB)

---

### 4. **Webhooks Configuráveis** (RF-2.5.2 a RF-2.5.4)
**Status**: ❌ **NÃO IMPLEMENTADO**

**O que falta:**
- `POST /v1/webhooks` para registro de webhooks
- Tabela `webhooks` em CockroachDB
- Disparo automático de webhooks quando status muda (DELIVERED/READ)
- Retry exponencial para webhooks falhos
- Assinatura HMAC dos payloads

**Impacto**: Não é possível integrar com sistemas externos via callbacks configuráveis.

**Implementação sugerida:**
```python
# Em frontend_service/app/main.py
@app.post("/v1/webhooks")
async def register_webhook(webhook: WebhookCreate, current_user: User = Depends(get_current_user)):
    # Validar URL
    # Salvar em CockroachDB
    # Retornar webhook_id

# Em services/router_worker/worker.py ou novo serviço
# Quando status muda para DELIVERED/READ:
# - Consultar webhooks do remetente
# - Filtrar por eventos
# - Fazer POST HTTP com retry exponencial
```

**Prioridade**: 🔴 **CRÍTICA** - Requisito explícito do PDF (seção 2.5)

---

### 5. **Roteamento por Canais** (RF-2.3.1 a RF-2.3.2)
**Status**: ⚠️ **PARCIAL** - Schema aceita `channels`, mas roteamento ainda usa heurística

**O que falta:**
- Modificar `router_worker` para ler campo `channels` do payload Kafka
- Rotear baseado em `channels` (não heurística de `@`)
- Se `["all"]` → enviar para todos os tópicos de connectors
- Se lista específica → enviar apenas para tópicos correspondentes

**Impacto**: Cliente não pode escolher canais de entrega conforme especificado no PDF.

**Implementação sugerida:**
```python
# Em services/router_worker/worker.py
channels = data.get('channels', ['all'])
if 'all' in channels or ChannelType.ALL in channels:
    # Enviar para todos os connectors
    producer.send(TOPIC_WHATSAPP, payload)
    producer.send(TOPIC_INSTAGRAM, payload)
else:
    # Enviar apenas para canais especificados
    if 'whatsapp' in channels:
        producer.send(TOPIC_WHATSAPP, payload)
    if 'instagram' in channels:
        producer.send(TOPIC_INSTAGRAM, payload)
```

**Prioridade**: 🔴 **CRÍTICA** - Requisito funcional explícito

---

## 🟡 **IMPORTANTES - MÉDIA PRIORIDADE** (Completam funcionalidade)

### 6. **Presence Service** (RF-2.1.13)
**Status**: ❌ **NÃO IMPLEMENTADO**

**O que falta:**
- `POST /v1/presence/heartbeat` para atualizar status online
- `GET /v1/presence/{user_id}` para consultar status
- Armazenamento em Redis ou DB: `user_id` → `last_seen`, `status`
- Lógica de timeout (usuário offline após X segundos sem heartbeat)

**Impacto**: Não é possível saber quem está online para decidir entre push WebSocket ou persistência.

**Prioridade**: 🟡 **MÉDIA** - Importante para otimização, mas não bloqueia funcionalidade básica

---

### 7. **Histórico de Estados de Mensagem** (RF-2.2.2 a RF-2.2.3)
**Status**: ❌ **NÃO IMPLEMENTADO**

**O que falta:**
- Tabela `message_status_history` em Cassandra
- Registrar cada transição: SENT → DELIVERED → READ
- `GET /v1/messages/{message_id}/status/history` para consultar histórico

**Impacto**: Não é possível rastrear histórico completo de estados (requisito do PDF).

**Prioridade**: 🟡 **MÉDIA** - Melhora rastreabilidade, mas estados básicos já funcionam

---

### 8. **Mapeamento de Usuários entre Plataformas** (RF-2.3.3 a RF-2.3.4)
**Status**: ❌ **NÃO IMPLEMENTADO**

**O que falta:**
- Tabela `user_channels` em CockroachDB
- `POST /v1/users/{user_id}/channels` para vincular canais
- `GET /v1/users/{user_id}/channels` para listar canais
- Roteamento cross-channel inteligente (WhatsApp → Instagram)

**Impacto**: Não é possível mapear usuários internos para múltiplas plataformas externas.

**Prioridade**: 🟡 **MÉDIA** - Importante para multicanal completo, mas não bloqueia básico

---

### 9. **OpenTelemetry Tracing** (NFR-3.7.4)
**Status**: ❌ **NÃO IMPLEMENTADO**

**O que falta:**
- Instrumentação com OpenTelemetry em todos os serviços
- Spans para operações críticas (envio, processamento, entrega)
- Exportador para Jaeger ou Zipkin
- Correlação de logs com `trace_id` e `span_id`

**Impacto**: Não é possível investigar latência/falhas em produção de forma eficiente.

**Prioridade**: 🟡 **MÉDIA** - Importante para observabilidade, mas não bloqueia funcionalidade

---

### 10. **Logs Centralizados** (NFR-3.7.6 a NFR-3.7.8)
**Status**: ❌ **NÃO IMPLEMENTADO**

**O que falta:**
- Stack ELK/EFK ou Loki no docker-compose
- Configurar todos os serviços para enviar logs centralizados
- Formato JSON estruturado padronizado
- Dashboards de logs no Grafana/Kibana

**Impacto**: Logs ficam dispersos, difícil de investigar problemas.

**Prioridade**: 🟡 **MÉDIA** - Importante para operação, mas não bloqueia desenvolvimento

---

## 🟢 **DESEJÁVEIS - BAIXA PRIORIDADE** (Melhorias e polish)

### 11. **Dashboards Grafana Completos** (NFR-3.7.3)
**Status**: ⚠️ **PARCIAL** - Grafana existe, mas dashboards não estão criados

**O que falta:**
- Dashboard: Throughput de mensagens (msg/s)
- Dashboard: Latência de entrega (p50/p95/p99)
- Dashboard: Taxa de erro por serviço
- Dashboard: Utilização de recursos (CPU, memória, disco)
- Exportar dashboards como JSON e versionar

**Prioridade**: 🟢 **BAIXA** - Melhora visualização, mas métricas básicas já existem

---

### 12. **Testes de Carga Documentados** (NFR-3.1.5, TEST-1)
**Status**: ⚠️ **PARCIAL** - `locustfile.py` existe, mas falta documentação de resultados

**O que falta:**
- Executar testes de carga (100k msgs/min conforme escopo)
- Documentar resultados: throughput, latência p50/p95/p99
- Criar relatório de performance

**Prioridade**: 🟢 **BAIXA** - Importante para validação, mas não bloqueia desenvolvimento

---

### 13. **Alta Disponibilidade** (NFR-3.2.1 a NFR-3.2.7)
**Status**: ❌ **NÃO IMPLEMENTADO** (ambiente single-node)

**O que falta:**
- Múltiplos brokers Kafka com replicação
- Cluster Cassandra com replication factor >= 3
- Health checks robustos em todos os serviços
- Circuit breaker nos connectors
- Testes de failover documentados

**Prioridade**: 🟢 **BAIXA** - Importante para produção, mas PoC pode funcionar com single-node

---

### 14. **SDKs** (RF-2.5.6 a RF-2.5.7)
**Status**: ❌ **NÃO IMPLEMENTADO**

**O que falta:**
- SDK Python básico (`Chat4AllClient`)
- SDK JavaScript/TypeScript (opcional)

**Prioridade**: 🟢 **BAIXA** - Melhora experiência do desenvolvedor, mas não bloqueia uso da API

---

### 15. **Interface Formal para Connectors** (RF-2.6.1 a RF-2.6.4)
**Status**: ⚠️ **PARCIAL** - Connectors existem, mas sem interface formal

**O que falta:**
- Classe base abstrata ou protocolo para connectors
- Documentação para desenvolver novos connectors
- Template/boilerplate de connector

**Prioridade**: 🟢 **BAIXA** - Melhora extensibilidade, mas connectors já funcionam

---

## 📋 **RESUMO EXECUTIVO**

### Requisitos Críticos (🔴) - **5 itens**
1. Gestão de Conversas (RF-2.1.1 a RF-2.1.4)
2. Idempotência e Deduplicação (RF-2.2.4, NFR-3.3.1)
3. Chunked Upload Resumable 2GB (RF-2.1.9 a RF-2.1.11)
4. Webhooks Configuráveis (RF-2.5.2 a RF-2.5.4)
5. Roteamento por Canais (RF-2.3.1 a RF-2.3.2)

### Requisitos Importantes (🟡) - **5 itens**
6. Presence Service (RF-2.1.13)
7. Histórico de Estados (RF-2.2.2 a RF-2.2.3)
8. Mapeamento de Usuários entre Plataformas (RF-2.3.3 a RF-2.3.4)
9. OpenTelemetry Tracing (NFR-3.7.4)
10. Logs Centralizados (NFR-3.7.6 a NFR-3.7.8)

### Requisitos Desejáveis (🟢) - **5 itens**
11. Dashboards Grafana Completos (NFR-3.7.3)
12. Testes de Carga Documentados (NFR-3.1.5, TEST-1)
13. Alta Disponibilidade (NFR-3.2.1 a NFR-3.2.7)
14. SDKs (RF-2.5.6 a RF-2.5.7)
15. Interface Formal para Connectors (RF-2.6.1 a RF-2.6.4)

---

## 🎯 **PLANO DE AÇÃO SUGERIDO**

### Fase 1: Funcionalidade Básica Completa (Sprint 1-2)
**Foco**: Implementar os 5 requisitos críticos (🔴)
- **Estimativa**: 2-3 semanas
- **Resultado**: Sistema funcional completo conforme requisitos básicos do PDF

### Fase 2: Completude e Observabilidade (Sprint 3-4)
**Foco**: Implementar os 5 requisitos importantes (🟡)
- **Estimativa**: 2-3 semanas
- **Resultado**: Sistema completo com observabilidade e funcionalidades avançadas

### Fase 3: Polish e Produção (Sprint 5-6)
**Foco**: Implementar os 5 requisitos desejáveis (🟢)
- **Estimativa**: 2-3 semanas
- **Resultado**: Sistema pronto para produção com alta disponibilidade e documentação completa

---

## 📝 **NOTAS**

- **Status atual**: ~40% dos requisitos funcionais implementados, ~30% dos não funcionais
- **Gap crítico**: Faltam funcionalidades core (conversas, webhooks, upload resumable)
- **Recomendação**: Priorizar Fase 1 para atingir MVP completo conforme PDF

---

**Última atualização**: Baseado em análise do código atual e comparação com `chat4all v2.pdf`

