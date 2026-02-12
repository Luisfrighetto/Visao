.PHONY: all build up down shell logs clean run rebuild status test purge help

IMAGE_NAME = video-analyzer
CONTAINER_NAME = analyzer-container
PORT = 5000

all: build up

build:
	@echo "🔨 Construindo Analisador de Vídeos..."
	@docker build -t $(IMAGE_NAME) .
	@echo "✅ Imagem construída"

up:
	@echo "🚀 Iniciando Analisador..."
	@docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):5000 \
		-v $(PWD)/uploads:/app/uploads \
		-v $(PWD)/results:/app/results \
		-v $(PWD)/Pictures:/app/Pictures \
		--restart unless-stopped \
		$(IMAGE_NAME)
	@echo "✅ Container iniciado"
	@echo "🌐 Interface: http://localhost:$(PORT)"
	@echo "📚 Docs: http://localhost:$(PORT)/docs"

down:
	@echo "🛑 Parando container..."
	@docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@docker rm $(CONTAINER_NAME) 2>/dev/null || true
	@echo "✅ Container removido"

shell:
	@docker exec -it $(CONTAINER_NAME) /bin/bash

logs:
	@docker logs -f $(CONTAINER_NAME)

clean: down
	@docker rmi $(IMAGE_NAME) 2>/dev/null || true
	@docker system prune -f
	@echo "🧹 Limpeza concluída"

rebuild: clean build up
	@echo "🔄 Rebuild completo"

status:
	@echo "📊 Status:"
	@docker ps -a --filter="name=$(CONTAINER_NAME)" --format="table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}" || echo "ℹ️  Nenhum container"

test:
	@echo "🧪 Testando API..."
	@curl -s http://localhost:$(PORT)/api/health | python3 -m json.tool 2>/dev/null || echo "❌ API não responde"
	@echo "🌐 Interface: HTTP 200" && curl -s -o /dev/null -w "%{http_code}" http://localhost:$(PORT)/ || echo "❌"

purge:
	@make down
	@docker system prune -a -f --volumes
	@echo "💣 Sistema limpo"

help:
	@echo "📖 Comandos:"
	@echo "  make all     - Build + Up"
	@echo "  make up      - Iniciar"
	@echo "  make down    - Parar"
	@echo "  make logs    - Ver logs"
	@echo "  make test    - Testar API"
	@echo "  make rebuild - Reconstruir tudo"
	@echo "  make purge   - Limpeza total"
