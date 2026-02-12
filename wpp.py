import os
import sys
import time
import platform
import datetime
import requests
import ctypes
from pathlib import Path
import subprocess
from PIL import Image
import io

class GOES16ImageDownloader:
    BASE_URL = "https://cdn.star.nesdis.noaa.gov/GOES19/ABI/FD"
    SAVE_WALLPAPER = Path("Pictures/Wallpapers/wallpaper.jpg")
    SAVE_SHARE_DIR = Path("Pictures/sky")

    def __init__(self, resolution="1808x1808.jpg", delay=2):
        self.resolution = resolution
        self.delay = delay
        self.system = platform.system()
        self.is_wsl = self._is_wsl()
        
        # Se estiver no WSL, configurar caminhos do Windows
        if self.is_wsl:
            self.SAVE_WALLPAPER, self.SAVE_SHARE_DIR = self._setup_windows_paths()
            # No WSL, as pastas já foram criadas via PowerShell
            # Apenas verificar se existem
            if not self.SAVE_WALLPAPER.parent.exists():
                print(f"⚠️ Aviso: Pasta não existe: {self.SAVE_WALLPAPER.parent}")
            if not self.SAVE_SHARE_DIR.exists():
                print(f"⚠️ Aviso: Pasta não existe: {self.SAVE_SHARE_DIR}")
        else:
            # No Linux/macOS/Windows nativo, criar pastas normalmente
            self.SAVE_WALLPAPER.parent.mkdir(parents=True, exist_ok=True)
            self.SAVE_SHARE_DIR.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Wallpaper será salvo em: {self.SAVE_WALLPAPER.resolve()}")
        print(f"📁 Imagens compartilhadas em: {self.SAVE_SHARE_DIR.resolve()}")
    
    def _is_wsl(self):
        """Detecta se está rodando no WSL"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower() or 'wsl' in f.read().lower()
        except:
            return False
    
    def _get_windows_username(self):
        """Obtém o nome de usuário do Windows"""
        # Primeiro, tentar detectar do caminho WSL (mais confiável)
        try:
            # Verificar se há acesso a /mnt/c/Users
            users_dir = Path('/mnt/c/Users')
            if users_dir.exists():
                # Pegar o primeiro diretório que não seja Default, Public, etc
                excluded = ['Default', 'Public', 'All Users', 'Default User']
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir() and user_dir.name not in excluded:
                        return user_dir.name
        except Exception as e:
            print(f"⚠️ Erro ao listar usuários: {e}")
        
        # Tentar via PowerShell
        try:
            result = subprocess.run(
                ['powershell.exe', '-Command', '$env:USERNAME'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                username = result.stdout.strip()
                # Verificar se o caminho existe
                user_path = Path(f"/mnt/c/Users/{username}")
                if user_path.exists():
                    return username
        except:
            pass
        
        # Tentar via variável de ambiente
        try:
            username = os.environ.get('USERNAME') or os.environ.get('USER')
            if username:
                user_path = Path(f"/mnt/c/Users/{username}")
                if user_path.exists():
                    return username
        except:
            pass
        
        return None
    
    def _create_windows_directories(self, windows_path: str):
        """Cria diretórios no Windows via PowerShell quando estiver no WSL"""
        try:
            # Converter caminho /mnt/c/... para C:\...
            if windows_path.startswith('/mnt/'):
                parts = windows_path.split('/')
                if len(parts) >= 4:
                    drive = parts[2].upper()
                    rest = '\\'.join(parts[3:])
                    win_path = f"{drive}:\\{rest}"
                else:
                    return False
            else:
                win_path = windows_path.replace('/', '\\')
            
            # Criar diretório via PowerShell (Force cria todos os pais necessários)
            ps_command = f'$path = "{win_path}"; if (-not (Test-Path $path)) {{ New-Item -ItemType Directory -Force -Path $path | Out-Null }}; if (Test-Path $path) {{ Write-Host "OK" }} else {{ Write-Host "FAIL" }}'
            result = subprocess.run(
                ['powershell.exe', '-Command', ps_command],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0 and "OK" in result.stdout:
                return True
            else:
                print(f"⚠️ Falha ao criar: {win_path}")
                if result.stderr:
                    print(f"   Erro: {result.stderr}")
                return False
        except Exception as e:
            print(f"⚠️ Erro ao criar diretório via PowerShell: {e}")
            return False
    
    def _setup_windows_paths(self):
        """Configura caminhos para salvar no Windows quando estiver no WSL"""
        username = self._get_windows_username()
        
        if username:
            # Verificar se o caminho do usuário existe (case-insensitive)
            user_path = Path(f"/mnt/c/Users/{username}")
            if not user_path.exists():
                print(f"⚠️ Caminho do usuário não encontrado: {user_path}")
                print(f"💡 Tentando encontrar com case diferente...")
                # Tentar encontrar com case diferente
                users_dir = Path('/mnt/c/Users')
                if users_dir.exists():
                    excluded = ['Default', 'Public', 'All Users', 'Default User']
                    available_users = [d.name for d in users_dir.iterdir() 
                                     if d.is_dir() and d.name not in excluded]
                    
                    # Buscar case-insensitive
                    found_user = None
                    for user in available_users:
                        if user.lower() == username.lower():
                            found_user = user
                            break
                    
                    if found_user:
                        username = found_user
                        print(f"✅ Usuário encontrado (case diferente): {username}")
                        user_path = Path(f"/mnt/c/Users/{username}")
                    elif available_users:
                        username = available_users[0]
                        print(f"📋 Usuários disponíveis: {', '.join(available_users)}")
                        print(f"✅ Usando: {username}")
                        user_path = Path(f"/mnt/c/Users/{username}")
                    else:
                        print(f"❌ Nenhum usuário válido encontrado")
                        return Path("Pictures/Wallpapers/wallpaper.jpg"), Path("Pictures/sky")
            
            # Usar caminho do Windows: /mnt/c/Users/username/Pictures/...
            windows_pictures = user_path / "Pictures"
            wallpaper_path = windows_pictures / "Wallpapers" / "wallpaper.jpg"
            share_path = windows_pictures / "sky"
            
            print(f"🪟 WSL detectado - usando caminhos do Windows")
            print(f"👤 Usuário Windows: {username}")
            
            # Criar pastas via PowerShell se necessário
            print(f"📁 Criando pastas no Windows...")
            if self._create_windows_directories(str(wallpaper_path.parent)):
                print(f"✅ Pasta criada: {wallpaper_path.parent}")
            if self._create_windows_directories(str(share_path)):
                print(f"✅ Pasta criada: {share_path}")
            
            return wallpaper_path, share_path
        else:
            # Fallback: usar caminho padrão do Linux
            print(f"⚠️ Não foi possível detectar usuário do Windows, usando caminho Linux padrão")
            return Path("Pictures/Wallpapers/wallpaper.jpg"), Path("Pictures/sky")

    def get_latest_timestamp(self, offset_minutes=30):
        now = datetime.datetime.utcnow() - datetime.timedelta(minutes=offset_minutes)
        return now.strftime("%Y%j%H") + now.strftime("%M")[0] + "0"

    def build_url(self, source, timestamp):
        return f"{self.BASE_URL}/{source}/{timestamp}_GOES19-ABI-FD-{source}-{self.resolution}"
    
    def resize_image(self, image_data: bytes, scale_factor: float = 0.65) -> bytes:
        """Redimensiona a imagem mantendo a proporção"""
        try:
            # Abrir a imagem
            img = Image.open(io.BytesIO(image_data))
            
            # Calcular novo tamanho (35% menor = 65% do original)
            original_width, original_height = img.size
            new_width = int(original_width * scale_factor)
            new_height = int(original_height * scale_factor)
            
            # Redimensionar mantendo qualidade
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Converter de volta para bytes
            output = io.BytesIO()
            resized_img.save(output, format='JPEG', quality=95, optimize=True)
            output.seek(0)
            
            print(f"📐 Imagem redimensionada: {original_width}x{original_height} → {new_width}x{new_height} ({scale_factor*100:.0f}%)")
            return output.getvalue()
        except Exception as e:
            print(f"⚠️ Erro ao redimensionar imagem: {e}")
            return image_data  # Retornar original se houver erro

    def set_wallpaper(self, path: Path):
        full_path = path.resolve()
        
        # Verificar se o arquivo existe
        if not full_path.exists():
            print(f"❌ Arquivo não encontrado: {full_path}")
            return
        
        print(f"🖼️ Tentando definir wallpaper: {full_path}")
        print(f"📋 Sistema detectado: {self.system}, WSL: {self.is_wsl}")
        
        try:
            # Se estiver no WSL, tentar definir no Windows primeiro
            if self.is_wsl:
                print("🔍 Detectado WSL, tentando definir wallpaper no Windows...")
                
                # Converter caminho /mnt/c/... para C:\...
                path_str = str(full_path)
                if path_str.startswith('/mnt/'):
                    # Converter /mnt/c/Users/... para C:\Users\...
                    parts = path_str.split('/')
                    if len(parts) >= 4:
                        drive = parts[2].upper()
                        rest = '\\'.join(parts[3:])
                        windows_path = f"{drive}:\\{rest}"
                    else:
                        # Tentar usar wslpath como fallback
                        try:
                            result = subprocess.run(['wslpath', '-w', path_str], 
                                                  capture_output=True, text=True, timeout=2)
                            if result.returncode == 0:
                                windows_path = result.stdout.strip()
                            else:
                                windows_path = path_str
                        except:
                            windows_path = path_str
                else:
                    # Tentar usar wslpath
                    try:
                        result = subprocess.run(['wslpath', '-w', path_str], 
                                              capture_output=True, text=True, timeout=2)
                        if result.returncode == 0:
                            windows_path = result.stdout.strip()
                        else:
                            windows_path = path_str
                    except:
                        windows_path = path_str
                
                print(f"🔄 Caminho convertido: {windows_path}")
                
                # Tentar via PowerShell
                ps_script = f'''
$code = @"
using System;
using System.Runtime.InteropServices;
public class Wallpaper {{
    [DllImport("user32.dll", CharSet=CharSet.Auto)]
    public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
}}
"@
Add-Type -TypeDefinition $code
$result = [Wallpaper]::SystemParametersInfo(20, 0, "{windows_path}", 3)
if ($result -eq 0) {{
    Write-Host "Erro: Falha ao definir wallpaper"
    exit 1
}} else {{
    Write-Host "Sucesso: Wallpaper definido"
    exit 0
}}
'''
                result = subprocess.run(['powershell.exe', '-Command', ps_script], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"✅ Wallpaper definido no Windows via WSL")
                    print(f"📁 Caminho Windows: {windows_path}")
                    return
                else:
                    print(f"⚠️ PowerShell retornou código: {result.returncode}")
                    if result.stderr:
                        print(f"⚠️ Erro: {result.stderr}")
                    if result.stdout:
                        print(f"⚠️ Saída: {result.stdout}")
                    print(f"⚠️ Tentando outros métodos...")
            
            if self.system == "Windows":
                # Para Windows nativo
                result = ctypes.windll.user32.SystemParametersInfoW(20, 0, str(full_path), 3)
                if result:
                    print(f"✅ Wallpaper definido no Windows: {full_path}")
                else:
                    print(f"⚠️ Falha ao definir wallpaper no Windows")
            elif self.system == "Darwin":  # macOS
                result = subprocess.run([
                    "osascript", "-e",
                    f'tell application "System Events" to set picture of every desktop to "{full_path}"'
                ], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"✅ Wallpaper definido no macOS: {full_path}")
                else:
                    print(f"⚠️ Erro ao definir wallpaper no macOS: {result.stderr}")
            elif self.system == "Linux":
                # Tentar gsettings (GNOME)
                result = subprocess.run([
                    "gsettings", "set",
                    "org.gnome.desktop.background",
                    "picture-uri", f"file://{full_path}"
                ], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"✅ Wallpaper definido no Linux (GNOME): {full_path}")
                else:
                    print(f"⚠️ gsettings não disponível, tentando alternativas...")
                    # Tentar feh (comum em ambientes leves)
                    result2 = subprocess.run(["which", "feh"], capture_output=True)
                    if result2.returncode == 0:
                        subprocess.run(["feh", "--bg-scale", str(full_path)])
                        print(f"✅ Wallpaper definido com feh: {full_path}")
                    else:
                        print(f"⚠️ Nenhum método disponível para definir wallpaper no Linux")
                        print(f"💡 Arquivo salvo em: {full_path}")
                        print(f"💡 Você pode definir manualmente ou usar: gsettings set org.gnome.desktop.background picture-uri file://{full_path}")
        except Exception as e:
            print(f"❌ Erro ao definir wallpaper: {e}")
            print(f"💡 Arquivo salvo em: {full_path}")
            import traceback
            traceback.print_exc()

def download_image(self, source: str):
        timestamp = self.get_latest_timestamp()
        url = self.build_url(source, timestamp)

        print(f"🔍 Verificando {source}...")
        try:
            print(f"Acessando URL: {url}")
            response = requests.get(url, stream=True, timeout=10)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                # Redimensionar a imagem (35% menor = 65% do tamanho original)
                resized_content = self.resize_image(response.content, scale_factor=0.65)
                
                wallpaper_path = self.SAVE_WALLPAPER.resolve()
                with open(self.SAVE_WALLPAPER, 'wb') as f:
                    f.write(resized_content)

                share_path = self.SAVE_SHARE_DIR / f"{source}.jpg"
                with open(share_path, 'wb') as f:
                    f.write(resized_content)

              print(f"✅ {source} baixado e redimensionado.")
              print(f"📁 Arquivo salvo em: {wallpaper_path}")
              self.set_wallpaper(self.SAVE_WALLPAPER)
          else:
              print(f"❌ {source} não encontrado: HTTP {response.status_code}")
      except Exception as e:
          print(f"⚠️ Erro ao baixar {source}: {e}")

    def run_sequence(self, sources: list[str]):
        for source in sources:
            self.download_image(source)
            time.sleep(self.delay)

if __name__ == "__main__":
    downloader = GOES16ImageDownloader()

    # Atalho: permitir escolher uma imagem/banda específica pela linha de comando
    #
    # Exemplos:
    #   python wpp.py GEOCOLOR      → se já existir Pictures/sky/GEOCOLOR.jpg, só troca o papel de parede
    #                                 (sem baixar de novo). Se não existir, baixa apenas essa banda.
    #   python wpp.py 10            → mesmo comportamento, mas para a banda "10".
    if len(sys.argv) > 1:
        source = sys.argv[1]
        image_path = downloader.SAVE_SHARE_DIR / f"{source}.jpg"

        if image_path.exists():
            print(f"🎯 Usando imagem já baixada: {image_path}")
            downloader.set_wallpaper(image_path)
        else:
            print(f"ℹ️ Imagem {source}.jpg não encontrada em {downloader.SAVE_SHARE_DIR}, baixando agora...")
            downloader.download_image(source)
    else:
        bands = ['AirMass', 'DayCloudPhase', 'Sandwich', '07', '08', '09', '10', '11', '12', '15', 'GEOCOLOR']
        downloader.run_sequence(bands)