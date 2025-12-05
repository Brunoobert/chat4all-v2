from locust import HttpUser, task, between
import uuid
import random

# Simula um arquivo de 15KB (3 chunks de 5KB se o chunk for pequeno, ou 1 se for grande)
FAKE_FILE_CONTENT = b"A" * 1024 * 15 

class ChatUser(HttpUser):
    wait_time = between(1, 3)
    token = None
    chat_id = "f7f859a9-9f85-40c1-bd8a-7e24eb9983eb" # <--- IMPRESCINDÍVEL

    def on_start(self):
        # Cria usuário aleatório para não dar conflito
        user = f"user_{uuid.uuid4().hex[:8]}"
        # Tenta criar usuário (se falhar, assume que login existe)
        try:
            # Atenção: Ajuste a URL do Metadata Service se necessário, ou crie user manualmente antes
            # Aqui vamos assumir que usamos o admin hardcoded para teste de carga rápido
            res = self.client.post("/token", data={"username": "locust_user", "password": "123"})
            if res.status_code == 200:
                self.token = res.json()["access_token"]
        except Exception as e:
            print(f"Erro login: {e}")

    @task(3) # Peso 3: Acontece mais vezes
    def send_message(self):
        if not self.token: return
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.post("/v1/messages", json={
            "chat_id": self.chat_id,
            "content": f"Msg Carga {random.randint(1, 1000)}",
            "channels": ["all"]
        }, headers=headers)

    @task(1) # Peso 1: Acontece menos vezes (Upload é pesado)
    def send_file(self):
        if not self.token: return
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # 1. Initiate
        res_init = self.client.post("/v1/files/initiate", json={
            "filename": f"loadtest_{uuid.uuid4()}.txt",
            "total_size": len(FAKE_FILE_CONTENT),
            "content_type": "text/plain"
        }, headers=headers)
        
        if res_init.status_code != 200: return
        file_data = res_init.json()
        file_id = file_data['file_id']
        
        # 2. Chunk (Mandando tudo num chunk só para o teste ser rápido, ou dividir se quiser)
        # O backend aceita chunks de qualquer tamanho, a validação de 5MB é soft no client
        self.client.post(f"/v1/files/{file_id}/chunk", 
            files={"file": FAKE_FILE_CONTENT},
            data={"chunk_index": 0},
            headers={"Authorization": f"Bearer {self.token}"}
        )

        # 3. Complete
        self.client.post(f"/v1/files/{file_id}/complete", headers=headers)