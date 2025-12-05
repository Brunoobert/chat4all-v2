FROM python:3.9-slim
WORKDIR /app
RUN pip install kafka-python requests
COPY . .
CMD ["python", "-u", "main.py"]