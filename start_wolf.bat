@echo off
title Wolf Matrix v5
cd /d "%~dp0"
:loop
echo [%date% %time%] Starting Wolf Matrix v5 (5-min)...
python run.py >> wolf.log 2>&1
echo [%date% %time%] Restarting in 10s...
timeout /t 10 /nobreak
goto loop
