import os
from minio import Minio
from minio.commonconfig import ComposeSource
from datetime import timedelta
import logging
import io

logger = logging.getLogger(__name__)

# Configurações
MINIO_URL = os.getenv("MINIO_URL", "minio:9000").replace("http://", "")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET_NAME = "chat-files"

# Cliente Único (Padrão)
client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def upload_chunk_to_minio(file_id: str, chunk_index: int, data: bytes):
    object_name = f"temp/{file_id}/{chunk_index}.part"
    try:
        client.put_object(
            BUCKET_NAME,
            object_name,
            io.BytesIO(data),
            len(data)
        )
        return True
    except Exception as e:
        logger.error(f"Erro ao subir chunk {chunk_index}: {e}")
        return False

def compose_final_file(file_id: str, filename: str, total_chunks: int) -> str:
    final_object_name = f"uploads/{file_id}_{filename}"
    
    sources = []
    for i in range(total_chunks):
        sources.append(
            ComposeSource(BUCKET_NAME, f"temp/{file_id}/{i}.part")
        )

    try:
        logger.info(f"Compondo arquivo final: {final_object_name}")
        
        # 1. Juntar as partes
        client.compose_object(
            bucket_name=BUCKET_NAME,
            object_name=final_object_name,
            sources=sources
        )

        # 2. Limpar temporários
        for i in range(total_chunks):
             try:
                 client.remove_object(BUCKET_NAME, f"temp/{file_id}/{i}.part")
             except: pass

        # 3. Gerar URL Pura (vai sair como http://minio:9000/...)
        # Como editamos o hosts, seu navegador vai aceitar esse endereço!
        url = client.presigned_get_object(
            BUCKET_NAME, 
            final_object_name, 
            expires=timedelta(days=7)
        )
        
        logger.info(f"URL Gerada: {url}")
        return url
    
    except Exception as e:
        logger.error(f"Erro crítico ao compor arquivo: {e}")
        raise e