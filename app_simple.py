from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "⚽ Analisador de Futebol"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "video-analyzer"}

@app.get("/test")
async def test():
    return {"test": "OK", "timestamp": "now"}

if __name__ == "__main__":
    print("🚀 Servidor SIMPLES iniciando...")
    uvicorn.run(app, host="0.0.0.0", port=5000)
