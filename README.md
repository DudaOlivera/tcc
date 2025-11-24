

````markdown
# 📘 Documentação do Sistema de Detecção de Placas (LPR)

## 1. Visão Geral do Projeto
Este projeto é um sistema de **LPR (License Plate Recognition)** que utiliza Inteligência Artificial para identificar e ler placas de veículos em vídeos.

A arquitetura funciona no modelo **Cliente-Servidor** usando **gRPC** para comunicação:

* **Cliente (`app.py`):** A interface visual onde o usuário envia o vídeo.
* **Servidor (`server.py`):** Onde ocorre o processamento pesado (IA, leitura de texto e banco de dados).

---

## 2. Estrutura de Arquivos

Baseado na estrutura da pasta, aqui está a função de cada arquivo importante:

### 📂 Pasta `TCC` (Raiz)
* **`app.py`**: É o frontend feito em **Streamlit**. Ele pega o vídeo, manda para o servidor e mostra o resultado na tela.
* **`client_pb2.py`** e **`client_pb2_grpc.py`**: Arquivos gerados automaticamente pelo gRPC. Eles servem para o `app.py` saber como "conversar" com o servidor.
* **`style.css`**: Arquivo de estilo para deixar a interface do Streamlit mais bonita.

### 📂 Pasta `server/`
* **`server.py`**: O "cérebro" do sistema. Roda a IA (YOLO), faz o OCR (EasyOCR) e salva no banco de dados.
* **`best.pt`**: O modelo treinado da IA (YOLOv8). É esse arquivo que "sabe" o que é uma placa.
* **`server.proto`**: O contrato. Define as regras de comunicação entre cliente e servidor (quais dados entram e quais saem).
* **`server_pb2...`**: Arquivos de apoio gerados pelo gRPC para o servidor funcionar.

---

## 3. Como funciona o Servidor (`server/server.py`)

Este script fica rodando esperando receber imagens. O fluxo dele é:

1.  **Recebe a imagem** via gRPC.
2.  **Detecta a placa**: Usa o **YOLO** (`best.pt`) para encontrar onde está a placa na imagem.
3.  **Recorta a placa**: Pega apenas o pedaço da imagem que interessa (ROI).
4.  **Lê o texto (OCR)**: Usa o **EasyOCR** para transformar a imagem da placa em texto.
5.  **Tratamento de Erros**:
    * Usa a função `replace_similar_characters` para corrigir erros comuns (ex: trocar 'B' por '8' ou 'O' por '0').
    * Verifica se é placa **Mercosul** ou **Tradicional** usando *Regex*.
6.  **Salva os dados**:
    * Grava a imagem da placa na pasta `plates/`.
    * Grava os dados (texto, hora, tipo) no **MongoDB**.
7.  **Devolve a resposta**: Manda o texto lido de volta para o `app.py`.

---

## 4. Como funciona o Cliente (`app.py`)

Este script roda no navegador. O fluxo é:

1.  **Interface**: Cria uma página web simples onde você pode fazer upload de um vídeo (`.mp4`, `.avi`, etc).
2.  **Streaming**: Quebra o vídeo em vários frames (imagens) e envia um por um para o servidor.
3.  **Visualização**:
    * Desenha um retângulo na placa detectada.
    * Mostra o texto da placa lida na lateral.
    * Mostra a imagem "cropada" (recortada) da placa.
4.  **Banco de Dados**: O cliente também se conecta ao Mongo para mostrar o status da conexão e salvar redundâncias se necessário.

---

## 5. Tecnologias Utilizadas

Ferramentas principais do projeto:

* **Linguagem:** Python 3.x
* **Comunicação:** gRPC (Protocol Buffers)
* **Visão Computacional:** OpenCV e Ultralytics YOLOv8
* **OCR (Leitura de Texto):** EasyOCR
* **Interface Web:** Streamlit
* **Banco de Dados:** MongoDB

---

## 6. Como Rodar o Projeto (Passo a Passo)

Para o sistema funcionar, você precisa abrir **3 terminais** diferentes.

### Passo 1: Iniciar o Banco de Dados
Certifique-se de que o MongoDB está instalado e rodando.
*(Geralmente ele já roda como serviço no Linux/Windows, mas se precisar iniciar manualmente)*:
```bash
mongod
````

### Passo 2: Iniciar o Servidor (O Cérebro)

Abra o terminal na pasta raiz do projeto e rode:

**Linux / Mac:**

```bash
python server/server.py
```

**Windows:**

```bash
python server\server.py
```

*Você verá a mensagem: "Servidor gRPC rodando na porta 50051..."*

### Passo 3: Iniciar o Cliente (A Interface)

Abra outro terminal na pasta raiz e rode:

```bash
streamlit run app.py
```
