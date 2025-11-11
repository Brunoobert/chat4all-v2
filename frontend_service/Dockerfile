# 1. Imagem base
FROM python:3.10-slim

# 2. Define o diretório de trabalho
WORKDIR /app_code

# 3. Copia o requirements.txt (que está na raiz do contexto)
COPY requirements.txt .

# 4. Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# 5. AJUSTE AQUI: Copia a pasta 'app' (do host) para dentro de /app_code (no container)
# Agora seu código estará em /app_code/app/main.py
COPY app/ ./app/

# 6. AJUSTE AQUI: O comando agora aponta para o módulo 'app.main'
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]