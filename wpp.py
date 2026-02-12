import cv2
import time
import json
import numpy as np
from pathlib import Path
from ultralytics import YOLO

class AnalisadorFutvolley:
    def __init__(self, model_path="yolov8n.pt"):
        self.model_path = model_path
        self.model = YOLO(model_path)
        print(f"✅ Modelo {model_path} carregado no Analisador.")

    def analisar(self, video_input, output_dir, confidence=0.4):
        video_path = Path(video_input)
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        cap = cv2.VideoCapture(str(video_path))
        fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        timestamp = int(time.time())
        output_filename = f"processed_{video_path.stem}_{timestamp}.mp4"
        output_path = output_dir / output_filename
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        stats = {"jogadores_max": 0, "bolas_detectadas": 0, "total_frames": total_frames}
        frame_count = 0
        start_time = time.time()

        print(f"🎬 Processando: {video_path.name} ({width}x{height})")

        while True:
            ret, frame = cap.read()
            if not ret: break
            frame_count += 1

            # Melhora na detecção: imgsz=640 ajuda na precisão de objetos pequenos
            results = self.model(frame, conf=confidence, classes=[0, 32], verbose=False, imgsz=640)
            
            jogadores = 0
            bolas = 0
            
            if results and len(results) > 0:
                for box in results[0].boxes:
                    cls = int(box.cls[0])
                    if cls == 0: jogadores += 1
                    elif cls == 32: bolas += 1
                
                annotated_frame = results[0].plot()
            else:
                annotated_frame = frame.copy()

            stats["jogadores_max"] = max(stats["jogadores_max"], jogadores)
            stats["bolas_detectadas"] += bolas

            # Overlay visual
            cv2.putText(annotated_frame, f"Jogadores: {jogadores} | Bolas: {bolas}", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            out.write(annotated_frame)

        cap.release()
        out.release()
        
        stats["tempo_total"] = time.time() - start_time
        stats["video_saida"] = str(output_path)
        
        # Salva JSON de estatísticas
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w') as f:
            json.dump(stats, f, indent=2)

        return stats
