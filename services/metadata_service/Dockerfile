# Usamos Python 3.11 (que sabemos que funciona bem com as libs atuais)
FROM python:3.11-slim

# Define o diretório de trabalho
WORKDIR /app

# Copia as dependências e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação (pasta app)
COPY app/ ./app/

# Comando para iniciar a API na porta 8001
# --host 0.0.0.0 é obrigatório para o Docker expor a rede
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]