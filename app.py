from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import os
import sys
from pathlib import Path
import json
import cv2
import numpy as np
from ultralytics import YOLO
import uvicorn
import asyncio
import threading
import uuid
import time
import torch




app = FastAPI(title="Analisador de Vídeos de Futebol - YOLOv8")

# ===== CONFIGURAÇÕES =====
UPLOAD_FOLDER = Path("uploads")
RESULTS_FOLDER = Path("results")
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'MP4', 'AVI', 'MOV'}

# Criar diretórios se não existirem
UPLOAD_FOLDER.mkdir(exist_ok=True)
RESULTS_FOLDER.mkdir(exist_ok=True)

# ===== MODELO YOLOv8 =====
MODEL = None
MODEL_LOADED = False
MODEL_LOADING = False
MODEL_ERROR = None

def load_yolo_model():
    """Carrega o modelo YOLOv8 em background"""
    global MODEL, MODEL_LOADED, MODEL_LOADING, MODEL_ERROR
    
    MODEL_LOADING = True
    try:
        print("🔄 Iniciando carregamento do modelo YOLOv8n...")
        
        # Tenta carregar modelo local primeiro
        model_path = Path("yolov8n.pt")
        if model_path.exists():
            print("📦 Carregando modelo local: yolov8n.pt")
            MODEL = YOLO(str(model_path))
        else:
            print("🌐 Baixando modelo YOLOv8n da internet...")
            MODEL = YOLO('yolov8n.pt')  # Isso baixa automaticamente
        
        # Teste rápido do modelo
        test_image = np.zeros((640, 640, 3), dtype=np.uint8)
        _ = MODEL(test_image, verbose=False)
        
        MODEL_LOADED = True
        MODEL_ERROR = None
        print("✅ Modelo YOLOv8 carregado com sucesso!")
        
    except Exception as e:
        MODEL_ERROR = str(e)
        print(f"❌ Erro ao carregar modelo: {e}")
        import traceback
        traceback.print_exc()
    finally:
        MODEL_LOADING = False

# Iniciar carregamento em thread separada
model_thread = threading.Thread(target=load_yolo_model, daemon=True)
model_thread.start()

