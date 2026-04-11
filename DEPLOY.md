# Wolf Matrix v4.2 — Deploy Guide

## Быстрый запуск (локально)
```powershell
cd C:\CRYPTO\wolf_matrix
del wolf_trades.csv wolf_signals.csv wolf_state.json
pip install websockets
python run.py
```
Дашборд: http://localhost:8888

## Бесплатный облачный запуск 24/7

### Вариант 1: Oracle Cloud (лучший, навсегда бесплатный)

1. Зарегистрируйся: https://cloud.oracle.com/free
   (нужна карта для верификации, деньги НЕ списываются)

2. Создай VM: Compute → Create Instance
   - Shape: VM.Standard.A1.Flex (1 CPU, 1 GB RAM) — ALWAYS FREE
   - OS: Ubuntu 22.04
   - Скачай SSH ключ

3. Подключись и настрой:
```bash
ssh -i key.pem ubuntu@<IP>

# Установка Python
sudo apt update && sudo apt install -y python3 python3-pip
pip3 install websockets

# Загрузка файлов
mkdir -p ~/wolf_matrix
# Скопировать все .py и .html файлы через scp:
# scp -i key.pem *.py *.html ubuntu@<IP>:~/wolf_matrix/

# Запуск в фоне (не умрёт при отключении)
cd ~/wolf_matrix
nohup python3 run.py > wolf.log 2>&1 &

# Проверить что работает
tail -f wolf.log
```

4. Открой порт 8888 в Oracle:
   Networking → VCN → Security Lists → Add Ingress Rule:
   - Source: 0.0.0.0/0
   - Port: 8888

5. Дашборд: http://<IP>:8888

### Вариант 2: Запуск на своём ПК 24/7

Создай файл `start_wolf.bat`:
```batch
@echo off
cd C:\CRYPTO\wolf_matrix
:loop
echo [%date% %time%] Starting Wolf Matrix...
python run.py >> wolf.log 2>&1
echo [%date% %time%] Crashed, restarting in 10s...
timeout /t 10
goto loop
```

Добавь в автозагрузку:
Win+R → shell:startup → скопируй start_wolf.bat туда

### Вариант 3: PythonAnywhere (ограниченный)

https://www.pythonanywhere.com — бесплатный аккаунт.
Минус: не поддерживает исходящие WebSocket на бесплатном тарифе.
Нужен платный за $5/мес.

## Удалённый доступ к дашборду (с любого устройства)

Если бот на домашнем ПК, используй ngrok:
```bash
# Установи: https://ngrok.com/download
ngrok http 8888
```
Получишь URL вида https://abc123.ngrok.io — открывай с телефона.
