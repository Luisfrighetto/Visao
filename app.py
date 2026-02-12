from fastapi import FastAPI, File, UploadFile, HTTPException
from pathlib import Path
import uuid
import shutil
from wpp import AnalisadorFutvolley

app = FastAPI(title="API Futevôlei Vision")

UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Inicializa o analisador uma única vez no startup
analisador = AnalisadorFutvolley("yolov8n.pt")

@app.get("/api/health")
def health():
    return {"status": "ready", "model": "YOLOv8n"}

@app.post("/api/analyze")
async def analyze_video(file: UploadFile = File(...)):
    # 1. Salvar o arquivo recebido
    file_id = str(uuid.uuid4())[:8]
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 2. Chamar o motor de análise do wpp.py
        print(f"🚀 Enviando {file_path.name} para o analisador...")
        resultado = analisador.analisar(file_path, RESULTS_DIR)
        
        return {
            "message": "Análise concluída com sucesso",
            "stats": resultado,
            "file": file_path.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