# ===== FUNÇÕES AUXILIARES =====
def allowed_file(filename: str) -> bool:
    """Verifica se a extensão do arquivo é permitida"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def analyze_video_safe(video_path: Path, confidence: float = 0.5):
    """Analisa vídeo com tratamento de erros robusto"""
    if not MODEL_LOADED:
        return None, "Modelo ainda não carregado. Aguarde alguns segundos.", None
    
    try:
        print(f"🎬 Iniciando análise do vídeo: {video_path.name}")
        
        # Abrir vídeo
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None, f"Não foi possível abrir o vídeo: {video_path}", None
        
        # Obter informações do vídeo
        fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        
        if total_frames == 0:
            # Contar frames manualmente se necessário
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            total_frames = 0
            while True:
                ret, _ = cap.read()
                if not ret:
                    break
                total_frames += 1
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        print(f"   📊 Resolução: {width}x{height}, FPS: {fps}, Frames: {total_frames}")
        
        # Preparar arquivo de saída
        timestamp = int(time.time())
        output_filename = f"processed_{video_path.stem}_{timestamp}.mp4"
        output_path = RESULTS_FOLDER / output_filename
        
        # Codec para MP4
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        
        if not out.isOpened():
            return None, f"Não foi possível criar arquivo de saída: {output_path}", None
        
        # Estatísticas
        stats = {
            "jogadores_max": 0,
            "jogadores_media": 0,
            "bolas_detectadas": 0,
            "total_frames": total_frames,
            "fps": fps,
            "resolucao": f"{width}x{height}",
            "tempo_processamento": 0,
            "frames_processados": 0
        }
        
        jogadores_por_frame = []
        frame_count = 0
        start_time = time.time()
        
        print("🔍 Processando frames...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Detecção com YOLOv8 (apenas classes 0=pessoa e 32=bola esportiva)
            try:
                results = MODEL(frame, conf=confidence, classes=[0, 32], verbose=False)
            except Exception as e:
                print(f"⚠️  Erro na detecção frame {frame_count}: {e}")
                results = []
            
            jogadores = 0
            bolas = 0
            
            # Contar detecções
            if results and len(results) > 0:
                for result in results:
                    if result.boxes is not None:
                        for box in result.boxes:
                            cls = int(box.cls[0])
                            if cls == 0:  # Pessoa (jogador)
                                jogadores += 1
                            elif cls == 32:  # Bola esportiva
                                bolas += 1
            
            jogadores_por_frame.append(jogadores)
            stats["jogadores_max"] = max(stats["jogadores_max"], jogadores)
            stats["bolas_detectadas"] += bolas
            
            # Anotar frame com resultados
            if results and len(results) > 0:
                annotated_frame = results[0].plot()
            else:
                annotated_frame = frame.copy()
            
            # Adicionar overlay com informações
            cv2.putText(annotated_frame, f"Jogadores: {jogadores}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Bolas: {bolas}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Frame: {frame_count}/{total_frames}", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(annotated_frame, f"Conf: {confidence}", (width - 100, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            out.write(annotated_frame)
            
            # Progresso a cada 10% ou 100 frames
            if frame_count % max(1, min(100, total_frames // 10)) == 0:
                progress = (frame_count / total_frames) * 100
                elapsed = time.time() - start_time
                print(f"   📈 {progress:.1f}% ({frame_count}/{total_frames}) - {elapsed:.1f}s")
        
        # Finalizar
        cap.release()
        out.release()
        
        stats["tempo_processamento"] = time.time() - start_time
        stats["frames_processados"] = frame_count
        
        if jogadores_por_frame:
            stats["jogadores_media"] = sum(jogadores_por_frame) / len(jogadores_por_frame)
        
        # Salvar estatísticas em JSON
        stats_filename = output_path.with_suffix('.json')
        with open(stats_filename, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Análise concluída: {frame_count} frames processados em {stats['tempo_processamento']:.1f}s")
        print(f"   📁 Vídeo processado: {output_path.name}")
        print(f"   📊 Estatísticas: {stats_filename.name}")
        
        return output_path, stats, None
        
    except Exception as e:
        error_msg = f"Erro durante análise: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return None, error_msg, None

# ===== HTML INTERFACE =====
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analisador de Futebol - YOLOv8</title>
    <style>
        :root {
            --primary: #4CAF50;
            --primary-dark: #45a049;
            --secondary: #2196F3;
            --light: #f8f9fa;
            --dark: #343a40;
            --success: #d4edda;
            --error: #f8d7da;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: var(--dark);
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
            max-width: 800px;
            margin: 0 auto;
            line-height: 1.6;
        }
        
        .status-bar {
            background: var(--light);
            padding: 15px 40px;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9rem;
        }
        
        .content {
            padding: 40px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
        }
        
        @media (max-width: 992px) {
            .content {
                grid-template-columns: 1fr;
            }
        }
        
        .section {
            background: var(--light);
            padding: 30px;
            border-radius: 15px;
            border: 2px solid #dee2e6;
        }
        
        .upload-section {
            border-style: dashed;
            border-color: var(--primary);
        }
        
        .section h2 {
            color: var(--dark);
            margin-bottom: 25px;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #495057;
            font-weight: 600;
        }
        
        .file-input {
            width: 100%;
            padding: 15px;
            border: 2px solid #ced4da;
            border-radius: 10px;
            background: white;
            font-size: 1rem;
            transition: border-color 0.3s;
        }
        
        .file-input:hover {
            border-color: var(--primary);
        }
        
        .slider-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #ced4da;
        }
        
        .slider-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .slider-value {
            background: var(--primary);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            min-width: 60px;
            text-align: center;
        }
        
        input[type="range"] {
            width: 100%;
            height: 8px;
            -webkit-appearance: none;
            background: #e9ecef;
            border-radius: 4px;
            outline: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 24px;
            height: 24px;
            background: var(--primary);
            border-radius: 50%;
            cursor: pointer;
            border: 3px solid white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        
        .btn {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            border: none;
            padding: 16px 32px;
            font-size: 1.1rem;
            font-weight: 600;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }
        
        .btn:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }
        
        .btn:disabled {
            background: #cccccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 30px;
        }
        
        .spinner {
            border: 4px solid rgba(0,0,0,0.1);
            border-top: 4px solid var(--primary);
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .progress-container {
            width: 100%;
            background: #e9ecef;
            border-radius: 10px;
            margin: 20px 0;
            overflow: hidden;
        }
        
        .progress-bar {
            height: 20px;
            background: linear-gradient(90deg, var(--primary), #8BC34A);
            width: 0%;
            transition: width 0.5s ease;
            border-radius: 10px;
        }
        
        .progress-text {
            font-size: 0.9rem;
            color: #6c757d;
            margin-bottom: 10px;
        }
        
        .status-message {
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            display: none;
        }
        
        .status-success {
            background: var(--success);
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .status-error {
            background: var(--error);
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            border-left: 5px solid var(--primary);
            transition: transform 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-value {
            font-size: 2.2rem;
            font-weight: bold;
            color: var(--primary);
            margin-bottom: 5px;
            line-height: 1;
        }
        
        .stat-label {
            color: #6c757d;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }
        
        .download-section {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 30px;
        }
        
        .download-btn {
            background: linear-gradient(135deg, var(--secondary) 0%, #1976D2 100%);
            color: white;
            text-decoration: none;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            transition: all 0.3s;
        }
        
        .download-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(33, 150, 243, 0.3);
        }
        
        .video-info {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }
        
        .video-info h3 {
            margin-bottom: 15px;
            color: var(--dark);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .video-info p {
            margin-bottom: 8px;
            color: #495057;
        }
        
        .icon {
            font-size: 1.5rem;
        }
        
        .model-status {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        
        .model-loading {
            background: #fff3cd;
            color: #856404;
        }
        
        .model-ready {
            background: #d4edda;
            color: #155724;
        }
        
        .model-error {
            background: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                <span class="icon">⚽</span>
                Analisador de Futebol Inteligente
            </h1>
            <p>Faça upload de vídeos de partidas para análise automática de jogadores e bola usando IA (YOLOv8)</p>
        </div>
        
        <div class="status-bar">
            <div class="status-item">
                <span>Status do Modelo:</span>
                <span id="modelStatus" class="model-status model-loading">🔄 Carregando...</span>
            </div>
            <div class="status-item">
                <span>📁 Uploads:</span>
                <span id="uploadCount">0 arquivos</span>
            </div>
            <div class="status-item">
                <span>📊 Resultados:</span>
                <span id="resultCount">0 análises</span>
            </div>
        </div>
        
        <div class="content">
            <!-- Seção de Upload -->
            <div class="section upload-section">
                <h2><span class="icon">📤</span> Upload do Vídeo</h2>
                
                <form id="uploadForm" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="videoFile">Selecione o vídeo:</label>
                        <input type="file" class="file-input" id="videoFile" name="video" 
                               accept="video/*" required>
                        <small style="color: #6c757d; display: block; margin-top: 5px;">
                            Formatos suportados: MP4, AVI, MOV, MKV, WEBM (máx. 500MB)
                        </small>
                    </div>
                    
                    <div class="form-group">
                        <label for="confidence">Sensibilidade da Detecção:</label>
                        <div class="slider-container">
                            <div class="slider-header">
                                <span>Menos sensível (mais preciso)</span>
                                <span class="slider-value" id="confValue">0.5</span>
                                <span>Mais sensível (mais detecções)</span>
                            </div>
                            <input type="range" id="confidence" name="confidence" 
                                   min="0.1" max="0.9" step="0.05" value="0.5">
                            <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                                <small style="color: #6c757d;">0.1</small>
                                <small style="color: #6c757d;">0.9</small>
                            </div>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn" id="analyzeBtn" disabled>
                        <span class="icon">🔍</span>
                        ANALISAR VÍDEO
                    </button>
                </form>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p style="font-size: 1.1rem; margin-bottom: 15px;">Processando vídeo...</p>
                    <p style="color: #6c757d; margin-bottom: 20px;">Isso pode levar alguns minutos dependendo do tamanho do vídeo.</p>
                    
                    <div class="progress-container">
                        <div class="progress-bar" id="progress"></div>
                    </div>
                    <p class="progress-text" id="progressText">0% - Iniciando...</p>
                    
                    <div style="display: flex; justify-content: center; gap: 20px; margin-top: 20px;">
                        <div style="text-align: center;">
                            <div style="font-size: 1.2rem; font-weight: bold;" id="currentFrame">0</div>
                            <small style="color: #6c757d;">Frames</small>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 1.2rem; font-weight: bold;" id="elapsedTime">0s</div>
                            <small style="color: #6c757d;">Tempo</small>
                        </div>
                    </div>
                </div>
                
                <div class="status-message" id="statusMessage"></div>
            </div>
            
            <!-- Seção de Resultados -->
            <div class="section">
                <h2><span class="icon">📊</span> Resultados da Análise</h2>
                
                <div id="resultsContent">
                    <div style="text-align: center; padding: 40px; color: #6c757d;">
                        <div style="font-size: 4rem; margin-bottom: 20px;">⚽</div>
                        <h3 style="margin-bottom: 15px; color: #495057;">Bem-vindo ao Analisador de Futebol!</h3>
                        <p>Faça upload de um vídeo de futebol para começar a análise.</p>
                        <p style="margin-top: 10px; font-size: 0.9rem;">
                            O sistema detectará automaticamente jogadores e bolas usando IA.
                        </p>
                    </div>
                </div>
                
                <div class="download-section" id="downloadSection" style="display: none;">
                    <a href="#" class="download-btn" id="downloadVideo">
                        <span class="icon">🎬</span>
                        Baixar Vídeo Processado
                    </a>
                    <a href="#" class="download-btn" id="downloadStats">
                        <span class="icon">📈</span>
                        Baixar Estatísticas
                    </a>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Elementos do DOM
        const confidenceSlider = document.getElementById('confidence');
        const confValue = document.getElementById('confValue');
        const uploadForm = document.getElementById('uploadForm');
        const analyzeBtn = document.getElementById('analyzeBtn');
        const loadingDiv = document.getElementById('loading');
        const statusDiv = document.getElementById('statusMessage');
        const resultsDiv = document.getElementById('resultsContent');
        const downloadSection = document.getElementById('downloadSection');
        const progressBar = document.getElementById('progress');
        const progressText = document.getElementById('progressText');
        const currentFrameEl = document.getElementById('currentFrame');
        const elapsedTimeEl = document.getElementById('elapsedTime');
        const modelStatusEl = document.getElementById('modelStatus');
        const uploadCountEl = document.getElementById('uploadCount');
        const resultCountEl = document.getElementById('resultCount');
        const videoFileInput = document.getElementById('videoFile');
        
        // Estado da aplicação
        let isProcessing = false;
        let progressInterval;
        let startTime;
        
        // ===== FUNÇÕES UTILITÁRIAS =====
        
        function updateModelStatus() {
            fetch('/api/health')
                .then(response => response.json())
                .then(data => {
                    if (data.model_loaded) {
                        modelStatusEl.textContent = '✅ Pronto';
                        modelStatusEl.className = 'model-status model-ready';
                        analyzeBtn.disabled = false;
                    } else if (data.model_error) {
                        modelStatusEl.textContent = '❌ Erro';
                        modelStatusEl.className = 'model-status model-error';
                    } else {
                        modelStatusEl.textContent = '🔄 Carregando...';
                        modelStatusEl.className = 'model-status model-loading';
                        // Verificar novamente em 3 segundos
                        setTimeout(updateModelStatus, 3000);
                    }
                    
                    // Atualizar contadores
                    uploadCountEl.textContent = data.upload_count + ' arquivos';
                    resultCountEl.textContent = data.result_count + ' análises';
                })
                .catch(error => {
                    console.error('Erro ao verificar status:', error);
                    setTimeout(updateModelStatus, 5000);
                });
        }
        
        function showStatus(message, type = 'success') {
            statusDiv.textContent = message;
            statusDiv.className = `status-message status-${type}`;
            statusDiv.style.display = 'block';
            
            // Auto-esconder após 10 segundos para sucesso, 15 para erro
            const timeout = type === 'success' ? 10000 : 15000;
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, timeout);
        }
        
        function formatBytes(bytes, decimals = 2) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const dm = decimals < 0 ? 0 : decimals;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
        }
        
        function formatTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes}m ${secs}s`;
            } else if (minutes > 0) {
                return `${minutes}m ${secs}s`;
            } else {
                return `${secs}s`;
            }
        }
        
        // ===== EVENT LISTENERS =====
        
        // Atualizar valor do slider
        confidenceSlider.addEventListener('input', function() {
            confValue.textContent = parseFloat(this.value).toFixed(2);
        });
        
        // Mostrar informações do arquivo selecionado
        videoFileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const file = this.files[0];
                showStatus(
                    `Arquivo selecionado: ${file.name} (${formatBytes(file.size)})`,
                    'success'
                );
            }
        });
        
        // Submissão do formulário
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            if (isProcessing) {
                showStatus('Já há uma análise em andamento. Aguarde.', 'error');
                return;
            }
            
            const fileInput = document.getElementById('videoFile');
            if (!fileInput.files[0]) {
                showStatus('Por favor, selecione um vídeo para análise.', 'error');
                return;
            }
            
            // Verificar tamanho do arquivo (limite de 500MB)
            const maxSize = 500 * 1024 * 1024; // 500MB
            if (fileInput.files[0].size > maxSize) {
                showStatus('Arquivo muito grande. Máximo permitido: 500MB', 'error');
                return;
            }
            
            const formData = new FormData(this);
            const confidence = confidenceSlider.value;
            
            // Configurar interface para processamento
            isProcessing = true;
            analyzeBtn.disabled = true;
            loadingDiv.style.display = 'block';
            statusDiv.style.display = 'none';
            downloadSection.style.display = 'none';
            
            // Inicializar progresso
            progressBar.style.width = '0%';
            progressText.textContent = '0% - Enviando arquivo...';
            currentFrameEl.textContent = '0';
            elapsedTimeEl.textContent = '0s';
            startTime = Date.now();
            
            // Simular progresso durante upload e processamento
            let simulatedProgress = 0;
            progressInterval = setInterval(() => {
                const elapsed = (Date.now() - startTime) / 1000;
                elapsedTimeEl.textContent = formatTime(elapsed);
                
                if (simulatedProgress < 95) {
                    simulatedProgress += 0.5;
                    progressBar.style.width = simulatedProgress + '%';
                    progressText.textContent = simulatedProgress.toFixed(0) + '% - Processando...';
                    
                    // Simular frames processados
                    if (simulatedProgress % 10 === 0) {
                        currentFrameEl.textContent = Math.floor(simulatedProgress * 100);
                    }
                }
            }, 500);
            
            try {
                // Enviar para API
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    body: formData
                });
                
                clearInterval(progressInterval);
                
                if (response.ok) {
                    const result = await response.json();
                    
                    if (result.success) {
                        // Completa a barra de progresso
                        progressBar.style.width = '100%';
                        progressText.textContent = '100% - Concluído!';
                        
                        showStatus('Análise concluída com sucesso!', 'success');
                        displayResults(result);
                        
                        // Configurar links de download
                        document.getElementById('downloadVideo').href = `/download/${result.video_file}`;
                        document.getElementById('downloadVideo').download = result.video_file;
                        document.getElementById('downloadStats').href = `/download/${result.stats_file}`;
                        document.getElementById('downloadStats').download = result.stats_file;
                        
                        downloadSection.style.display = 'grid';
                    } else {
                        showStatus(`Erro na análise: ${result.message}`, 'error');
                    }
                } else {
                    const errorText = await response.text();
                    showStatus(`Erro do servidor: ${errorText}`, 'error');
                }
            } catch (error) {
                showStatus(`Erro de conexão: ${error.message}`, 'error');
            } finally {
                // Resetar interface
                isProcessing = false;
                analyzeBtn.disabled = false;
                loadingDiv.style.display = 'none';
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 1000);
                
                // Atualizar status do modelo
                updateModelStatus();
            }
        });
        
        // ===== FUNÇÕES DE EXIBIÇÃO =====
        
        function displayResults(result) {
            const stats = result.statistics;
            
            resultsDiv.innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">${stats.jogadores_max}</div>
                        <div class="stat-label">Jogadores Máximo</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.jogadores_media.toFixed(1)}</div>
                        <div class="stat-label">Jogadores Média</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.bolas_detectadas}</div>
                        <div class="stat-label">Bolas Detectadas</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.frames_processados || stats.total_frames}</div>
                        <div class="stat-label">Frames Processados</div>
                    </div>
                </div>
                
                <div class="video-info">
                    <h3><span class="icon">📋</span> Informações do Vídeo</h3>
                    <p><strong>Resolução:</strong> ${stats.resolucao}</p>
                    <p><strong>FPS:</strong> ${stats.fps}</p>
                    <p><strong>Total de Frames:</strong> ${stats.total_frames}</p>
                    <p><strong>Tempo de Processamento:</strong> ${stats.tempo_processamento ? stats.tempo_processamento.toFixed(1) + 's' : 'N/A'}</p>
                    <p><strong>Tempo Estimado do Vídeo:</strong> ${Math.round(stats.total_frames / stats.fps)} segundos</p>
                </div>
            `;
        }
        
        // ===== INICIALIZAÇÃO =====
        
        // Atualizar status do modelo periodicamente
        updateModelStatus();
        setInterval(updateModelStatus, 30000); // Atualizar a cada 30 segundos
        
        // Verificar se há resultados anteriores ao carregar a página
        window.addEventListener('load', function() {
            // Tentar carregar último resultado se existir
            const lastResult = localStorage.getItem('lastAnalysisResult');
            if (lastResult) {
                try {
                    const result = JSON.parse(lastResult);
                    if (result && result.success) {
                        displayResults(result);
                        downloadSection.style.display = 'grid';
                    }
                } catch (e) {
                    // Ignorar erro
                }
            }
        });
    </script>
</body>
</html>
"""

