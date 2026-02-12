# 🏐 Futevôlei Vision API

Sistema de análise inteligente para vídeos de futevôlei utilizando **YOLOv8** e **FastAPI**.

## 🚀 Estrutura do Projeto
- **app.py**: API de entrada (FastAPI) que gerencia uploads e monitoramento.
- **wpp.py**: Motor de Visão Computacional (YOLOv8) especializado na detecção de jogadores e bola.
- **Docker**: Ambiente isolado para garantir que o processamento funcione em qualquer máquina.

## 🛠️ Tecnologias
- Python 3.11
- YOLOv8 (Ultralytics)
- OpenCV (Processamento de vídeo)
- FastAPI (Servidor Web)
- Docker & Docker Compose

## 📦 Como Rodar
1. **Build da imagem:**
   ```bash
   docker build -t meu-projeto-visao .
   ```

2. **Iniciar o contêiner:**
   ```bash
   docker run -d -p 5000:5000 \
     -v $(pwd)/uploads:/app/uploads \
     -v $(pwd)/results:/app/results \
     --name planeta-wpp meu-projeto-visao
   ```

## 📊 Endpoints
- `GET /api/health`: Verifica se o modelo está carregado.
- `POST /api/analyze`: Envia um vídeo para análise.

## 📈 Melhorias de Precisão
O sistema utiliza `imgsz=640` e confiança ajustada em `0.4` no arquivo `wpp.py` para melhor rastreio da bola em alta velocidade.
