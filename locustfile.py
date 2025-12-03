from locust import HttpUser, task, between
import uuid

class ChatUser(HttpUser):
    wait_time = between(1, 3) # Simula um usuário real esperando entre 1s e 3s
    token = None

    def on_start(self):
        """
        Executado uma vez quando o usuário "nasce".
        Faz login para pegar o token JWT.
        """
        # Garanta que este usuário 'locust_user' existe no seu Metadata Service!
        response = self.client.post("/token", data={"username": "locust_user", "password": "123"})
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        else:
            print(f"❌ Falha no Login do Locust: {response.status_code} - {response.text}")

    @task
    def send_message(self):
        """
        Tarefa principal: Enviar mensagens continuamente.
        """
        if not self.token:
            return # Se não logou, aborta

        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Payload limpo (conforme o Schema atualizado)
        # Não precisa mandar sender_id, a API pega do token
        self.client.post("/v1/messages", json={
            "chat_id": "8f8736df-112b-4bcc-a298-12804c76f7fc",
            "content": "Teste de Carga Final"
        }, headers=headers)