# ===== ENDPOINTS DA API =====

@app.get("/", response_class=HTMLResponse)
async def home():
    """Página inicial com interface web"""
    return HTMLResponse(content=HTML_TEMPLATE)

@app.get("/api/health")
async def health_check():
    """Health check da API e status do modelo"""
    # Contar arquivos nos diretórios
    upload_count = len(list(UPLOAD_FOLDER.glob("*"))) if UPLOAD_FOLDER.exists() else 0
    result_count = len(list(RESULTS_FOLDER.glob("*.mp4"))) if RESULTS_FOLDER.exists() else 0
    
    return {
        "status": "healthy",
        "model_loaded": MODEL_LOADED,
        "model_loading": MODEL_LOADING,
        "model_error": MODEL_ERROR,
        "upload_folder": str(UPLOAD_FOLDER.absolute()),
        "results_folder": str(RESULTS_FOLDER.absolute()),
        "upload_count": upload_count,
        "result_count": result_count,
        "system": "Analisador de Vídeos de Futebol com YOLOv8",
        "timestamp": time.time()
    }

@app.post("/api/analyze")
async def api_analyze(
    video: UploadFile = File(...),
    confidence: float = Form(0.5)
):
    """Endpoint para análise de vídeo"""
    try:
        # Validar entrada
        if not video.filename:
            raise HTTPException(status_code=400, detail="Nenhum arquivo selecionado")
        
        if not allowed_file(video.filename):
            raise HTTPException(
                status_code=400,
                detail=f"Formato não suportado. Use: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Verificar se o modelo está carregado
        if not MODEL_LOADED:
            if MODEL_LOADING:
                raise HTTPException(
                    status_code=503, 
                    detail="Modelo ainda está carregando. Aguarde alguns segundos e tente novamente."
                )
            elif MODEL_ERROR:
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro ao carregar modelo: {MODEL_ERROR}"
                )
            else:
                raise HTTPException(
                    status_code=503,
                    detail="Modelo não disponível. Tente novamente em alguns segundos."
                )
        
        # Criar nome único para o arquivo
        file_id = uuid.uuid4().hex[:8]
        original_filename = Path(video.filename).stem
        filename = f"{original_filename}_{file_id}{Path(video.filename).suffix}"
        video_path = UPLOAD_FOLDER / filename
        
        # Salvar arquivo
        print(f"💾 Salvando arquivo: {filename}")
        with open(video_path, "wb") as buffer:
            content = await video.read()
            buffer.write(content)
        
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"📦 Arquivo salvo: {file_size_mb:.2f} MB")
        
        # Analisar vídeo
        print(f"🔍 Iniciando análise com confiança: {confidence}")
        output_path, stats, error = analyze_video_safe(video_path, confidence)
        
        if error:
            # Tentar limpar arquivo em caso de erro
            try:
                video_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail=error)
        
        if not output_path or not output_path.exists():
            raise HTTPException(status_code=500, detail="Erro ao processar vídeo: arquivo de saída não criado")
        
        return {
            "success": True,
            "message": "Análise concluída com sucesso!",
            "video_file": output_path.name,
            "stats_file": output_path.with_suffix('.json').name,
            "statistics": stats,
            "original_filename": video.filename,
            "file_size_mb": round(file_size_mb, 2),
            "processing_time": stats.get("tempo_processamento", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Erro interno: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download de arquivos processados"""
    # Primeiro tenta no diretório de resultados
    file_path = RESULTS_FOLDER / filename
    
    # Se não encontrar, tenta no diretório de uploads
    if not file_path.exists():
        file_path = UPLOAD_FOLDER / filename
    
    if file_path.exists():
        # Verificar tipo de arquivo para content-type apropriado
        if filename.lower().endswith('.mp4'):
            media_type = 'video/mp4'
        elif filename.lower().endswith('.json'):
            media_type = 'application/json'
        elif filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
            media_type = 'image/jpeg'
        elif filename.lower().endswith('.png'):
            media_type = 'image/png'
        else:
            media_type = 'application/octet-stream'
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )
    else:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

@app.get("/api/uploads")
async def list_uploads():
    """Lista arquivos disponíveis para download"""
    files = []
    
    # Listar arquivos de upload
    if UPLOAD_FOLDER.exists():
        for file_path in UPLOAD_FOLDER.glob("*"):
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "size": os.path.getsize(file_path),
                    "type": "upload",
                    "path": f"/download/{file_path.name}"
                })
    
    # Listar arquivos de resultados
    if RESULTS_FOLDER.exists():
        for file_path in RESULTS_FOLDER.glob("*"):
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "size": os.path.getsize(file_path),
                    "type": "result",
                    "path": f"/download/{file_path.name}"
                })
    
    return {"files": files}

@app.delete("/api/uploads/{filename}")
async def delete_file(filename: str):
    """Remove um arquivo"""
    file_path = RESULTS_FOLDER / filename
    if not file_path.exists():
        file_path = UPLOAD_FOLDER / filename
    
    if file_path.exists():
        try:
            file_path.unlink()
            return {"success": True, "message": f"Arquivo {filename} removido"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao remover arquivo: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

# ===== INICIALIZAÇÃO DO SERVIDOR =====

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ANALISADOR DE VÍDEOS DE FUTEBOL - YOLOv8")
    print("=" * 60)
    print(f"📁 Diretório de Uploads: {UPLOAD_FOLDER.absolute()}")
    print(f"📁 Diretório de Resultados: {RESULTS_FOLDER.absolute()}")
    print(f"🌐 Interface Web: http://0.0.0.0:5000")
    print(f"📚 API Health Check: http://0.0.0.0:5000/api/health")
    print(f"🔄 Carregando modelo YOLOv8...")
    print("=" * 60)
    
    # Iniciar servidor
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info",
        access_log=True
    )
