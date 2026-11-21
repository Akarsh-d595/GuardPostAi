@echo off
title GuardPost AI - Dataset Classifier
cd /d "%~dp0"
echo ==========================================
echo  GUARDPOST AI - DATASET CLASSIFIER
echo  No Ollama / No Gemini / No LLM
echo ==========================================
if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creating Python virtual environment...
  py -m venv .venv
)
echo [2/4] Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
echo [3/4] Installing frontend dependencies...
cd frontend
if not exist "node_modules" npm install
start "GuardPost AI Backend" cmd /k "cd /d ""%~dp0"" && "".venv\Scripts\python.exe"" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"
echo [4/4] Starting frontend...
npm run dev
