
-----

# 🧪 Guia de Testes e Demonstração - Chat4All v2

Este guia explica como validar as funcionalidades principais do sistema utilizando a Suite de Testes automatizada no Postman e as interfaces de demonstração web.

## 📋 Pré-requisitos

1.  O ambiente deve estar rodando (`docker-compose up -d`).
2.  Você deve ter o [Postman](https://www.postman.com/downloads/) instalado.
3.  Os arquivos `demo_chat.html`, `demo_upload.html` e `postman_collection.json` devem estar na raiz do projeto.

-----

## 🚀 Parte 1: Testes Automatizados com Postman

A collection do Postman contém scripts que automatizam o fluxo de autenticação, criação de conversas e envio de mensagens, facilitando a validação rápida.

### 1\. Importar a Collection

1.  Abra o Postman.
2.  Clique no botão **Import** (canto superior esquerdo).
3.  Arraste o arquivo `postman_collection.json` (ou o JSON que você salvou) para a janela.
4.  Confirme a importação.

### 2\. Executar os Cenários

A collection está organizada em pastas lógicas. Recomenda-se executar na seguinte ordem:

#### **Passo A: Autenticação (Obrigatório)**

  * Vá na pasta `0. Configuração (Auth)` \> **Login (Admin)**.
  * Clique em **Send**.
  * **O que acontece:** O sistema faz login e **salva automaticamente** o `access_token` nas variáveis de ambiente do Postman. Você não precisa copiar e colar nada manualmente.

#### **Passo B: Chat Core**

  * Vá na pasta `1. Core`.
  * Execute **Criar Grupo**. O ID da conversa será salvo automaticamente.
  * Execute **Enviar Msg (Texto)**.
  * Execute **Ver Histórico** para confirmar que a mensagem foi salva.

#### **Passo C: Integrações (Gap Analysis)**

  * Vá na pasta `3. Gestão`.
  * Execute **Vincular Canal (WhatsApp)** para testar o mapeamento de usuários.
  * Execute **Presence: Heartbeat** para ficar online.

-----

## 💬 Parte 2: Chat em Tempo Real (WebSocket)

Utilize o arquivo `demo_chat.html` para simular um cliente real (como WhatsApp Web).

### Passo a Passo

1.  **Obtenha um Token:** Execute a requisição de Login no Postman e copie o `access_token` da resposta.
2.  **Obtenha um ID de Conversa:** Execute a requisição "Criar Grupo" no Postman e copie o `conversation_id`.
3.  Abra o arquivo `demo_chat.html` no seu navegador (Chrome/Firefox).
4.  Cole o **Token** e o **ID da Conversa** nos campos respectivos.
5.  Clique em **Conectar WebSocket**.
      * *Status deve mudar para:* 🟢 **Conectado e Ouvindo...**
6.  **Teste de Recebimento:**
      * Volte ao Postman.
      * Use a requisição **Enviar Msg (Texto)** com o mesmo `chat_id`.
      * Observe no navegador: A mensagem aparecerá instantaneamente na área de chat sem recarregar a página.

-----

## 📂 Parte 3: Upload de Arquivos Gigantes (2GB+)

Utilize o arquivo `demo_upload.html` para validar a funcionalidade de *Chunked Upload* e remontagem de arquivos.

### Passo a Passo

1.  Abra o arquivo `demo_upload.html` no navegador.
2.  Cole o **Token de Acesso** (o mesmo usado anteriormente).
3.  Clique em **Escolher arquivo** e selecione um arquivo grande (sugestão: um instalador ou vídeo de 500MB+).
4.  Clique em **Iniciar Upload**.

### O que observar

1.  **Barra de Progresso:** Acompanhe o envio dos fragmentos (*chunks*) de 5MB em tempo real.
2.  **Logs na Tela:** O console mostrará `Enviando Chunk 1...`, `Enviando Chunk 2...`.
3.  **Conclusão:** Ao final (100%), o sistema processará a remontagem e exibirá um link verde: **📥 Download Arquivo Completo**.
4.  **Validação:** Clique no link. O arquivo deve ser baixado do MinIO com o tamanho original exato e integridade preservada.

-----

## 📊 Monitoramento em Tempo Real (Opcional)

Enquanto executa os testes acima, você pode acompanhar a saúde do sistema nos dashboards:

  * **Grafana:** [http://localhost:3000](https://www.google.com/search?q=http://localhost:3000) (admin/admin)
      * Veja os gráficos de "Active WebSockets" subindo quando você conecta o `demo_chat.html`.
      * Veja a taxa de "Chunks/s" subir durante o upload no `demo_upload.html`.
  * **Jaeger UI:** [http://localhost:16686](https://www.google.com/search?q=http://localhost:16686)
      * Busque por traces do `frontend_service` para ver o tempo de resposta de cada requisição.