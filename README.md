# 🌎 GOES-16 Dynamic Wallpaper for Windows

Este script baixa imagens atualizadas do satélite GOES-16 (como AirMass, GEOCOLOR, etc), salva localmente e atualiza automaticamente o papel de parede do Linux, MacOs ou Windows, exibindo cada banda sequencialmente.

---

## ✅ Requisitos

- Python 3.8+
- Biblioteca `requests` instalada

```bash
pip install requests
```

# wpp
This is for automate my wallpaper with images obtained from GOES16 at current time.(but 15 or 45 min later, this time were spent in verifying the picture)

Now this repository will be used for teaching friends to programing in python.

## 🐧 Automating on Ubuntu 22.04

You can automate the wallpaper updates with `cron` by following these steps:

### 1. Copy the script
Move `wpp.py` to a folder of your choice, for example:
~/Desktop/wpp.py

---

### 2. Set the correct wallpaper path

Open your wallpaper folder and copy the **exact name** of your current wallpaper file.

Inside the script, set:

```python
path_to_current_wpp = 'Pictures/Wallpapers/your-current-wallpaper-file-name.jpg'
```
In most cases, it's just:
```python
path_to_current_wpp = 'Pictures/Wallpapers/wallpaper.jpg'
```

### 🛠️ Automating with `cron` (Ubuntu)

```bash
# 1. Find your Python executable
whereis python
```

Copy the path shown (e.g. `/usr/bin/python3` or `/home/your_user/anaconda3/bin/python`).

---

```bash
# 2. Open the crontab editor
crontab -e
```

Then, at the end of the file, add the following line (replace the paths with yours):

```cron
0,15,30,45 * * * * /path/to/python /path/to/wpp.py
```

This will run the script every 15 minutes (at 00, 15, 30, and 45 of each hour).

---

**To save:** press `Ctrl + O`, then `Enter`  
**To exit:** press `Ctrl + X`

---

✅ **Example from my machine:**

```cron
0,15,30,45 * * * * /home/v/anaconda3/bin/python /home/v/Desktop/wpp.py
```

---


### 🍎 macOS (via `launchd`)

1. Crie um arquivo `.plist` em `~/Library/LaunchAgents/com.user.goes16.plist` com o conteúdo:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.user.goes16</string>
    <key>ProgramArguments</key>
    <array>
      <string>/usr/local/bin/python3</string>
      <string>/Users/your_user/Desktop/wpp.py</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer> <!-- 900s = 15min -->
    <key>RunAtLoad</key>
    <true/>
  </dict>
</plist>
```

2. Carregue o serviço:

```bash
launchctl load ~/Library/LaunchAgents/com.user.goes16.plist
```

Agora o script será executado automaticamente a cada 15 minutos.


---
### 🪟 Windows (via `.bat`)

1. Crie um arquivo chamado `run_wallpaper.bat` no mesmo diretório do seu script `wpp.py` com o seguinte conteúdo:

```bat
@echo off
cd /d %~dp0
python wpp.py
pause
```

2. Clique duas vezes no arquivo `.bat` para executar o script.
3. Isso irá baixar todas as bandas, atualizar o plano de fundo automaticamente, e salvar as imagens localmente.

💡 Dica: você pode usar o Agendador de Tarefas do Windows para rodar o `.bat` automaticamente a cada X minutos.

---