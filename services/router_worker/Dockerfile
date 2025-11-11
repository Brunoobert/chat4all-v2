# 1. Usar a imagem base do Python 3.11 (a chave do sucesso)
FROM python:3.11-slim

# 2. Definir o diretório de trabalho dentro do contêiner
WORKDIR /app

# 3. Copiar o arquivo de dependências
COPY requirements.txt .

# 4. Instalar as dependências
#    Usamos --no-cache-dir para manter a imagem pequena
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar o código do worker
#    (Como o worker é um único arquivo, só copiamos ele)
COPY worker.py .

# 6. Comando para iniciar o worker quando o contêiner subir
CMD ["python", "worker.py"]