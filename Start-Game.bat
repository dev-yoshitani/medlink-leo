@echo off
chcp 65001 >nul
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo 起動用の環境が見つかりません。docs/game.md の初回セットアップを確認してください。
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0scripts\start_game.py"
