import boto3
import logging
from botocore.exceptions import ClientError
import os

# Configurações
# URL INTERNA (Para o Python salvar o arquivo)
MINIO_INTERNAL_URL = os.getenv("MINIO_URL", "http://minio:9000")

# URL EXTERNA (Para o seu navegador baixar o arquivo)
# Se estiver rodando localmente, é localhost. Em produção, seria seu dominio.com
MINIO_EXTERNAL_URL = "http://localhost:9000" 

ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET_NAME = "chat-files"

logger = logging.getLogger(__name__)

def get_s3_client_internal():
    """Cliente para operações DENTRO do Docker (Upload)"""
    return boto3.client(
        's3',
        endpoint_url=MINIO_INTERNAL_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=boto3.session.Config(signature_version='s3v4'),
        region_name='us-east-1'
    )

def get_s3_client_external():
    """Cliente configurado APENAS para gerar links para quem está fora (Download)"""
    return boto3.client(
        's3',
        endpoint_url=MINIO_EXTERNAL_URL, # <-- AQUI ESTÁ O SEGREDO
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=boto3.session.Config(signature_version='s3v4'),
        region_name='us-east-1'
    )

def create_presigned_url(object_name: str, expiration=3600):
    """
    Gera uma URL temporária para download usando o host EXTERNO.
    """
    # Usamos o cliente externo para que a assinatura bata com 'localhost'
    s3_client = get_s3_client_external()
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_name
            },
            ExpiresIn=expiration
        )
        # Não precisamos mais fazer .replace(), a URL já nasce certa!
        return response
            
    except ClientError as e:
        logger.error(f"Erro ao gerar URL presigned: {e}")
        return None

def upload_file_to_minio(file_obj, object_name: str, content_type: str):
    """
    Envia um arquivo usando a rede INTERNA do Docker.
    """
    # Usamos o cliente interno para conectar no 'minio:9000'
    s3_client = get_s3_client_internal()
    try:
        s3_client.upload_fileobj(
            file_obj,
            BUCKET_NAME,
            object_name,
            ExtraArgs={'ContentType': content_type}
        )
        logger.info(f"Arquivo {object_name} enviado para o MinIO.")
        return True
    except ClientError as e:
        logger.error(f"Erro ao enviar arquivo: {e}")
        return False