from locust import HttpUser, task, between
import uuid

@task
def send_message(self):
    if not self.token:
        return

    headers = {"Authorization": f"Bearer {self.token}"}
    
    # Payload limpo, sem sender_id
    self.client.post("/v1/messages", json={
        "chat_id": "11111111-1111-1111-1111-111111111111",
        "content": "Teste de Carga Locust"
    }, headers=headers)

class ChatUser(HttpUser):
    wait_time = between(1, 3) # Espera entre 1 e 3 segundos
    token = None

    def on_start(self):
        """
        Executado quando cada usuário virtual "nasce".
        Faz login para pegar o token.
        """
        # Usando o usuário novo que acabamos de criar no Metadata
        response = self.client.post("/token", data={"username": "locust_user", "password": "123"})
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        else:
            print(f"Falha no Login do Locust: {response.status_code} - {response.text}")

    @task
    def send_message(self):
        """
        Tarefa principal: Enviar mensagens
        """
        if not self.token:
            return # Se não logou, não tenta enviar

        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Usa um chat_id fixo para teste
        chat_id = "11111111-1111-1111-1111-111111111111"
        
        self.client.post("/v1/messages", json={
            "chat_id": chat_id,
            "content": "Teste de Carga Locust Automático",
            "sender_id": "locust_user"
        }, headers=headers)