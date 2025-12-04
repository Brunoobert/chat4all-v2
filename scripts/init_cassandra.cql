-- 1. Criar o Keyspace
CREATE KEYSPACE IF NOT EXISTS chat4all_ks 
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};

USE chat4all_ks;

-- 2. Tabela de Mensagens
-- ATENÇÃO: Adicionamos o campo 'channels' do tipo list<text>
CREATE TABLE IF NOT EXISTS messages (
    conversation_id uuid,
    message_id uuid,
    sender_id text,
    content text,
    status text,
    created_at timestamp,
    type text,
    file_id text,
    channels list<text>, -- <--- NOVO CAMPO
    PRIMARY KEY (conversation_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);

-- 3. Tabela de Conversas
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id uuid PRIMARY KEY,
    type text,
    members list<text>,
    metadata map<text,text>,
    created_at timestamp
);

CREATE TABLE IF NOT EXISTS file_uploads (
    file_id uuid PRIMARY KEY,
    filename text,
    total_size bigint,
    chunk_size int,
    total_chunks int,
    uploaded_chunks set<int>, -- Lista de índices já recebidos (ex: {1, 2, 5})
    status text, -- 'PENDING', 'COMPLETED', 'FAILED'
    upload_url text, -- URL final no MinIO
    owner_id text,
    created_at timestamp
);

-- Tabela de Metadados de Arquivos (Arquivo pronto)
CREATE TABLE IF NOT EXISTS files (
    file_id uuid PRIMARY KEY,
    owner_id text,
    filename text,
    size bigint,
    content_type text,
    minio_path text,
    created_at timestamp
);

-- 4. Índices
CREATE INDEX IF NOT EXISTS ON conversations (type);