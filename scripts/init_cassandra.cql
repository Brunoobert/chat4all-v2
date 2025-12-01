-- 1. Criar o Keyspace
CREATE KEYSPACE IF NOT EXISTS chat4all_ks 
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};

-- 2. Usar o Keyspace
USE chat4all_ks;

-- 3. Tabela de Mensagens (Histórico)
CREATE TABLE IF NOT EXISTS messages (
    conversation_id uuid,
    message_id uuid,
    sender_id text,
    content text,
    status text,
    created_at timestamp,
    type text,
    file_id text,
    PRIMARY KEY (conversation_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);

-- 4. Tabela de Conversas (Grupos/Privado)
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id uuid PRIMARY KEY,
    type text,
    members list<text>,
    metadata map<text,text>,
    created_at timestamp
);

-- 5. Índices (Opcional, mas bom para performance futura)
CREATE INDEX IF NOT EXISTS ON conversations (type);