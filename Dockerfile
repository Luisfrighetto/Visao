FROM python:3.11-slim

# Dependências do sistema para OpenCV e Processamento
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar modelo local para evitar download no startup
COPY yolov8n.pt . 

# Copiar o código (incluindo app.py e wpp.py)
COPY . .

# Criar pastas e dar permissão
RUN mkdir -p uploads results Pictures && chmod 777 uploads results Pictures

EXPOSE 5000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
