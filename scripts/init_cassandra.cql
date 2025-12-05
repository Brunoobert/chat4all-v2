-- 1. Criar o Keyspace
CREATE KEYSPACE IF NOT EXISTS chat4all_ks 
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};

USE chat4all_ks;

-- 2. Tabela de Mensagens (Core)
CREATE TABLE IF NOT EXISTS messages (
    conversation_id uuid,
    message_id uuid,
    sender_id text,
    content text,
    status text,
    created_at timestamp,
    type text,
    file_id text,
    channels list<text>,
    PRIMARY KEY (conversation_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);

-- 3. Tabela de Conversas (Metadata)
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id uuid PRIMARY KEY,
    type text,
    members list<text>,
    metadata map<text,text>,
    created_at timestamp
);

-- 4. Índices
CREATE INDEX IF NOT EXISTS ON conversations (type);

-- 5. Uploads (Fase 2)
CREATE TABLE IF NOT EXISTS file_uploads (
    file_id uuid PRIMARY KEY,
    filename text,
    total_size bigint,
    chunk_size int,
    total_chunks int,
    uploaded_chunks set<int>,
    status text,
    upload_url text,
    owner_id text,
    created_at timestamp
);

CREATE TABLE IF NOT EXISTS files (
    file_id uuid PRIMARY KEY,
    owner_id text,
    filename text,
    size bigint,
    content_type text,
    minio_path text,
    created_at timestamp
);

-- 6. Funcionalidades Extras (Gap Analysis)
CREATE TABLE IF NOT EXISTS webhooks (
    user_id text, 
    webhook_id uuid, 
    url text, 
    events list<text>, 
    secret text, 
    created_at timestamp, 
    PRIMARY KEY (user_id, webhook_id)
);

CREATE TABLE IF NOT EXISTS user_channels (
    user_id text, 
    channel_type text, 
    identifier text, 
    created_at timestamp, 
    PRIMARY KEY (user_id, channel_type)
);

CREATE TABLE IF NOT EXISTS user_presence (
    user_id text PRIMARY KEY, 
    status text, 
    last_seen timestamp
);